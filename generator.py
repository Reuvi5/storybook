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
STALLED_AFTER_SECONDS = 4 * 60       # a book stuck this long (server restarted) is marked for retry

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
    """Average API cost per book, over every book that used the API (a running total in the database)."""
    rec = storage.get_record("STATS", "COSTS") or {}
    books = int(rec.get("books", 0))
    usd = rec.get("usd_micro", 0) / 1e6
    return {"books": books, "total_usd": usd, "avg_usd": (usd / books) if books else None,
            "image_calls": int(rec.get("image_calls", 0)), "analysis_calls": int(rec.get("analysis_calls", 0)),
            "retries": int(rec.get("retries", 0))}


def _save_cost(storage, user_id, book_id, meter):
    """Add what was spent since the last save to the book and to the all-books total. Called after each
    stage, so a server restart can't lose the whole book's cost. A book counts toward the average once it
    has actually used the API (a book that failed before any call doesn't drag the average down)."""
    try:
        d = meter.take()
        if not d["image_calls"] and not d["analysis_calls"]:
            return
        book = storage.get_book(user_id, book_id)
        retries = sum(max(0, int(i.get("attempt") or 0) - 1) for i in book["images"].values())
        old = book.get("cost") or {}
        cost = {k: (round(old.get(k, 0) + d[k], 5) if isinstance(d[k], float) else old.get(k, 0) + d[k]) for k in d}
        cost.update(retries=retries, estimated=FAKE_IMAGES, counted=True)
        storage.update_book(user_id, book_id, cost=cost)
        storage.add_counters("STATS", "COSTS", books=0 if old.get("counted") else 1, usd_micro=int(round(d["usd"] * 1e6)),
                             image_calls=d["image_calls"], analysis_calls=d["analysis_calls"],
                             retries=max(0, retries - int(old.get("retries", 0))))
        log.info("book_cost user=%s book=%s usd_so_far=%.4f image_calls=%s analysis_calls=%s retries=%s price=0.99",
                 user_id, book_id, cost["usd"], cost["image_calls"], cost["analysis_calls"], retries)
    except Exception:  # noqa: BLE001 - never lose a book over bookkeeping
        log.exception("cost_record_failed user=%s book=%s", user_id, book_id)


def _run(storage, user_id, book_id, only_pages):
    meter = ai.Meter()
    try:
        _pipeline(storage, user_id, book_id, only_pages, meter)
    finally:
        _save_cost(storage, user_id, book_id, meter)


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
            # 1+2. The hero, then the 20 pages. The pages start the moment the hero is DRAWN, while the
            # hero is still being checked (saves the length of a check, about 5 s). If the check fails,
            # those pages are stopped and redrawn with the next hero.
            t = time.time()
            storage.update_book(user_id, book_id, stage="character")
            hero, why = _make_hero_and_pages(storage, user_id, book_id, s, meter, timings)
            _save_cost(storage, user_id, book_id, meter)
            if hero is None:
                storage.update_book(user_id, book_id, status="failed", stage="failed", timings=timings, failure=why)
                ledger.refund_failed_book(storage, user_id, book_id)
                log.info("book_finished user=%s book=%s status=failed seconds=%.1f", user_id, book_id, time.time() - started)
                return
            timings["pages"] = round(time.time() - t, 1)

        if only_pages is not None:
            # 2. Retry: only the pages that didn't come out, with the saved hero
            t = time.time()
            storage.update_book(user_id, book_id, stage="pages")
            numbers = [int(n[4:]) for n in only_pages]
            _draw_pages(storage, user_id, book_id, s, numbers, _hero_refs(storage, user_id, book_id, hero), meter)
            timings["pages"] = round(time.time() - t, 1)
        _save_cost(storage, user_id, book_id, meter)

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
        if only_pages is None:
            timings["total"] = round(time.time() - book["created_at"], 1)  # from the moment of upload
        else:
            timings["retry"] = round(time.time() - started, 1)  # a retry never pretends to be the whole book
        storage.update_book(user_id, book_id, status="done", stage="done", timings=timings, finished_at=int(time.time()))
        log.info("book_finished user=%s book=%s status=done seconds=%.1f timings=%s", user_id, book_id, time.time() - started, timings)
    except Exception:
        log.exception("book_crashed user=%s book=%s", user_id, book_id)
        storage.update_book(user_id, book_id, status="needs_retry", stage="needs_retry", timings=timings)


def _draw_pages(storage, user_id, book_id, s, numbers, refs, meter, cancel=None):
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        list(pool.map(lambda n: _make_page(storage, user_id, book_id, s, n, refs, meter, cancel), numbers))


