"""
Storybook: a 20-page cartoon storybook starring the person in the uploaded photo.
Two stories share one template: Jack and the Beanstalk, and Little Red Riding Hood.

  - Sign in with Google (auth.py).
  - Wallet: add funds with Stripe (test mode), each book costs $0.99, refunds, full history
    (wallet.py, ledger.py).
  - Books are made in the background (generator.py) from pre-drawn scenes and a character bible
    (assets.py, stories.py), checked image by image (ai.py), laid out by one template
    (template.py) and saved as a PDF (book.py).
  - Everything is stored in AWS (storage.py: DynamoDB + S3), so books and PDFs are still there
    on the next visit. Locally, without AWS settings, a local_data/ folder is used.
  - Everything important is logged to the console (Render shows it under "Logs").

Secrets come from environment variables (.env locally, Render's Environment tab when deployed),
never from the code. See .env.example and SETUP.md.
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

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for  # noqa: E402
from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

import ai  # noqa: E402
import assets  # noqa: E402
import checks  # noqa: E402
import generator  # noqa: E402
import ledger  # noqa: E402
import orders  # noqa: E402
import stories  # noqa: E402
import story as story_v1  # noqa: E402
import wallet  # noqa: E402
from auth import current_user, init_auth, login_required  # noqa: E402
from book import build_pdf as build_pdf_v1, copyright_lines, cover_geometry  # noqa: E402
from storage import book_key, content_type, get_storage, story_key  # noqa: E402

try:
    from pillow_heif import register_heif_opener  # iPhone HEIC photos (optional)
    register_heif_opener()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Logging: one line per event, e.g. "... INFO storybook.generator page_done user=... page=4 tries=1 seconds=21.4"
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
app.register_blueprint(wallet.bp)
app.register_blueprint(orders.bp)

# Each user can start this many books per hour (failed books don't count).
BOOKS_PER_HOUR = int(os.environ.get("BOOKS_PER_HOUR", 3))

# About Me fields: (form name, label, max length)
DETAILS = [
    ("age", "Age", 20),
    ("favorite_color", "Favorite color", 40),
    ("favorite_food", "Favorite food", 40),
    ("favorite_animal", "Favorite animal", 40),
    ("about", "About me", 600),
]
MAX_TRIES = assets.MAX_TRIES


def attempt_text(info: dict) -> str:
    """The attempt count for one image, as shown on its tile (the quality loop, made visible)."""
    status, n = info.get("status", "waiting"), int(info.get("attempt") or 0)
    if status == "waiting":
        return "Waiting"
    if status in ("drawing", "retrying"):
        return f"{'Redrawing' if n > 1 else 'Drawing'} · try {max(n, 1)} of {MAX_TRIES}"
    if status == "checking":
        return f"Checking · try {max(n, 1)} of {MAX_TRIES}"
    if status == "failed":
        return "Failed"
    if n == 0:
        return "Pre-drawn scene · checked"
    if info.get("passed"):
        return f"Passed on try {n} of {MAX_TRIES}"
    return f"None passed · best of {n}"


@app.template_filter("datetime")
def _datetime(ts):
    return time.strftime("%b %d, %Y %H:%M UTC", time.gmtime(int(ts))) if ts else ""


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


def file_url(key: str) -> str:
    """A direct (S3, temporary) link to a stored file, or the app's own route locally."""
    return storage.blob_url(key) or url_for("blob", key=key)


def image_list(book: dict) -> list:
    """Every picture in the book with its state and (when finished) its thumbnail."""
    uid = current_user()["id"]
    out = []
    for name in generator.image_names(book):
        info = book["images"].get(name, {})
        status = info.get("status", "waiting")
        thumb = full = None
        if status == "done":
            if book.get("version", 1) >= 2:
                thumb = file_url(book_key(uid, book["book_id"], generator.thumb_for(name)))
                full = file_url(book_key(uid, book["book_id"], generator.file_for(name)))
            else:
                thumb = full = url_for("image", book_id=book["book_id"], name=name)
        out.append({
            "name": name, "label": generator.image_label(name), "status": status,
            "state": attempt_text(info),
            "attempt": info.get("attempt"), "thumb": thumb, "full": full,
            "layout": info.get("layout"), "score": info.get("score"), "passed": info.get("passed"),
        })
    return out


def story_cards() -> list:
    cards = []
    for s in stories.STORIES.values():
        ready = assets.story_ready(storage, s["id"])
        cover = file_url(story_key(s["id"], "plates/thumb-01.jpg")) if ready else None
        cards.append({"id": s["id"], "title": s["title"], "hero": s["hero_name"], "ready": ready, "cover": cover,
                      "blurb": s["pages"][0]["text"]})
    return cards


