"""
One-time setup: draw the character bible and the 20 scenes for each story, check them, and save
them to the database (the same AWS table and bucket the app uses, from .env).

Run from the storybook folder, with the venv on:

    python prepare_story.py all                  # both stories, everything (about 15-25 minutes)
    python prepare_story.py jack                 # just Jack and the Beanstalk
    python prepare_story.py red --pages 4,7      # redraw only pages 4 and 7 of Red Riding Hood
    python prepare_story.py jack --chars cow     # redraw one bible character (then redraw the pages it's in)
    python prepare_story.py jack --chars cow --pages 1,2,3   # both in one run
    python prepare_story.py all --sheet          # only rebuild the contact sheets for review
    python prepare_story.py red --recheck        # re-inspect the scenes (where text can go) without redrawing

Each run writes a contact sheet to prepared/<story>-sheet.jpg, and full-size copies of every image
to prepared/<story>/, so you can look at them.
Cost: roughly 70 images at medium quality, plus the checks. A few dollars in total, once.
"""

import argparse
import io
import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import assets  # noqa: E402
import stories  # noqa: E402
from storage import get_storage  # noqa: E402


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def contact_sheet(storage, story_id, out_dir="prepared"):
    """One big JPEG with every bible character and every scene, labeled with its score and problems."""
    s = stories.get_story(story_id)
    tiles = []
    for key in ["hero"] + list(s["bible"]):
        rec = storage.get_record(assets.pk(story_id), f"BIBLE#{key}")
        if rec:
            tiles.append((f"bible: {key}", rec, storage.get_blob(rec["jpeg"])))
    for p in s["pages"]:
        rec = storage.get_record(assets.pk(story_id), f"PLATE#{p['number']:02d}")
        if rec:
            tiles.append((f"page {p['number']} (text {p['zone']})", rec, storage.get_blob(rec["thumb"])))
    if not tiles:
        return None
    tw, th, cap = 240, 360, 70
    cols = 7
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + cap)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (label, rec, data) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + cap)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((tw, th))
        sheet.paste(img, (x, y))
        # protected regions, so you can see where text is not allowed
        for r in rec.get("regions", []):
            x0, y0, x1, y1 = r["box"]
            color = "red" if r["kind"] == "face" else ("orange" if r["kind"] == "character" else "deepskyblue")
            d.rectangle((x + x0 / 1000 * img.width, y + y0 / 1000 * img.height,
                         x + x1 / 1000 * img.width, y + y1 / 1000 * img.height), outline=color, width=2)
        clear = [z for z, v in (rec.get("zones") or {}).items() if v]
        if clear:
            d.text((x + 6, y + th + 54), "text ok: " + ", ".join(c.replace("_", "-") for c in clear)[:40], fill="navy", font=_font(12))
        ok = "ok" if rec.get("passed") else "BEST OF 3"
        d.text((x + 6, y + th + 4), f"{label}", fill="black", font=_font(15))
        d.text((x + 6, y + th + 22), f"{ok}  score {rec.get('score')}  tries {rec.get('attempts')}", fill="darkgreen" if rec.get("passed") else "darkred", font=_font(14))
        problems = "; ".join(rec.get("problems", []))[:60]
        d.text((x + 6, y + th + 40), problems, fill="gray", font=_font(12))
    os.makedirs(out_dir, exist_ok=True)
    # full-size copies too, one file per image, to look at closely
    full_dir = os.path.join(out_dir, story_id)
    os.makedirs(full_dir, exist_ok=True)
    for key in ["hero"] + list(s["bible"]):
        rec = storage.get_record(assets.pk(story_id), f"BIBLE#{key}")
        if rec:
            with open(os.path.join(full_dir, f"bible-{key}.jpg"), "wb") as f:
                f.write(storage.get_blob(rec["jpeg"]))
    for p in s["pages"]:
        rec = storage.get_record(assets.pk(story_id), f"PLATE#{p['number']:02d}")
        if rec:
            with open(os.path.join(full_dir, f"page-{p['number']:02d}.jpg"), "wb") as f:
                f.write(storage.get_blob(rec["jpeg"]))
    path = os.path.join(out_dir, f"{story_id}-sheet.jpg")
    sheet.save(path, quality=88)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story", choices=list(stories.STORIES) + ["all"])
    ap.add_argument("--pages", help="only these page numbers, e.g. 3,7,12")
    ap.add_argument("--chars", help="only these bible characters, e.g. cow,giant (hero = the stand-in)")
    ap.add_argument("--quality", default=os.environ.get("PLATE_QUALITY", "medium"), choices=["low", "medium", "high"])
    ap.add_argument("--workers", type=int, default=int(os.environ.get("IMAGE_CONCURRENCY", 8)))
    ap.add_argument("--sheet", action="store_true", help="only rebuild the contact sheets")
    ap.add_argument("--recheck", action="store_true", help="re-inspect existing scenes without redrawing them")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("FAKE_IMAGES") and not args.sheet:  # --recheck needs it too
        sys.exit("OPENAI_API_KEY is missing from .env")
    storage = get_storage()
    if storage.kind != "aws":
        print("NOTE: AWS isn't set in .env, so this only saves to the local_data folder (Render won't see it).")

    story_ids = list(stories.STORIES) if args.story == "all" else [args.story]
    pages = {int(x) for x in args.pages.split(",")} if args.pages else None
    chars = set(args.chars.split(",")) if args.chars else None

    for sid in story_ids:
        title = stories.get_story(sid)["title"]
        t = time.time()
        if args.recheck:
            print(f"\n{title}: re-inspecting scenes (no redrawing)")
            assets.recheck_plates(storage, sid, pages=pages, workers=args.workers)
        elif not args.sheet:
            failed = []
            if chars or not pages:
                print(f"\n{title}: character bible ({args.quality} quality)")
                failed += assets.prepare_bible(storage, sid, only=chars, quality=args.quality, workers=args.workers)
            if pages or not chars:
                print(f"\n{title}: scenes ({args.quality} quality)")
                failed += assets.prepare_plates(storage, sid, pages=pages, quality=args.quality, workers=args.workers)
            assets.mark_ready(storage, sid, failed=failed)
            print(f"{title}: took {time.time() - t:.0f} seconds")
        path = contact_sheet(storage, sid)
        if path:
            print(f"Contact sheet: {os.path.abspath(path)}")


if __name__ == "__main__":
    main()
