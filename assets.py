"""
Story assets: the character bible and the pre-drawn scenes ("plates"), shared by every book.

Stored in the same database and bucket as the books:
  DynamoDB, partition "STORY#<story>":
    sk "BIBLE#<character>"  {name, description, image, score, passed, problems, attempts}
    sk "PLATE#01".."20"     {page, zone, hero, image, jpeg, regions, score, passed, problems, attempts}
    sk "META"               {ready, prepared_at}
  S3: stories/<story>/bible/<character>.png, stories/<story>/plates/<NN>.png and .jpg

They are made once, ahead of time, by prepare_story.py. A book only swaps its hero into them.
"""

import io
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

import ai
import stories
from storage import story_key

log = logging.getLogger("storybook.assets")

MAX_TRIES = 3


def pk(story_id):
    return f"STORY#{story_id}"


def jpeg(data: bytes, max_side: int = None, quality: int = 90) -> bytes:
    """JPEG bytes, at most max_side. A JPEG that's already small enough is returned untouched."""
    with ai.IMAGE_WORK:
        return _jpeg(data, max_side, quality)


def _jpeg(data, max_side, quality):
    img = Image.open(io.BytesIO(data))
    if img.format == "JPEG" and (not max_side or max(img.size) <= max_side):
        return data
    if img.format == "JPEG" and max_side:
        img.draft("RGB", (max_side, max_side))  # shrink while decoding: much less CPU
    img = img.convert("RGB")
    if max_side:
        img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def best_of(attempts):
    """Pick the attempt to keep: a passing one if any, else the highest score."""
    return max(attempts, key=lambda a: (a["check"].get("passed", False), a["check"].get("score", 0)))


def draw_checked(make, check, label, tries=MAX_TRIES, on_attempt=None, errors=None):
    """The quality loop: draw, inspect, and redraw on failure, up to `tries` drawings in total.
    Still not right after that? Keep the best of them. Returns (png, check, attempts_made)."""
    attempts = []
    for n in range(1, tries + 1):
        if on_attempt:
            on_attempt(n, "drawing")
        try:
            png = make()
        except Exception as e:  # noqa: BLE001
            log.error("draw_failed image=%s attempt=%s error=%s", label, n, str(e)[:200])
            if errors is not None:
                errors.append(str(e)[:300])
            continue
        if on_attempt:
            on_attempt(n, "checking")
        try:
            result = check(png)
        except Exception as e:  # noqa: BLE001 - an inspector failure shouldn't throw the image away
            log.error("check_failed image=%s attempt=%s error=%s", label, n, str(e)[:200])
            result = {"passed": False, "score": 0, "problems": ["could not be inspected"], "regions": []}
        attempts.append({"png": png, "check": result})
        log.info("image_checked image=%s attempt=%s passed=%s score=%s problems=%s", label, n,
                 result.get("passed"), result.get("score"), "; ".join(result.get("problems", []))[:200])
        if result.get("passed"):
            break
    if not attempts:
        return None, None, n
    best = best_of(attempts)
    return best["png"], best["check"], n  # n = drawings tried (a blocked or failed drawing still counts)


# ---------------------------------------------------------------------------
# Reading (used by the app while making books)
# ---------------------------------------------------------------------------
_cache = {}
_cache_lock = threading.Lock()


def story_ready(storage, story_id) -> bool:
    meta = storage.get_record(pk(story_id), "META")
    return bool(meta and meta.get("ready"))


def plate(storage, story_id, number) -> dict:
    """The plate record plus its JPEG bytes (cached in memory: every book uses the same 20)."""
    cache_key = (story_id, number)
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]
    rec = storage.get_record(pk(story_id), f"PLATE#{number:02d}")
    if not rec:
        raise RuntimeError(f"story {story_id} page {number} has not been prepared")
    rec = dict(rec)
    rec["jpeg_bytes"] = storage.get_blob(rec["jpeg"])
    with _cache_lock:
        _cache[cache_key] = rec
    return rec


def clear_cache():
    with _cache_lock:
        _cache.clear()


