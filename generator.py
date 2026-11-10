"""
Makes a book in the background and records every step, so the book page can show which stage
it's in and each thumbnail as soon as that picture is finished.

Stages (book["stage"]):
  character  "Creating your character"   the photo -> the hero, checked against the photo
  pages      "Drawing your 20 pages"      the hero is swapped into the 20 pre-drawn scenes, all at once
  pdf        "Putting your book together" text placed on every page, PDF built and saved
  done       "Ready"

Quality loop (every image): draw -> inspect -> redraw on failure, up to 3 drawings in total; if none
passes, keep the best of the three (assets.draw_checked).

Image statuses: waiting -> drawing -> checking -> (retrying ->) done | failed
Book statuses:  generating -> done | needs_retry | failed
"""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import ai
import assets
import book as pdf
import ledger
import stories
import template
from storage import book_key

log = logging.getLogger("storybook.generator")

FAKE_IMAGES = ai.FAKE
QUALITY = "low"                      # per-book images: fixed, not shown to users
PAGE_QUALITY = os.environ.get("PAGE_QUALITY", QUALITY)   # "medium" holds the face better, but is slower
CONCURRENCY = int(os.environ.get("IMAGE_CONCURRENCY", 20))
STALLED_AFTER_SECONDS = 10 * 60      # a book stuck this long (server restarted) is marked for retry

STAGES = {
    "character": "Creating your character",
    "pages": "Drawing your 20 pages",
    "pdf": "Putting your book together",
    "done": "Ready",
    "needs_retry": "Some pages need another try",
    "failed": "Couldn't create the character",
}

V1_NAMES = ["character", "page1", "page2", "page3"]   # books made before the 20-page template

DETAIL_LABELS = [("age", "Age"), ("favorite_color", "Favorite color"), ("favorite_food", "Favorite food"),
                 ("favorite_animal", "Favorite animal"), ("about", "About me")]


def page_name(n: int) -> str:
    return f"page{n:02d}"


def image_names(book: dict = None) -> list:
    if book and book.get("version", 1) < 2:
        return V1_NAMES
    return ["hero"] + [page_name(n) for n in range(1, stories.PAGE_COUNT + 1)]


def image_label(name: str) -> str:
    if name in ("hero", "character"):
        return "Your character"
    return f"Page {int(name[4:])}"


def new_book_record(book_id, story_id, details, now):
    return {
        "book_id": book_id, "version": 2, "story_id": story_id,
        "created_at": now, "updated_at": now, "status": "generating",
        "stage": "character", "details": details,
        "images": {name: {"status": "waiting"} for name in image_names()},
    }


def file_for(name: str) -> str:
    return "hero.png" if name == "hero" else f"{name}.jpg"


def thumb_for(name: str) -> str:
    return f"thumb-{name}.jpg"


# ---------------------------------------------------------------------------
# Starting
# ---------------------------------------------------------------------------
def start_book(storage, user_id, book_id):
    threading.Thread(target=_run, args=(storage, user_id, book_id, None), daemon=True).start()


def start_retry(storage, user_id, book_id, names):
    for name in names:
        storage.set_image_status(user_id, book_id, name, "waiting")
    storage.update_book(user_id, book_id, status="generating", stage="pages")
    threading.Thread(target=_run, args=(storage, user_id, book_id, list(names)), daemon=True).start()


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------
def cost_stats(storage) -> dict:
    """Average API cost per book, over every book ever made (from a running total in the database)."""
    rec = storage.get_record("STATS", "COSTS") or {}
    books = int(rec.get("books", 0))
    usd = rec.get("usd_micro", 0) / 1e6
    return {"books": books, "total_usd": usd, "avg_usd": (usd / books) if books else None,
            "image_calls": int(rec.get("image_calls", 0)), "analysis_calls": int(rec.get("analysis_calls", 0)),
            "retries": int(rec.get("retries", 0))}


def _record_cost(storage, user_id, book_id, meter, first_run):
    """Save what this run cost on the book (added to earlier runs) and to the all-books total."""
    book = storage.get_book(user_id, book_id)
    retries = sum(max(0, int(i.get("attempt") or 0) - 1) for i in book["images"].values())
    old = book.get("cost") or {}
    m = meter.summary()
    cost = {k: round(old.get(k, 0) + m[k], 5) if isinstance(m[k], float) else old.get(k, 0) + m[k] for k in m}
    cost["retries"] = retries
    cost["estimated"] = FAKE_IMAGES
    storage.update_book(user_id, book_id, cost=cost)
    storage.add_counters("STATS", "COSTS", books=1 if first_run else 0, usd_micro=int(round(m["usd"] * 1e6)),
                         image_calls=m["image_calls"], analysis_calls=m["analysis_calls"],
                         retries=max(0, retries - int(old.get("retries", 0))))
    log.info("book_cost user=%s book=%s usd=%.4f image_calls=%s analysis_calls=%s retries=%s price=0.99",
             user_id, book_id, m["usd"], m["image_calls"], m["analysis_calls"], retries)