def _make_hero_and_pages(storage, user_id, book_id, s, meter, timings):
    """The quality loop for the hero (up to 3 drawings, best of them if none passes), with the pages
    drawn in parallel with each hero's check. Returns (hero, None) or (None, why it failed)."""
    photo = storage.get_image(user_id, book_id, "photo")
    progress = _progress(storage, user_id, book_id, "hero")
    numbers = list(range(1, stories.PAGE_COUNT + 1))
    attempts, errors = [], []
    t0 = time.time()
    for n in range(1, assets.MAX_TRIES + 1):
        progress(n, "drawing")
        try:
            png = ai.draw(stories.hero_prompt(s), [("photo.jpg", photo, "image/jpeg")], QUALITY, "Your character", meter, fmt="jpeg")
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:300])
            log.error("draw_failed image=%s/hero attempt=%s error=%s", book_id, n, str(e)[:200])
            continue
        progress(n, "checking")
        _save_hero(storage, user_id, book_id, png, None)
        timings["character"] = round(time.time() - t0, 1)
        storage.update_book(user_id, book_id, stage="pages")
        cancel = threading.Event()
        pages = threading.Thread(target=_draw_pages, daemon=True,
                                 args=(storage, user_id, book_id, s, numbers, _hero_refs(storage, user_id, book_id, png), meter, cancel))
        pages.start()
        try:
            check = ai.inspect_hero(png, photo, meter)
        except Exception as e:  # noqa: BLE001 - a checker failure doesn't throw the hero away
            log.error("check_failed image=%s/hero attempt=%s error=%s", book_id, n, str(e)[:200])
            check = {"passed": False, "score": 0, "problems": ["could not be inspected"], "regions": []}
        attempts.append({"png": png, "check": check})
        log.info("image_checked image=%s/hero attempt=%s passed=%s score=%s problems=%s", book_id, n,
                 check.get("passed"), check.get("score"), "; ".join(check.get("problems", []))[:200])
        if check.get("passed") or n == assets.MAX_TRIES and assets.best_of(attempts)["png"] is png:
            _finish_hero(storage, user_id, book_id, png, check, n)
            pages.join()
            return png, None
        # This hero didn't pass: stop its pages and try again.
        cancel.set()
        pages.join()
        for num in numbers:
            storage.set_image_status(user_id, book_id, page_name(num), "waiting", attempt=0)
        storage.update_book(user_id, book_id, stage="character")
    if not attempts:
        why = failure_reason(errors)
        storage.set_image_status(user_id, book_id, "hero", "failed", error=(errors[-1] if errors else "")[:200], attempt=assets.MAX_TRIES)
        log.error("hero_failed user=%s book=%s reason=%s", user_id, book_id, why)
        return None, why
    # None passed: keep the best of them, and draw the pages with it.
    best = assets.best_of(attempts)
    _save_hero(storage, user_id, book_id, best["png"], best["check"])
    _finish_hero(storage, user_id, book_id, best["png"], best["check"], assets.MAX_TRIES)
    storage.update_book(user_id, book_id, stage="pages")
    _draw_pages(storage, user_id, book_id, s, numbers, _hero_refs(storage, user_id, book_id, best["png"]), meter)
    return best["png"], None


def _save_hero(storage, user_id, book_id, png, check):
    storage.put_blob(book_key(user_id, book_id, "hero.png"), png)
    face = next((r["box"] for r in (check or {}).get("regions", []) if r.get("kind") == "face"), None)
    storage.put_blob(book_key(user_id, book_id, "hero-face.jpg"), face_closeup(png, face))
    storage.put_blob(book_key(user_id, book_id, thumb_for("hero")), assets.jpeg(png, 360, 80))


def _finish_hero(storage, user_id, book_id, png, check, tries):
    storage.set_image_status(user_id, book_id, "hero", "done", attempt=tries,
                             score=check.get("score", 0), passed=bool(check.get("passed")),
                             problems=check.get("problems", [])[:4])


def _progress(storage, user_id, book_id, name):
    def on_attempt(n, state):
        status = state if n == 1 else ("retrying" if state == "drawing" else "checking")
        storage.set_image_status(user_id, book_id, name, status, attempt=n)
    return on_attempt


def failure_reason(errors: list) -> str:
    """Why drawing failed, in words the book page can act on: "blocked" (OpenAI's safety filter turned
    the photo down), "service" (OpenAI unavailable: no credits, rate limit, outage), or "photo"."""
    text = " ".join(errors).lower()
    if "moderation" in text or "safety system" in text:
        return "blocked"
    if errors:
        return "service"
    return "photo"


def _make_hero(storage, user_id, book_id, s, meter):
    """Returns (picture, None), or (None, why it failed)."""
    photo = storage.get_image(user_id, book_id, "photo")
    errors = []
    png, check, tries = assets.draw_checked(
        lambda: ai.draw(stories.hero_prompt(s), [("photo.jpg", photo, "image/jpeg")], QUALITY, "Your character", meter, fmt="jpeg"),
        lambda img: ai.inspect_hero(img, photo, meter),
        f"{book_id}/hero",
        on_attempt=_progress(storage, user_id, book_id, "hero"),
        errors=errors,
    )
    if png is None:
        why = failure_reason(errors)
        storage.set_image_status(user_id, book_id, "hero", "failed", error=(errors[-1] if errors else "")[:200], attempt=tries)
        log.error("hero_failed user=%s book=%s reason=%s", user_id, book_id, why)
        return None, why
    storage.put_blob(book_key(user_id, book_id, "hero.png"), png)
    face = (next((r["box"] for r in check.get("regions", []) if r.get("kind") == "face"), None))
    storage.put_blob(book_key(user_id, book_id, "hero-face.jpg"), face_closeup(png, face))
    storage.put_blob(book_key(user_id, book_id, thumb_for("hero")), assets.jpeg(png, 360, 80))
    storage.set_image_status(user_id, book_id, "hero", "done", attempt=tries,
                             score=check.get("score", 0), passed=bool(check.get("passed")),
                             problems=check.get("problems", [])[:4])
    return png, None