# ---------------------------------------------------------------------------
# Preparing (prepare_story.py)
# ---------------------------------------------------------------------------
def _save_bible(storage, story_id, key, description, png, check, attempts):
    image = story_key(story_id, f"bible/{key}.png")
    storage.put_blob(image, png)
    storage.put_blob(story_key(story_id, f"bible/{key}.jpg"), jpeg(png, 1024))
    storage.put_record(pk(story_id), f"BIBLE#{key}", {
        "name": key, "description": description, "image": image,
        "jpeg": story_key(story_id, f"bible/{key}.jpg"),
        "score": check.get("score", 0), "passed": bool(check.get("passed")),
        "problems": check.get("problems", []), "attempts": attempts, "made_at": int(time.time()), "fake": ai.FAKE,
    })


def prepare_bible(storage, story_id, only=None, quality="medium", workers=8, say=print):
    s = stories.get_story(story_id)
    jobs = {"hero": ("The hero (stand-in): " + s["standin"], [(stories.standin_prompt(s), ())])}
    for key, desc in s["bible"].items():
        options = [(p, ()) for p in stories.bible_prompts(s, key)]
        if key in s.get("sheet_from_scene", {}):
            # last resort: copy the character out of a scene that already passed the filter
            rec = storage.get_record(pk(story_id), f"PLATE#{s['sheet_from_scene'][key][0]:02d}")
            if rec:
                options.append((stories.sheet_from_scene_prompt(s, key), (("scene.jpg", storage.get_blob(rec["jpeg"]), "image/jpeg"),)))
        jobs[key] = (desc, options)
    if only:
        jobs = {k: v for k, v in jobs.items() if k in only}

    failed = []

    def one(key):
        desc, prompts = jobs[key]
        errors = []
        turn = {"i": 0}

        def make():
            # If the safety filter blocks this wording, the next attempt uses the next (plainer) one.
            prompt, refs = prompts[min(turn["i"], len(prompts) - 1)]
            try:
                return ai.draw(prompt, refs, quality=quality, label=f"{story_id} {key}")
            except Exception as e:
                if "moderation" in str(e) or "safety system" in str(e):
                    turn["i"] += 1
                    if turn["i"] < len(prompts):
                        last = turn["i"] == len(prompts) - 1 and prompts[-1][1]
                        say(f"  ...     {key}: blocked by the safety filter, " + ("copying her from a scene that passed" if last else f"trying wording {turn['i'] + 1} of {len(prompts)}"))
                raise

        what = "A prop design sheet: the object alone, no people." if key in stories.OBJECTS else "A character design sheet: one character only."
        png, check, n = draw_checked(
            make,
            lambda img: ai.inspect_page(img, f"{what} {desc} Plain grey background.", "", hero_note="This is a design sheet, not a story page."),
            f"{story_id}/bible/{key}", tries=MAX_TRIES + len(prompts) - 1, errors=errors)
        if png is None:
            failed.append(key)
            say(f"  FAILED  {key}: {errors[-1] if errors else 'unknown error'}")
            return
        _save_bible(storage, story_id, key, desc, png, check, n)
        say(f"  {'ok  ' if check.get('passed') else 'BEST'}  {key:12s} score {check.get('score')}  tries {n}  {'; '.join(check.get('problems', []))[:90]}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))
    return failed


def prepare_plates(storage, story_id, pages=None, quality="medium", workers=8, say=print):
    s = stories.get_story(story_id)
    bible = {}
    for key in ["hero"] + list(s["bible"]):
        rec = storage.get_record(pk(story_id), f"BIBLE#{key}")
        if not rec:
            raise SystemExit(f"Character '{key}' isn't prepared yet. Run the bible step first.")
        bible[key] = storage.get_blob(rec["jpeg"])

    todo = [p for p in s["pages"] if not pages or p["number"] in pages]
    failed = []

    def one(page):
        errors = []
        hero = stories.hero_appears(page)
        refs = ([("hero.jpg", bible["hero"], "image/jpeg")] if hero else [])
        refs += [(f"{c}.jpg", bible[c], "image/jpeg") for c in page["cast"]]
        prompt = stories.plate_prompt(s, page)
        cast_note = "Characters who should appear: " + "; ".join(s["bible"][c] for c in page["cast"]) if page["cast"] else ""
        png, check, n = draw_checked(
            lambda: ai.draw(prompt, refs, quality=quality, label=f"{story_id} page {page['number']}"),
            lambda img: ai.inspect_page(img, page["scene"], page["text"], bible["hero"] if hero else None, cast_note),
            f"{story_id}/plate/{page['number']:02d}", errors=errors)
        if png is None:
            failed.append(page["number"])
            say(f"  FAILED  page {page['number']:2d}: {errors[-1] if errors else 'unknown error'}")
            return
        num = f"{page['number']:02d}"
        storage.put_blob(story_key(story_id, f"plates/{num}.png"), png)
        storage.put_blob(story_key(story_id, f"plates/{num}.jpg"), jpeg(png, 1536, 92))
        storage.put_blob(story_key(story_id, f"plates/thumb-{num}.jpg"), jpeg(png, 360, 80))
        storage.put_record(pk(story_id), f"PLATE#{num}", {
            "page": page["number"], "zone": page["zone"], "hero": hero,
            "image": story_key(story_id, f"plates/{num}.png"), "jpeg": story_key(story_id, f"plates/{num}.jpg"),
            "thumb": story_key(story_id, f"plates/thumb-{num}.jpg"),
            "regions": check.get("regions", []), "zones": check.get("zones"), "score": check.get("score", 0), "passed": bool(check.get("passed")),
            "problems": check.get("problems", []), "attempts": n, "made_at": int(time.time()), "fake": ai.FAKE,
        })
        say(f"  {'ok  ' if check.get('passed') else 'BEST'}  page {page['number']:2d}  score {check.get('score')}  tries {n}  {'; '.join(check.get('problems', []))[:90]}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    return failed


def recheck_plates(storage, story_id, pages=None, workers=8, say=print):
    """Re-inspect existing scenes WITHOUT redrawing them (refreshes the clear text spots and boxes)."""
    s = stories.get_story(story_id)
    hero_rec = storage.get_record(pk(story_id), "BIBLE#hero")
    hero = storage.get_blob(hero_rec["jpeg"]) if hero_rec else None

    def one(page):
        num = f"{page['number']:02d}"
        rec = storage.get_record(pk(story_id), f"PLATE#{num}")
        if not rec:
            return
        img = storage.get_blob(rec["jpeg"])
        cast_note = "Characters who should appear: " + "; ".join(s["bible"][c] for c in page["cast"]) if page["cast"] else ""
        try:
            check = ai.inspect_page(img, page["scene"], page["text"], hero if rec.get("hero") else None, cast_note)
        except Exception as e:  # noqa: BLE001
            say(f"  FAILED  page {page['number']:2d}: {str(e)[:150]}")
            return
        rec.update(regions=check.get("regions", []), zones=check.get("zones"))
        storage.put_record(pk(story_id), f"PLATE#{num}", {k: v for k, v in rec.items() if k != "sk"})
        clear = [z for z, ok in (check.get("zones") or {}).items() if ok]
        say(f"  checked page {page['number']:2d}  clear text spots: {', '.join(clear) or 'none'}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, [p for p in s["pages"] if not pages or p["number"] in pages]))
    clear_cache()


def mark_ready(storage, story_id, say=print, failed=()) -> bool:
    """Ready only if every character and every scene exists, none failed this run, and none is a
    leftover test image (unless we're in test mode)."""
    s = stories.get_story(story_id)
    problems = [f"failed this run: {', '.join(map(str, failed))}"] if failed else []
    for key in ["hero"] + list(s["bible"]):
        rec = storage.get_record(pk(story_id), f"BIBLE#{key}")
        if not rec:
            problems.append(f"character '{key}' missing")
        elif rec.get("fake", False) != ai.FAKE:
            problems.append(f"character '{key}' is a {'test' if rec.get('fake') else 'real'} image")
    for p in s["pages"]:
        rec = storage.get_record(pk(story_id), f"PLATE#{p['number']:02d}")
        if not rec:
            problems.append(f"page {p['number']} missing")
        elif rec.get("fake", False) != ai.FAKE:
            problems.append(f"page {p['number']} is a {'test' if rec.get('fake') else 'real'} image")
    ready = not problems
    storage.put_record(pk(story_id), "META", {"ready": ready, "prepared_at": int(time.time())})
    say(f"{s['title']}: {'READY' if ready else 'NOT READY (books are blocked until fixed): ' + '; '.join(problems)}")
    clear_cache()
    return ready