def _run(storage, user_id, book_id, only_pages):
    meter = ai.Meter()
    try:
        _pipeline(storage, user_id, book_id, only_pages, meter)
    finally:
        try:
            _record_cost(storage, user_id, book_id, meter, first_run=only_pages is None)
        except Exception:  # noqa: BLE001 - never lose a book over bookkeeping
            log.exception("cost_record_failed user=%s book=%s", user_id, book_id)


def _pipeline(storage, user_id, book_id, only_pages, meter):
    started = time.time()
    book = storage.get_book(user_id, book_id)
    s = stories.get_story(book["story_id"])
    log.info("book_started user=%s book=%s story=%s retry=%s fake=%s", user_id, book_id, s["id"], only_pages is not None, FAKE_IMAGES)
    timings = dict(book.get("timings") or {})
    try:
        # 1. The hero
        if only_pages is not None:
            hero = storage.get_blob(book_key(user_id, book_id, "hero.png"))
        else:
            t = time.time()
            storage.update_book(user_id, book_id, stage="character")
            hero = _make_hero(storage, user_id, book_id, s, meter)
            timings["character"] = round(time.time() - t, 1)
            if hero is None:
                storage.update_book(user_id, book_id, status="failed", stage="failed", timings=timings)
                ledger.refund_failed_book(storage, user_id, book_id)
                log.info("book_finished user=%s book=%s status=failed seconds=%.1f", user_id, book_id, time.time() - started)
                return

        # 2. The 20 pages, all at once
        t = time.time()
        storage.update_book(user_id, book_id, stage="pages")
        numbers = [int(n[4:]) for n in only_pages] if only_pages is not None else range(1, stories.PAGE_COUNT + 1)
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            list(pool.map(lambda n: _make_page(storage, user_id, book_id, s, n, hero, meter), numbers))
        timings["pages"] = round(time.time() - t, 1)

        book = storage.get_book(user_id, book_id)
        if any(book["images"][page_name(n)]["status"] != "done" for n in range(1, stories.PAGE_COUNT + 1)):
            storage.update_book(user_id, book_id, status="needs_retry", stage="needs_retry", timings=timings)
            log.info("book_finished user=%s book=%s status=needs_retry seconds=%.1f", user_id, book_id, time.time() - started)
            return

        # 3. The PDF
        t = time.time()
        storage.update_book(user_id, book_id, stage="pdf")
        make_pdf(storage, user_id, book)
        timings["pdf"] = round(time.time() - t, 1)
        timings["total"] = round(time.time() - started, 1)
        storage.update_book(user_id, book_id, status="done", stage="done", timings=timings, finished_at=int(time.time()))
        log.info("book_finished user=%s book=%s status=done seconds=%.1f timings=%s", user_id, book_id, time.time() - started, timings)
    except Exception:
        log.exception("book_crashed user=%s book=%s", user_id, book_id)
        storage.update_book(user_id, book_id, status="needs_retry", stage="needs_retry", timings=timings)


def _progress(storage, user_id, book_id, name):
    def on_attempt(n, state):
        status = state if n == 1 else ("retrying" if state == "drawing" else "checking")
        storage.set_image_status(user_id, book_id, name, status, attempt=n)
    return on_attempt


def _make_hero(storage, user_id, book_id, s, meter):
    photo = storage.get_image(user_id, book_id, "photo")
    png, check, tries = assets.draw_checked(
        lambda: ai.draw(stories.hero_prompt(s), [("photo.jpg", photo, "image/jpeg")], QUALITY, "Your character", meter),
        lambda img: ai.inspect_hero(img, photo, meter),
        f"{book_id}/hero",
        on_attempt=_progress(storage, user_id, book_id, "hero"),
    )
    if png is None:
        storage.set_image_status(user_id, book_id, "hero", "failed", error="The character couldn't be drawn")
        return None
    storage.put_blob(book_key(user_id, book_id, "hero.png"), png)
    face = (next((r["box"] for r in check.get("regions", []) if r.get("kind") == "face"), None))
    storage.put_blob(book_key(user_id, book_id, "hero-face.jpg"), face_closeup(png, face))
    storage.put_blob(book_key(user_id, book_id, thumb_for("hero")), assets.jpeg(png, 360, 80))
    storage.set_image_status(user_id, book_id, "hero", "done", attempt=tries,
                             score=check.get("score", 0), passed=bool(check.get("passed")),
                             problems=check.get("problems", [])[:4])
    return png


