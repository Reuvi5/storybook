"""
Storybook: a cartoon "Jack and the Beanstalk" starring the child in the uploaded photo.

Flow (one click):
  1. The real photo -> ONE image call -> Jack's character design (also the book cover).
  2. Jack's character image (NOT the photo) -> ONE image call per page -> the story pages.
     The pages run at the same time.
  3. The user downloads one PDF: cover, the story pages with the text drawn on top,
     and an About Me page with the details they typed in.

Each image is exactly one API call. There are no automatic retries; if a page fails,
the user can click "Try again" to remake only the missing pages.

The API key is read from OPENAI_API_KEY (.env locally, Render's Environment tab when deployed).
"""

import base64
import io
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from openai import OpenAI, OpenAIError
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.middleware.proxy_fix import ProxyFix

import story
from book import build_pdf

try:
    from pillow_heif import register_heif_opener  # iPhone HEIC photos (optional)
    register_heif_opener()
except ImportError:
    pass

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB photo cap

# On Render, requests arrive through Render's proxy, which passes along the visitor's real
# IP address in a header. This tells Flask to use it (needed for the per-person limit below).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# Limit: each person (IP address) can make this many books per hour.
BOOKS_PER_WINDOW = 2
WINDOW_SECONDS = 60 * 60
_book_times = defaultdict(list)  # IP address -> times their recent books were started
_limit_lock = threading.Lock()

MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
QUALITY = "low"         # fixed for every image (not shown to users)
SIZE = "1024x1536"      # portrait book page

# Generated books are kept on the server for a while, then deleted.
BOOKS_DIR = Path(tempfile.gettempdir()) / "storybook"
KEEP_SECONDS = 2 * 60 * 60  # 2 hours
BOOK_ID = re.compile(r"^[0-9a-f]{32}$")

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


def create_image(file_name: str, data: bytes, mime: str, prompt: str) -> bytes:
    """ONE call to the image edit endpoint. Returns PNG bytes, or raises OpenAIError."""
    result = OpenAI().images.edit(
        model=MODEL,
        image=(file_name, data, mime),
        prompt=prompt,
        size=SIZE,
        quality=QUALITY,
    )
    return base64.b64decode(result.data[0].b64_json)


def make_one_page(folder: Path, page: dict, character: bytes):
    """Make one story page from Jack's character image. Returns an error message or None."""
    try:
        png = create_image("jack-character.png", character, "image/png", story.page_prompt(page))
    except OpenAIError as e:
        return str(e)
    (folder / f"page{page['number']}.png").write_bytes(png)
    return None


def make_pages(folder: Path, numbers: list) -> dict:
    """Make the given pages at the same time, one API call each. Returns {page number: error}."""
    character = (folder / "character.png").read_bytes()
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {n: pool.submit(make_one_page, folder, story.PAGE_BY_NUMBER[n], character) for n in numbers}
    return {n: job.result() for n, job in jobs.items() if job.result()}


def book_folder(book_id: str) -> Path:
    if not BOOK_ID.match(book_id):
        abort(404)
    folder = BOOKS_DIR / book_id
    if not (folder / "meta.json").is_file():
        abort(404)
    return folder


def load_meta(folder: Path) -> dict:
    return json.loads((folder / "meta.json").read_text())


def save_meta(folder: Path, meta: dict):
    (folder / "meta.json").write_text(json.dumps(meta))


def missing_pages(folder: Path) -> list:
    return [p["number"] for p in story.PAGES if not (folder / f"page{p['number']}.png").is_file()]


def delete_old_books():
    if not BOOKS_DIR.is_dir():
        return
    for folder in BOOKS_DIR.iterdir():
        if folder.is_dir() and time.time() - folder.stat().st_mtime > KEEP_SECONDS:
            shutil.rmtree(folder, ignore_errors=True)


def reserve_book(ip: str) -> int:
    """Count a new book for this IP. Returns 0 if allowed, or the seconds to wait if over the limit."""
    with _limit_lock:
        now = time.time()
        recent = [t for t in _book_times[ip] if now - t < WINDOW_SECONDS]
        if len(recent) >= BOOKS_PER_WINDOW:
            _book_times[ip] = recent
            return int(WINDOW_SECONDS - (now - recent[0])) + 1
        recent.append(now)
        _book_times[ip] = recent
        return 0


