"""
Draws a book in the background and records each image's progress, so the page can
show a progress bar per image instead of one long wait.

  1. The real photo -> ONE image call -> Jack's character (also the cover).
  2. Jack's character (not the photo) -> ONE image call per page. The pages are drawn
     at the same time, in parallel threads.

Each image is exactly one API call, with no automatic retries. Failed pages can be
remade from the book page ("Try again").

Free test mode: set FAKE_IMAGES=1 to draw placeholder images instead of calling OpenAI.
"""

import base64
import io
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

import story

log = logging.getLogger("storybook.generator")

MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
QUALITY = "low"        # fixed for every image (not shown to users)
SIZE = "1024x1536"     # portrait book page
FAKE_IMAGES = os.environ.get("FAKE_IMAGES") == "1"

# A book gets stuck if the server restarts mid-drawing. After this long with no
# progress, unfinished images are marked failed so the user can try again.
STALLED_AFTER_SECONDS = 10 * 60


def image_names() -> list:
    return ["character"] + [f"page{p['number']}" for p in story.PAGES]


def image_label(name: str) -> str:
    if name == "character":
        return "Jack (the character)"
    page = story.PAGE_BY_NUMBER[int(name[4:])]
    return f"Page {page['number']}: {page['title']}"


# ---------------------------------------------------------------------------
# One image
# ---------------------------------------------------------------------------
def create_image(file_name: str, data: bytes, mime: str, prompt: str, label: str) -> bytes:
    """ONE call to the image edit endpoint (or a placeholder in test mode). Returns PNG bytes."""
    if FAKE_IMAGES:
        return _placeholder(label)
    result = OpenAI().images.edit(
        model=MODEL,
        image=(file_name, data, mime),
        prompt=prompt,
        size=SIZE,
        quality=QUALITY,
    )
    return base64.b64decode(result.data[0].b64_json)


def _placeholder(label: str) -> bytes:
    """Test mode: wait a few seconds like a real call, then return a labeled colored image."""
    time.sleep(random.uniform(2, 5))
    colors = [(176, 128, 84), (120, 170, 220), (70, 50, 100), (190, 190, 195), (110, 150, 90)]
    img = Image.new("RGB", (1024, 1536), random.choice(colors))
    draw = ImageDraw.Draw(img)
    draw.ellipse((362, 250, 662, 600), fill=(240, 200, 170))
    try:
        font = ImageFont.load_default(size=56)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((512, 760), "TEST IMAGE", fill="white", anchor="mm", font=font)
    draw.text((512, 840), label, fill="white", anchor="mm", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _short_error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:300]


# ---------------------------------------------------------------------------
# A whole book
# ---------------------------------------------------------------------------
def start_book(storage, user_id: str, book_id: str):
    """Start drawing a new book in a background thread and return immediately."""
    threading.Thread(target=_draw_book, args=(storage, user_id, book_id), daemon=True).start()


def start_retry(storage, user_id: str, book_id: str, page_names: list):
    """Remake only the given (failed) pages, from the same Jack, in the background."""
    for name in page_names:
        storage.set_image_status(user_id, book_id, name, "waiting")
    storage.update_book(user_id, book_id, status="generating")
    threading.Thread(target=_draw_retry, args=(storage, user_id, book_id, page_names), daemon=True).start()


def _draw_book(storage, user_id, book_id):
    started = time.time()
    log.info("book_started user=%s book=%s fake=%s", user_id, book_id, FAKE_IMAGES)
    try:
        photo = storage.get_image(user_id, book_id, "photo")

        # Step 1 - the real photo -> Jack's character
        storage.set_image_status(user_id, book_id, "character", "drawing")
        t = time.time()
        try:
            character = create_image("photo.jpg", photo, "image/jpeg", story.CHARACTER_PROMPT, image_label("character"))
        except Exception as e:
            log.error("image_failed user=%s book=%s image=character seconds=%.1f error=%s",
                      user_id, book_id, time.time() - t, _short_error(e))
            storage.set_image_status(user_id, book_id, "character", "failed", _short_error(e))
            for name in image_names()[1:]:
                storage.set_image_status(user_id, book_id, name, "failed", "Not drawn: the character failed")
            return  # finish() below marks the book failed
        storage.put_image(user_id, book_id, "character", character)
        storage.set_image_status(user_id, book_id, "character", "done")
        log.info("image_done user=%s book=%s image=character seconds=%.1f", user_id, book_id, time.time() - t)

        # Step 2 - all the pages at once, from Jack's character
        _draw_pages(storage, user_id, book_id, image_names()[1:], character)
    except Exception:
        log.exception("book_crashed user=%s book=%s", user_id, book_id)
    finally:
        status = finish(storage, user_id, book_id)
        log.info("book_finished user=%s book=%s status=%s seconds=%.1f", user_id, book_id, status, time.time() - started)


def _draw_retry(storage, user_id, book_id, page_names):
    started = time.time()
    log.info("retry_started user=%s book=%s pages=%s", user_id, book_id, ",".join(page_names))
    try:
        character = storage.get_image(user_id, book_id, "character")
        _draw_pages(storage, user_id, book_id, page_names, character)
    except Exception:
        log.exception("retry_crashed user=%s book=%s", user_id, book_id)
    finally:
        status = finish(storage, user_id, book_id)
        log.info("retry_finished user=%s book=%s status=%s seconds=%.1f", user_id, book_id, status, time.time() - started)


def _draw_pages(storage, user_id, book_id, page_names, character):
    with ThreadPoolExecutor(max_workers=max(1, len(page_names))) as pool:
        jobs = [pool.submit(_draw_page, storage, user_id, book_id, name, character) for name in page_names]
    for job in jobs:
        job.result()


def _draw_page(storage, user_id, book_id, name, character):
    page = story.PAGE_BY_NUMBER[int(name[4:])]
    storage.set_image_status(user_id, book_id, name, "drawing")
    t = time.time()
    try:
        png = create_image("jack-character.png", character, "image/png", story.page_prompt(page), image_label(name))
    except Exception as e:
        log.error("image_failed user=%s book=%s image=%s seconds=%.1f error=%s",
                  user_id, book_id, name, time.time() - t, _short_error(e))
        storage.set_image_status(user_id, book_id, name, "failed", _short_error(e))
        return
    storage.put_image(user_id, book_id, name, png)
    storage.set_image_status(user_id, book_id, name, "done")
    log.info("image_done user=%s book=%s image=%s seconds=%.1f", user_id, book_id, name, time.time() - t)


def finish(storage, user_id, book_id) -> str:
    """Set the book's overall status from its images' statuses."""
    book = storage.get_book(user_id, book_id)
    if not book:
        return "missing"
    statuses = {name: book["images"].get(name, {}).get("status") for name in image_names()}
    if all(s == "done" for s in statuses.values()):
        status = "done"
    elif statuses["character"] == "failed":
        status = "failed"
    else:
        status = "needs_retry"
    storage.update_book(user_id, book_id, status=status)
    return status


def recover_if_stalled(storage, user_id, book: dict) -> dict:
    """If the server restarted mid-book, mark the stuck images failed so the user can retry."""
    if book["status"] != "generating" or time.time() - book["updated_at"] < STALLED_AFTER_SECONDS:
        return book
    for name in image_names():
        if book["images"].get(name, {}).get("status") in ("waiting", "drawing"):
            storage.set_image_status(user_id, book["book_id"], name, "failed", "Interrupted (server restarted)")
    log.warning("book_stalled user=%s book=%s", user_id, book["book_id"])
    finish(storage, user_id, book["book_id"])
    return storage.get_book(user_id, book["book_id"])