def face_closeup(png: bytes, box=None) -> bytes:
    """A square, enlarged crop of the hero's face (box from the inspector, 0-1000 coords). Sent with every
    page so the model sees the face in detail, not just as a small part of the full-body design."""
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = img.size
    if box:
        x0, y0, x1, y1 = box[0] / 1000 * w, box[1] / 1000 * h, box[2] / 1000 * w, box[3] / 1000 * h
    else:  # design sheets put the face in the upper middle
        x0, y0, x1, y1 = w * 0.3, h * 0.05, w * 0.7, h * 0.32
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(x1 - x0, y1 - y0) * 1.5  # some hair and head covering around the face
    side = max(side, w * 0.25)
    crop = img.crop((max(0, cx - side / 2), max(0, cy - side / 2), min(w, cx + side / 2), min(h, cy + side / 2)))
    crop = crop.resize((768, 768))
    buf = io.BytesIO()
    crop.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _make_page(storage, user_id, book_id, s, number, hero, meter):
    name = page_name(number)
    page = s["pages"][number - 1]
    t = time.time()
    try:
        plate = assets.plate(storage, s["id"], number)
        if not plate["hero"]:
            # The hero isn't on this page: the pre-drawn, pre-checked scene is used as it is.
            art, tries = plate["jpeg_bytes"], 0
            check = {"score": plate["score"], "passed": plate["passed"], "problems": plate["problems"], "regions": []}  # zones come from the plate below
        else:
            hero_jpg = assets.jpeg(hero, 1024)
            face_jpg = storage.get_blob(book_key(user_id, book_id, "hero-face.jpg")) or face_closeup(hero, None)
            cast_note = ("Characters who should appear: " + "; ".join(s["bible"][c] for c in page["cast"])) if page["cast"] else ""
            png, check, tries = assets.draw_checked(
                lambda: ai.draw(stories.swap_prompt(s, page),
                                [("scene.jpg", plate["jpeg_bytes"], "image/jpeg"), ("hero.jpg", hero_jpg, "image/jpeg"),
                                 ("face.jpg", face_jpg, "image/jpeg")],
                                PAGE_QUALITY, f"{s['id']} page {number}", meter),
                lambda img: ai.inspect_page(img, page["scene"], page["text"], hero, cast_note, meter=meter),
                f"{book_id}/{name}",
                on_attempt=_progress(storage, user_id, book_id, name),
            )
            if png is None:
                storage.set_image_status(user_id, book_id, name, "failed", error="The page couldn't be drawn")
                return
            art = assets.jpeg(png, 1536, 92)
        # Text placement: keep off everything the inspector found on this picture AND on the
        # pre-drawn scene (the swap keeps the scene's layout, so both apply).
        if check.get("zones"):
            # this picture's own inspection says which text spots are clear
            layout = template.place_text(page["text"], check.get("regions", []), page["zone"], art, check["zones"])
        else:
            # pre-drawn scene used as-is (hero not on the page): use the scene's own inspection
            layout = template.place_text(page["text"], plate.get("regions", []), page["zone"], art, plate.get("zones"))
        storage.put_blob(book_key(user_id, book_id, file_for(name)), art)
        storage.put_blob(book_key(user_id, book_id, thumb_for(name)), assets.jpeg(art, 360, 80))
        storage.set_image_status(user_id, book_id, name, "done", attempt=tries, score=check.get("score", 0),
                                 passed=bool(check.get("passed")), problems=check.get("problems", [])[:4],
                                 layout=layout, seconds=round(time.time() - t, 1))
        log.info("page_done user=%s book=%s page=%s tries=%s score=%s text=%s seconds=%.1f", user_id, book_id,
                 number, tries, check.get("score"), layout["slot"], time.time() - t)
    except Exception as e:  # noqa: BLE001
        log.exception("page_crashed user=%s book=%s page=%s", user_id, book_id, number)
        storage.set_image_status(user_id, book_id, name, "failed", error=f"{type(e).__name__}"[:100])


def labeled_details(details: dict) -> list:
    return [(label, details.get(key, "")) for key, label in DETAIL_LABELS]


def make_pdf(storage, user_id, book) -> bytes:
    s = stories.get_story(book["story_id"])
    bid = book["book_id"]
    with ThreadPoolExecutor(max_workers=10) as pool:
        arts = list(pool.map(lambda n: storage.get_blob(book_key(user_id, bid, file_for(page_name(n)))),
                             range(1, stories.PAGE_COUNT + 1)))
    pages = [(art, book["images"][page_name(n)]["layout"]) for n, art in enumerate(arts, 1)]
    data = pdf.build_story_pdf(
        s, book["details"]["name"], labeled_details(book["details"]),
        storage.get_blob(book_key(user_id, bid, "hero.png")), storage.get_image(user_id, bid, "photo"), pages)
    storage.put_blob(book_key(user_id, bid, "book.pdf"), data)
    log.info("pdf_saved user=%s book=%s bytes=%s", user_id, bid, len(data))
    return data


def recover_if_stalled(storage, user_id, book: dict) -> dict:
    """If the server restarted mid-book, mark the stuck images failed so the user can retry."""
    if book["status"] != "generating" or time.time() - book["updated_at"] < STALLED_AFTER_SECONDS:
        return book
    for name in image_names(book):
        if book["images"].get(name, {}).get("status") not in ("done", "failed"):
            storage.set_image_status(user_id, book["book_id"], name, "failed", error="Interrupted (server restarted)")
    hero_ok = book["images"].get("hero", book["images"].get("character", {})).get("status") == "done"
    storage.update_book(user_id, book["book_id"], status="needs_retry" if hero_ok else "failed",
                        stage="needs_retry" if hero_ok else "failed")
    if not hero_ok:
        ledger.refund_failed_book(storage, user_id, book["book_id"])
    log.warning("book_stalled user=%s book=%s", user_id, book["book_id"])
    return storage.get_book(user_id, book["book_id"])
