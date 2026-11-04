"""
Storybook: a cartoon "Jack and the Beanstalk" starring the person in the uploaded photo.

  - Sign in with Google (auth.py).
  - Each user's books are saved (storage.py: AWS DynamoDB + S3, or a local folder in
    development), so they're still there on the next visit.
  - Books are drawn in the background (generator.py); the book page shows a progress
    bar per image while it works.
  - The finished book downloads as one PDF (book.py).
  - Everything important is logged to the console (Render shows it under "Logs").

Secrets come from environment variables (.env locally, Render's Environment tab when
deployed), never from the code. See .env.example and SETUP.md.
"""

import io
import logging
import os
import re
import secrets
import time
import uuid
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()  # must run before the other modules read their settings

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.middleware.proxy_fix import ProxyFix

import generator
import story
from auth import current_user, init_auth, login_required
from book import build_pdf
from storage import get_storage

try:
    from pillow_heif import register_heif_opener  # iPhone HEIC photos (optional)
    register_heif_opener()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Logging: one line per event, e.g. "2026-11-02 12:00:01 INFO storybook.generator image_done user=... image=page2 seconds=21.4"
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # the OpenAI library is chatty
log = logging.getLogger("storybook.app")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB photo cap

# On Render, requests come through Render's proxy. This makes Flask see the visitor's real
# address and that the site is https (needed for Google's sign-in redirect).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

secret = os.environ.get("FLASK_SECRET_KEY")
if not secret:
    log.warning("FLASK_SECRET_KEY is not set: using a temporary key (everyone is signed out on restart)")
    secret = secrets.token_hex(32)
app.secret_key = secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),  # https-only cookies on Render
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

storage = get_storage()
app.extensions["storybook_storage"] = storage
init_auth(app)

# Each user can start this many books per hour (failed books don't count).
BOOKS_PER_HOUR = int(os.environ.get("BOOKS_PER_HOUR", 2))