def face_closeup(png: bytes, box=None) -> bytes:
    """A square, enlarged crop of the hero's face (box from the inspector, 0-1000 coords). Sent with every
    page so the model sees the face in detail, not just as a small part of the full-body design."""
    with ai.IMAGE_WORK:
        return _face_closeup(png, box)


def _face_closeup(png, box):
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


def _hero_refs(storage, user_id, book_id, hero):
    return {"full": hero,
            "jpg": assets.jpeg(hero, 1024),
            "face": storage.get_blob(book_key(user_id, book_id, "hero-face.jpg")) or face_closeup(hero, None)}


def _make_page(storage, user_id, book_id, s, number, refs, meter, cancel=None):
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
            cast_note = ("Characters who should appear: " + "; ".join(s["bible"][c] for c in page["cast"])) if page["cast"] else ""
            def make():
                if cancel is not None and cancel.is_set():
                    raise assets.Cancelled()
                return ai.draw(stories.swap_prompt(s, page),
                                [("scene.jpg", plate["jpeg_bytes"], "image/jpeg"), ("hero.jpg", refs["jpg"], "image/jpeg"),
                                 ("face.jpg", refs["face"], "image/jpeg")],
                                PAGE_QUALITY, f"{s['id']} page {number}", meter, fmt="jpeg")

            png, check, tries = assets.draw_checked(
                make,
                lambda img: ai.inspect_page(img, page["scene"], page["text"], refs["jpg"], cast_note, meter=meter),
                f"{book_id}/{name}",
                on_attempt=_progress(storage, user_id, book_id, name),
            )
            if cancel is not None and cancel.is_set():
                return  # the hero didn't pass; this page will be redrawn with the next one
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


def relayout(storage, user_id, book: dict) -> dict:
    """Place the text again on a finished book's saved pictures with the current layout rules, and
    rebuild its PDF. No OpenAI calls: it costs nothing. Returns {page: (old slot, new slot)}."""
    s = stories.get_story(book["story_id"])
    changes = {}
    for n in range(1, stories.PAGE_COUNT + 1):
        name = page_name(n)
        info = book["images"].get(name, {})
        if info.get("status") != "done":
            continue
        art = storage.get_blob(book_key(user_id, book["book_id"], file_for(name)))
        plate = assets.plate(storage, s["id"], n)
        page = s["pages"][n - 1]
        layout = template.place_text(page["text"], plate.get("regions", []), page["zone"], art, plate.get("zones"))
        changes[n] = ((info.get("layout") or {}).get("slot"), layout["slot"])
        storage.set_image_status(user_id, book["book_id"], name, "done",
                                 **{k: v for k, v in info.items() if k not in ("status", "layout")}, layout=layout)
    make_pdf(storage, user_id, storage.get_book(user_id, book["book_id"]))
    log.info("book_relayout user=%s book=%s changes=%s", user_id, book["book_id"], changes)
    return changes


def labeled_details(details: dict) -> list:
    return [(label, details.get(key, "")) for key, label in DETAIL_LABELS]


def book_pages(storage, user_id, book) -> list:
    """[(art, layout)] for the 20 story pages."""
    bid = book["book_id"]
    with ThreadPoolExecutor(max_workers=10) as pool:
        arts = list(pool.map(lambda n: storage.get_blob(book_key(user_id, bid, file_for(page_name(n)))),
                             range(1, stories.PAGE_COUNT + 1)))
    return [(art, book["images"][page_name(n)]["layout"]) for n, art in enumerate(arts, 1)]


def layouts_print_safe(book) -> bool:
    """True if every text panel sits at least 0.5 inch inside the trim (books made before the margin
    was widened need a free re-layout first)."""
    for n in range(1, stories.PAGE_COUNT + 1):
        lay = book["images"].get(page_name(n), {}).get("layout")
        if not lay:
            return False
        x, y, w, h = lay["rect"]
        if x < template.MARGIN - 0.5 or y < template.MARGIN - 0.5 or x + w > template.W - template.MARGIN + 0.5 \
                or y + h > template.H - template.MARGIN + 0.5:
            return False
    return True


def make_pdf(storage, user_id, book) -> bytes:
    s = stories.get_story(book["story_id"])
    bid = book["book_id"]
    pages = book_pages(storage, user_id, book)
    data = pdf.build_story_pdf(
        s, book["details"]["name"], labeled_details(book["details"]),
        storage.get_blob(book_key(user_id, bid, "hero.png")), storage.get_image(user_id, bid, "photo"), pages,
        book_id=bid, made_at=book["created_at"])
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