@app.context_processor
def inject_costs():
    def avg_cost():
        try:
            return generator.cost_stats(storage)
        except Exception:  # noqa: BLE001
            log.exception("cost_stats_failed")
            return {"books": 0, "avg_usd": None}
    def print_stats():
        try:
            return orders.print_stats(storage)
        except Exception:  # noqa: BLE001
            return {"orders": 0, "avg_lulu": None}
    return {"avg_cost": avg_cost, "print_stats": print_stats, "print_price": ledger.PRINT_PRICE_CENTS}


@app.context_processor
def inject_user():
    user = current_user()
    balance = None
    if user:
        try:
            balance = storage.get_balance(user["id"])
        except Exception:  # never break a page over the header
            log.exception("balance_lookup_failed")
    return {"user": user, "fake_images": generator.FAKE_IMAGES, "balance": balance,
            "money": ledger.money, "price": ledger.BOOK_PRICE_CENTS}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    if not current_user():
        return render_template("landing.html")
    return render_template("index.html", details=DETAILS, values={}, books_per_hour=BOOKS_PER_HOUR,
                           stories=story_cards())


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
    story_id = request.form.get("story", "")

    def form_error(message, field_errors=None):
        return render_template("index.html", details=DETAILS, values=values, books_per_hour=BOOKS_PER_HOUR,
                               stories=story_cards(), chosen=story_id, error=message, field_errors=field_errors or {})

    if story_id not in stories.STORIES:
        return form_error("Please choose a story.")
    if not assets.story_ready(storage, story_id):
        return form_error("That story isn't ready yet. Please choose the other one.")
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

    # Nothing inappropriate gets drawn or printed: check the name and About Me before charging.
    check_meter = ai.Meter()
    problems = checks.check_details(values, check_meter)
    if problems:
        log.info("details_rejected user=%s fields=%s", user["id"], ",".join(problems))
        return form_error("Please fix the highlighted details. This book gets printed, so it has to be right.", problems)

    if storage.get_balance(user["id"]) < ledger.BOOK_PRICE_CENTS:  # say this before the hourly limit
        return form_error(f"Each book costs {ledger.money(ledger.BOOK_PRICE_CENTS)}, and your balance is "
                          f"{ledger.money(storage.get_balance(user['id']))}. Add funds in your Wallet first.")

    wait = wait_minutes(user["id"])
    if wait:
        log.info("rate_limited user=%s wait_minutes=%s", user["id"], wait)
        return form_error(f"You can make {BOOKS_PER_HOUR} books per hour. Please try again in about {wait} minute{'s' if wait != 1 else ''}.")

    now = int(time.time())
    book_id = uuid.uuid4().hex
    if not ledger.charge_for_book(storage, user["id"], book_id, f"{stories.get_story(story_id)['title']}, starring {values['name']}"):
        return form_error(f"Each book costs {ledger.money(ledger.BOOK_PRICE_CENTS)}, and your balance is "
                          f"{ledger.money(storage.get_balance(user['id']))}. Add funds in your Wallet first.")
    storage.put_image(user["id"], book_id, "photo", photo)
    record = generator.new_book_record(book_id, story_id, values, now)
    if check_meter.usd:  # the checks are part of what this book cost to make
        record["cost"] = {**check_meter.summary(), "retries": 0, "estimated": False, "counted": False}
        storage.add_counters("STATS", "COSTS", usd_micro=int(round(check_meter.usd * 1e6)),
                             analysis_calls=check_meter.analysis_calls)
    storage.create_book(user["id"], record)
    log.info("book_created user=%s book=%s story=%s", user["id"], book_id, story_id)
    generator.start_book(storage, user["id"], book_id)
    return redirect(url_for("book", book_id=book_id))


@app.get("/books")
@login_required
def books():
    user = current_user()
    items = storage.list_books(user["id"])
    for b in items:
        if b.get("version", 1) >= 2:
            done = b["images"].get("hero", {}).get("status") == "done"
            b["cover_url"] = file_url(book_key(user["id"], b["book_id"], "thumb-hero.jpg")) if done else None
            b["title"] = stories.get_story(b["story_id"])["title"]
        else:
            done = b["images"].get("character", {}).get("status") == "done"
            b["cover_url"] = url_for("image", book_id=b["book_id"], name="character") if done else None
            b["title"] = story_v1.BOOK_TITLE
        b["created_text"] = time.strftime("%b %d, %Y", time.gmtime(b["created_at"]))
    return render_template("books.html", books=items)


@app.get("/book/<book_id>")
@login_required
def book(book_id):
    b = get_own_book(book_id)
    if b.get("version", 1) < 2:
        images = image_list(b)
        return render_template("book_v1.html", book=b, book_id=book_id, title=story_v1.BOOK_TITLE,
                               pages=story_v1.PAGES, details=DETAILS, values=b["details"], images=images,
                               failed=[i for i in images if i["status"] == "failed"])
    s = stories.get_story(b["story_id"])
    images = image_list(b)
    return render_template(
        "book.html", book=b, book_id=book_id, story=s, images=images, details=DETAILS, values=b["details"],
        stage_label=generator.STAGES.get(b.get("stage"), ""), pages=s["pages"],
        failed=[i for i in images if i["status"] == "failed"],
        photo_url=url_for("image", book_id=book_id, name="photo"), now_ts=int(time.time()),
        cover=cover_geometry(s["title"]), copyright=copyright_lines(s["title"], b["details"]["name"], book_id, b["created_at"]),
        print_price=ledger.PRINT_PRICE_CENTS,
    )