# About Me fields: (form name, label, max length)
DETAILS = [
    ("age", "Age", 20),
    ("favorite_color", "Favorite color", 40),
    ("favorite_food", "Favorite food", 40),
    ("favorite_animal", "Favorite animal", 40),
    ("about", "About me", 600),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def prepare_photo(raw: bytes) -> bytes:
    """Fix phone rotation, shrink to max 1024px, re-encode as JPEG."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def get_own_book(book_id: str) -> dict:
    """The signed-in user's book, or 404. Users can only ever see their own books."""
    user = current_user()
    book = storage.get_book(user["id"], book_id)
    if not book:
        abort(404)
    return generator.recover_if_stalled(storage, user["id"], book)


def wait_minutes(user_id: str) -> int:
    """0 if the user may start a book now, otherwise roughly how many minutes to wait."""
    hour_ago = time.time() - 3600
    recent = sorted(
        b["created_at"] for b in storage.list_books(user_id)
        if b["created_at"] > hour_ago and b["status"] != "failed"
    )
    if len(recent) < BOOKS_PER_HOUR:
        return 0
    return max(1, int((recent[-BOOKS_PER_HOUR] + 3600 - time.time()) // 60) + 1)


def image_status_list(book: dict) -> list:
    out = []
    for name in generator.image_names():
        info = book["images"].get(name, {})
        status = info.get("status", "waiting")
        out.append({
            "name": name,
            "label": generator.image_label(name),
            "status": status,
            "url": url_for("image", book_id=book["book_id"], name=name) if status == "done" else None,
        })
    return out


@app.context_processor
def inject_user():
    return {"user": current_user(), "fake_images": generator.FAKE_IMAGES}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    if not current_user():
        return render_template("landing.html")
    return render_template("index.html", details=DETAILS, values={}, books_per_hour=BOOKS_PER_HOUR)


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


@app.post("/make")
@login_required
def make():
    user = current_user()

    values = {"name": request.form.get("name", "").strip()[:40]}
    for key, _label, max_len in DETAILS:
        values[key] = request.form.get(key, "").strip()[:max_len]

    def form_error(message):
        return render_template("index.html", details=DETAILS, values=values,
                               books_per_hour=BOOKS_PER_HOUR, error=message)

    if not values["name"]:
        return form_error("Please enter the name.")
    upload = request.files.get("photo")
    if not upload or not upload.filename:
        return form_error("Please upload a photo.")
    try:
        photo = prepare_photo(upload.read())
    except (UnidentifiedImageError, ValueError):
        return form_error("That file isn't an image I can read. Try a JPG or PNG.")
    if not generator.FAKE_IMAGES and not os.environ.get("OPENAI_API_KEY"):
        return form_error("The server is missing its OpenAI API key.")

    wait = wait_minutes(user["id"])
    if wait:
        log.info("rate_limited user=%s wait_minutes=%s", user["id"], wait)
        return form_error(f"You can make {BOOKS_PER_HOUR} books per hour. Please try again in about {wait} minute{'s' if wait != 1 else ''}.")

    now = int(time.time())
    book_id = uuid.uuid4().hex
    storage.put_image(user["id"], book_id, "photo", photo)
    storage.create_book(user["id"], {
        "book_id": book_id,
        "created_at": now,
        "updated_at": now,
        "status": "generating",
        "details": values,
        "images": {name: {"status": "waiting"} for name in generator.image_names()},
    })
    log.info("book_created user=%s book=%s", user["id"], book_id)
    generator.start_book(storage, user["id"], book_id)
    return redirect(url_for("book", book_id=book_id))


@app.get("/books")
@login_required
def books():
    user = current_user()
    items = storage.list_books(user["id"])
    for b in items:
        b["cover_url"] = (url_for("image", book_id=b["book_id"], name="character")
                          if b["images"].get("character", {}).get("status") == "done" else None)
        b["created_text"] = time.strftime("%b %d, %Y", time.gmtime(b["created_at"]))
    return render_template("books.html", books=items)


@app.get("/book/<book_id>")
@login_required
def book(book_id):
    b = get_own_book(book_id)
    return render_template(
        "book.html",
        book=b,
        book_id=book_id,
        title=story.BOOK_TITLE,
        pages=story.PAGES,
        details=DETAILS,
        values=b["details"],
        images=image_status_list(b),
        failed=[i for i in image_status_list(b) if i["status"] == "failed"],
    )


@app.get("/book/<book_id>/status")
@login_required
def status(book_id):
    """Polled by the book page every 2 seconds while the book is being drawn."""
    b = get_own_book(book_id)
    images = image_status_list(b)
    return jsonify({
        "status": b["status"],
        "done": sum(1 for i in images if i["status"] == "done"),
        "total": len(images),
        "images": images,
    })


@app.post("/book/<book_id>/retry")
@login_required
def retry(book_id):
    user = current_user()
    b = get_own_book(book_id)
    if b["status"] == "needs_retry":
        failed = [n for n in generator.image_names()[1:] if b["images"].get(n, {}).get("status") == "failed"]
        if failed:
            generator.start_retry(storage, user["id"], book_id, failed)
    return redirect(url_for("book", book_id=book_id))


@app.get("/book/<book_id>/image/<name>")
@login_required
def image(book_id, name):
    user = current_user()
    get_own_book(book_id)
    if name not in ["photo"] + generator.image_names():
        abort(404)
    url = storage.image_url(user["id"], book_id, name)
    if url:  # AWS: a temporary link straight to the private S3 image
        return redirect(url)
    data = storage.get_image(user["id"], book_id, name)
    if data is None:
        abort(404)
    return send_file(io.BytesIO(data), mimetype="image/jpeg" if name == "photo" else "image/png")


@app.get("/book/<book_id>/download")
@login_required
def download(book_id):
    user = current_user()
    b = get_own_book(book_id)
    if b["status"] != "done":
        return redirect(url_for("book", book_id=book_id))
    details = b["details"]

    images = {"character": storage.get_image(user["id"], book_id, "character"),
              "photo": storage.get_image(user["id"], book_id, "photo")}
    for p in story.PAGES:
        images[p["number"]] = storage.get_image(user["id"], book_id, f"page{p['number']}")

    labeled = [(label, details.get(key, "")) for key, label, _ in DETAILS]
    pdf = build_pdf(details["name"], labeled, images)
    log.info("pdf_download user=%s book=%s bytes=%s", user["id"], book_id, len(pdf))

    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", details["name"]).strip("-") or "My"
    return send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True,
                     download_name=f"{safe_name}-Jack-and-the-Beanstalk.pdf")


@app.post("/book/<book_id>/delete")
@login_required
def delete(book_id):
    user = current_user()
    b = get_own_book(book_id)
    if b["status"] == "generating":
        flash("Please wait until the book is finished before deleting it.")
        return redirect(url_for("book", book_id=book_id))
    storage.delete_book(user["id"], book_id)
    log.info("book_deleted user=%s book=%s", user["id"], book_id)
    flash("Book deleted.")
    return redirect(url_for("books"))


@app.errorhandler(404)
def not_found(_):
    return render_template("message.html", title="Not found",
                           message="That page doesn't exist, or it isn't yours."), 404


@app.errorhandler(413)
def too_large(_):
    return render_template("message.html", title="Photo too big",
                           message="That photo is too big (15 MB max)."), 413


@app.errorhandler(500)
def server_error(e):
    log.exception("server_error path=%s", request.path)
    return render_template("message.html", title="Something went wrong",
                           message="Sorry, something went wrong on our side. Please try again."), 500


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