def release_book(ip: str):
    """Give the slot back if the book failed before anything was made."""
    with _limit_lock:
        if _book_times[ip]:
            _book_times[ip].pop()


def form_page(**kwargs):
    return render_template("index.html", details=DETAILS, values=kwargs.pop("values", {}), **kwargs)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return form_page()


@app.post("/make")
def make():
    delete_old_books()

    values = {"name": request.form.get("name", "").strip()[:40]}
    for key, _label, max_len in DETAILS:
        values[key] = request.form.get(key, "").strip()[:max_len]

    if not values["name"]:
        return form_page(error="Please enter the child's name.", values=values)

    upload = request.files.get("photo")
    if not upload or not upload.filename:
        return form_page(error="Please upload a photo of the child.", values=values)
    try:
        photo = prepare_photo(upload.read())
    except (UnidentifiedImageError, ValueError):
        return form_page(error="That file isn't an image I can read. Try a JPG or PNG.", values=values)

    if not os.environ.get("OPENAI_API_KEY"):
        return form_page(error="The server is missing its OpenAI API key.", values=values)

    # Per-person limit: checked right before any paid API call.
    ip = request.remote_addr or "unknown"
    wait = reserve_book(ip)
    if wait:
        minutes = max(1, (wait + 59) // 60)
        return form_page(
            error=f"You can make {BOOKS_PER_WINDOW} books per hour. Please try again in about {minutes} minute{'s' if minutes != 1 else ''}.",
            values=values,
        )

    # Step 1 - ONE call: the real photo -> Jack's character.
    try:
        character = create_image("photo.jpg", photo, "image/jpeg", story.CHARACTER_PROMPT)
    except OpenAIError as e:
        release_book(ip)  # nothing was made, so this attempt doesn't count
        return form_page(error=f"Sorry, creating the character failed: {e}", values=values)

    # The photo is only needed for step 1, so it is never saved. Only the cartoon is kept.
    book_id = uuid.uuid4().hex
    folder = BOOKS_DIR / book_id
    folder.mkdir(parents=True)
    (folder / "character.png").write_bytes(character)
    save_meta(folder, {"details": values, "errors": {}})

    # Step 2 - one call per page, drawn from Jack's character.
    errors = make_pages(folder, [p["number"] for p in story.PAGES])
    save_meta(folder, {"details": values, "errors": errors})

    return redirect(url_for("book", book_id=book_id))


@app.get("/book/<book_id>")
def book(book_id):
    folder = book_folder(book_id)
    meta = load_meta(folder)
    missing = missing_pages(folder)
    return render_template(
        "book.html",
        book_id=book_id,
        title=story.BOOK_TITLE,
        pages=story.PAGES,
        details=DETAILS,
        values=meta["details"],
        missing=missing,
        errors=meta.get("errors", {}),
    )


@app.post("/book/<book_id>/retry")
def retry(book_id):
    """Remake only the pages that failed, from the same Jack."""
    folder = book_folder(book_id)
    meta = load_meta(folder)
    missing = missing_pages(folder)
    if missing:
        meta["errors"] = make_pages(folder, missing)
        save_meta(folder, meta)
    return redirect(url_for("book", book_id=book_id))


@app.get("/book/<book_id>/image/<name>.png")
def image(book_id, name):
    folder = book_folder(book_id)
    allowed = {"character"} | {f"page{p['number']}" for p in story.PAGES}
    path = folder / f"{name}.png"
    if name not in allowed or not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/png")


@app.get("/book/<book_id>/download")
def download(book_id):
    folder = book_folder(book_id)
    if missing_pages(folder):
        return redirect(url_for("book", book_id=book_id))
    meta = load_meta(folder)
    details = meta["details"]

    images = {"character": (folder / "character.png").read_bytes()}
    for p in story.PAGES:
        images[p["number"]] = (folder / f"page{p['number']}.png").read_bytes()

    labeled = [(label, details.get(key, "")) for key, label, _ in DETAILS]
    pdf = build_pdf(details["name"], labeled, images)

    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", details["name"]).strip("-") or "My"
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_name}-Jack-and-the-Beanstalk.pdf",
    )


@app.errorhandler(413)
def too_large(_):
    return form_page(error="That photo is too big (15 MB max)."), 413


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