@app.get("/book/<book_id>/status")
@login_required
def status(book_id):
    """Polled by the book page every 1.5 seconds while the book is being made."""
    b = get_own_book(book_id)
    images = image_list(b)
    return jsonify({
        "status": b["status"],
        "stage": b.get("stage"),
        "stage_label": generator.STAGES.get(b.get("stage"), ""),
        "done": sum(1 for i in images if i["status"] == "done"),
        "total": len(images),
        "elapsed": int(time.time() - b["created_at"]),
        "images": [{k: i[k] for k in ("name", "label", "status", "state", "thumb")} for i in images],
    })


@app.post("/book/<book_id>/retry")
@login_required
def retry(book_id):
    user = current_user()
    b = get_own_book(book_id)
    if b.get("version", 1) >= 2 and b["status"] == "needs_retry":
        failed = [n for n in generator.image_names(b)[1:] if b["images"].get(n, {}).get("status") != "done"]
        generator.start_retry(storage, user["id"], book_id, failed)
    return redirect(url_for("book", book_id=book_id))


@app.post("/book/<book_id>/relayout")
@login_required
def relayout(book_id):
    """Re-place the text on a finished book with the current layout rules and rebuild its PDF. Free:
    no new pictures are drawn. Used for testing layout changes without paying for a new book."""
    user = current_user()
    b = get_own_book(book_id)
    if b.get("version", 1) < 2 or b["status"] != "done":
        abort(404)
    changes = generator.relayout(storage, user["id"], b)
    moved = sum(1 for old, new in changes.values() if old != new)
    flash(f"Text placed again with the current rules: {moved} of {len(changes)} pages moved. The PDF was rebuilt.")
    return redirect(url_for("book", book_id=book_id))


@app.get("/book/<book_id>/image/<name>")
@login_required
def image(book_id, name):
    """The uploaded photo, and pictures of books made before the 20-page template."""
    user = current_user()
    get_own_book(book_id)
    if name not in ["photo"] + generator.V1_NAMES:
        abort(404)
    url = storage.image_url(user["id"], book_id, name)
    if url:  # AWS: a temporary link straight to the private S3 image
        return redirect(url)
    data = storage.get_image(user["id"], book_id, name)
    if data is None:
        abort(404)
    return send_file(io.BytesIO(data), mimetype="image/jpeg" if name == "photo" else "image/png")


@app.get("/file/<path:key>")
@login_required
def blob(key):
    """Local development only: serves stored files (on AWS, pages link straight to S3)."""
    user = current_user()
    if not (key.startswith(f"books/{user['id']}/") or key.startswith("stories/")):
        abort(404)
    try:
        data = storage.get_blob(key)
    except ValueError:
        abort(404)
    if data is None:
        abort(404)
    return send_file(io.BytesIO(data), mimetype=content_type(key), max_age=3600)


@app.get("/book/<book_id>/download")
@login_required
def download(book_id):
    user = current_user()
    b = get_own_book(book_id)
    if b["status"] != "done":
        return redirect(url_for("book", book_id=book_id))
    details = b["details"]
    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", details["name"]).strip("-") or "My"

    if b.get("version", 1) < 2:
        images = {"character": storage.get_image(user["id"], book_id, "character"),
                  "photo": storage.get_image(user["id"], book_id, "photo")}
        for p in story_v1.PAGES:
            images[p["number"]] = storage.get_image(user["id"], book_id, f"page{p['number']}")
        labeled = [(label, details.get(key, "")) for key, label, _ in DETAILS]
        data = build_pdf_v1(details["name"], labeled, images)
        return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True,
                         download_name=f"{safe_name}-Jack-and-the-Beanstalk.pdf")

    s = stories.get_story(b["story_id"])
    filename = f"{safe_name}-{re.sub(r'[^A-Za-z0-9]+', '-', s['title']).strip('-')}.pdf"
    key = book_key(user["id"], book_id, "book.pdf")
    if hasattr(storage, "s3"):
        if storage.get_blob(key) is None:  # older finished book without a saved PDF: make it now
            generator.make_pdf(storage, user["id"], b)
        log.info("pdf_download user=%s book=%s", user["id"], book_id)
        return redirect(storage.s3.generate_presigned_url(
            "get_object", ExpiresIn=300,
            Params={"Bucket": storage.bucket, "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"'}))
    data = storage.get_blob(key) or generator.make_pdf(storage, user["id"], b)
    log.info("pdf_download user=%s book=%s bytes=%s", user["id"], book_id, len(data))
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True, download_name=filename)


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
