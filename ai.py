"""
Every call to OpenAI goes through here: drawing images, and inspecting them.

  draw(prompt, refs)      - one image. With reference images it's an edit (the model sees them);
                            without, a plain generation.
  inspect_page(...)       - a vision model checks a finished page and returns a score, a list of
                            problems, and boxes around every face, character and important object
                            (the layout uses the boxes to keep text off them).
  inspect_hero(...)       - checks the hero design against the uploaded photo.

FAKE_IMAGES=1 replaces all of it with placeholders, so the whole app can be tested for free.
"""

import base64
import hashlib
import io
import json
import logging
import os
import random
import time

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("storybook.ai")

IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
VISION_MODEL = os.environ.get("VISION_MODEL", "gpt-5-mini")
SIZE = "1024x1536"  # portrait, the same 2:3 shape as the book page
FAKE = os.environ.get("FAKE_IMAGES") == "1"

_client = None

# Picture processing (decode, shrink, encode) is memory-hungry. The 20 pages wait on OpenAI in parallel,
# but only this many may process pictures at the same moment, so memory stays small (Render: 512 MB).
import threading as _threading
IMAGE_WORK = _threading.BoundedSemaphore(int(os.environ.get("IMAGE_WORK_SLOTS", 3)))

# Prices in US dollars per 1M tokens (override in .env if OpenAI changes them).
#   gpt-image-2: text in $5, image in $8, image out $30   gpt-5-mini: in $0.25, out $2
PRICE = {
    "image_text_in": float(os.environ.get("PRICE_IMAGE_TEXT_IN", 5.00)),
    "image_image_in": float(os.environ.get("PRICE_IMAGE_IMAGE_IN", 8.00)),
    "image_out": float(os.environ.get("PRICE_IMAGE_OUT", 30.00)),
    "vision_in": float(os.environ.get("PRICE_VISION_IN", 0.25)),
    "vision_out": float(os.environ.get("PRICE_VISION_OUT", 2.00)),
}


class Meter:
    """Adds up what one book (or one setup run) costs in API calls. Thread-safe: pages run in parallel."""

    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.image_calls = self.analysis_calls = 0
        self.image_usd = self.analysis_usd = 0.0

    def add(self, kind, usd):
        with self.lock:
            if kind == "image":
                self.image_calls += 1
                self.image_usd += usd
            else:
                self.analysis_calls += 1
                self.analysis_usd += usd

    @property
    def usd(self):
        return self.image_usd + self.analysis_usd

    def take(self) -> dict:
        """What was spent since the last take(), so costs can be saved as the book goes (a crash then
        loses at most one stage's worth, not the whole book)."""
        with self.lock:
            now = self.summary()
            last = getattr(self, "_last", {k: 0 for k in now})
            self._last = now
            return {k: (round(now[k] - last[k], 5) if isinstance(now[k], float) else now[k] - last[k]) for k in now}

    def summary(self) -> dict:
        return {"usd": round(self.usd, 5), "image_usd": round(self.image_usd, 5), "analysis_usd": round(self.analysis_usd, 5),
                "image_calls": self.image_calls, "analysis_calls": self.analysis_calls}


def _get(obj, name, default=0):
    if obj is None:
        return default
    v = obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)
    return v if v is not None else default


def _image_cost(usage, refs, quality) -> float:
    """From the API's own token counts. If they're missing, estimate (output tokens from OpenAI's calculator)."""
    if usage is not None:
        details = _get(usage, "input_tokens_details", None)
        text_in, image_in = _get(details, "text_tokens"), _get(details, "image_tokens")
        if not (text_in or image_in):
            text_in = _get(usage, "input_tokens")
        out = _get(usage, "output_tokens")
        return (text_in * PRICE["image_text_in"] + image_in * PRICE["image_image_in"] + out * PRICE["image_out"]) / 1e6
    out = {"low": 158, "medium": 1372, "high": 5500}.get(quality, 158)
    return (500 * PRICE["image_text_in"] + 1500 * len(refs) * PRICE["image_image_in"] + out * PRICE["image_out"]) / 1e6


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(timeout=150, max_retries=2)  # max_retries covers rate limits (429) with backoff
    return _client


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def draw(prompt: str, refs=(), quality: str = "low", label: str = "", meter: Meter = None, fmt: str = "png") -> bytes:
    """refs: [(file name, bytes, mime)]. Returns image bytes (PNG, or JPEG with fmt="jpeg": book pages use
    JPEG so the server never has to decode and re-encode them). Adds its cost to `meter`."""
    if FAKE:
        if meter:
            meter.add("image", _image_cost(None, refs, quality))  # test mode: what it WOULD cost
        return _placeholder(label or prompt[:40], fmt)
    extra = {"output_format": "jpeg", "output_compression": 90} if fmt == "jpeg" else {}
    if refs:
        result = client().images.edit(model=IMAGE_MODEL, image=list(refs), prompt=prompt, size=SIZE, quality=quality, **extra)
    else:
        result = client().images.generate(model=IMAGE_MODEL, prompt=prompt, size=SIZE, quality=quality, **extra)
    if meter:
        meter.add("image", _image_cost(getattr(result, "usage", None), refs, quality))
    return base64.b64decode(result.data[0].b64_json)


def _placeholder(label: str, fmt: str = "png") -> bytes:
    time.sleep(random.uniform(1.5, 4))
    with IMAGE_WORK:
        return _draw_placeholder(label, fmt)


def _draw_placeholder(label, fmt):
    seed = int(hashlib.md5(label.encode()).hexdigest()[:6], 16)
    rnd = random.Random(seed)
    img = Image.new("RGB", (1024, 1536), (rnd.randint(90, 200), rnd.randint(110, 200), rnd.randint(90, 210)))
    d = ImageDraw.Draw(img)
    # a "character" with a face, somewhere in the middle band, so the layout has something to avoid
    cx, cy = rnd.randint(300, 724), rnd.randint(600, 900)
    d.rounded_rectangle((cx - 160, cy, cx + 160, cy + 520), 60, fill=(80, 60, 120))
    d.ellipse((cx - 110, cy - 230, cx + 110, cy + 10), fill=(240, 200, 170))
    try:
        font = ImageFont.load_default(size=48)
    except TypeError:
        font = ImageFont.load_default()
    d.text((512, 120), "TEST IMAGE", fill="white", anchor="mm", font=font)
    d.text((512, 180), label[:34], fill="white", anchor="mm", font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG" if fmt == "jpeg" else "PNG", **({"quality": 90} if fmt == "jpeg" else {}))
    return buf.getvalue()


def open_small(data: bytes, max_side: int):
    with IMAGE_WORK:
        return _open_small(data, max_side)


def _open_small(data: bytes, max_side: int):
    """Open an image already shrunk to about max_side. For JPEGs the decoder does the shrinking
    (draft mode), which is many times faster than decoding the full picture: it matters on a small server."""
    img = Image.open(io.BytesIO(data))
    if img.format == "JPEG":
        img.draft("RGB", (max_side, max_side))
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    return img


# ---------------------------------------------------------------------------
# Inspecting
# ---------------------------------------------------------------------------
def _data_url(png: bytes, max_side: int = 768, grid: bool = False) -> str:
    with IMAGE_WORK:
        img = _open_small(png, max_side)
        if grid:
            img = _with_grid(img)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        del img
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _with_grid(img):
    """Faint lines every 10% with their coordinate (0-1000), so boxes come back more accurate."""
    img = img.copy()
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    try:
        font = ImageFont.load_default(size=12)
    except TypeError:
        font = ImageFont.load_default()
    for i in range(1, 10):
        x, y = w * i / 10, h * i / 10
        d.line([(x, 0), (x, h)], fill=(255, 255, 255, 70), width=1)
        d.line([(0, y), (w, y)], fill=(255, 255, 255, 70), width=1)
        d.text((x + 2, 2), str(i * 100), fill=(255, 255, 255, 170), font=font)
        d.text((2, y + 2), str(i * 100), fill=(255, 255, 255, 170), font=font)
    return img


def _ask(instructions: str, images: list, meter: Meter = None) -> dict:
    content = [{"type": "text", "text": instructions}]
    content += [{"type": "image_url", "image_url": {"url": _data_url(b, grid=(i == 0)), "detail": "high"}}
                for i, b in enumerate(images)]
    kwargs = dict(model=VISION_MODEL, messages=[{"role": "user", "content": content}],
                  response_format={"type": "json_object"})
    try:
        resp = client().chat.completions.create(reasoning_effort="minimal", **kwargs)
    except Exception as e:  # noqa: BLE001 - some models don't take reasoning_effort
        if "reasoning" not in str(e).lower():
            raise
        resp = client().chat.completions.create(**kwargs)
    if meter:
        u = getattr(resp, "usage", None)
        meter.add("analysis", (_get(u, "prompt_tokens") * PRICE["vision_in"] + _get(u, "completion_tokens") * PRICE["vision_out"]) / 1e6)
    return json.loads(resp.choices[0].message.content)


ZONES = {  # where a text panel can go: (x0, y0, x1, y1) in 0-1000 image coordinates, from the TOP-LEFT
    "top": (0, 0, 1000, 280), "middle": (0, 360, 1000, 640), "bottom": (0, 720, 1000, 1000),
    "top_left": (0, 0, 540, 360), "top_right": (460, 0, 1000, 360),
    "bottom_left": (0, 640, 540, 1000), "bottom_right": (460, 640, 1000, 1000),
}
ZONE_RULES = """"text_zones": for each of these areas of image 1 (coordinates 0-1000 from the top-left; the
  faint grid on image 1 shows them), would a text box placed there cover any face, any part of a character's
  head or body, or anything the story needs the reader to see? Plain sky, walls, floor, ground, grass or
  blurry background is fine to cover.
    "top": y 0-280 full width, "middle": y 360-640 full width, "bottom": y 720-1000 full width,
    "top_left": x 0-540 y 0-360, "top_right": x 460-1000 y 0-360,
    "bottom_left": x 0-540 y 640-1000, "bottom_right": x 460-1000 y 640-1000
  Reply as {"top": {"clear": true/false, "would_cover": "what it would cover, or nothing"}, "middle": {...}, ...}
  for all seven. Be strict about faces and characters."""

REGION_RULES = """"regions": a list of boxes for everything the reader needs to see, so that no words are ever printed on top of them:
  - every face (a tight box around the head), kind "face"
  - every character's whole body, kind "character"
  - every object the page text mentions or the scene depends on (beans, basket, axe, harp, door...), kind "object"
  Each region is {"label": "...", "kind": "face" | "character" | "object", "box": [x0, y0, x1, y1]} in
  coordinates from 0 to 1000 across image 1's width (x) and height (y), measured from the TOP-LEFT corner.
  Boxes should be generous rather than tight, except faces."""


def inspect_page(page_png: bytes, scene: str, text: str, hero_png: bytes = None, cast_note: str = "",
                 hero_note: str = None, meter: Meter = None) -> dict:
    """Score a finished page. Returns {"score", "passed", "problems", "regions", ...}."""
    if FAKE:
        if meter:
            meter.add("analysis", 0.0015)
        return _fake_inspection(page_png)
    hero_part = (
        "Image 2 is the hero's official character design. The hero in image 1 must be the same character "
        "(same face, hair, skin tone, any head covering, outfit)."
        if hero_png else (hero_note or "The hero does not appear on this page.")
    )
    instructions = f"""You are a strict quality inspector for a children's picture book. Image 1 is one illustrated page.
{hero_part}

The scene that was asked for: {scene}
{cast_note}
The words that will be printed on this page: "{text}"

Inspect image 1 carefully and reply with JSON only:
{{
  "hero_present": true/false,
  "hero_matches_design": 0-10 (10 = clearly the same character as image 2; 0 if no hero is needed),
  "hero_face_clear": true/false (face visible, lit, large enough to recognize; true if no hero is needed),
  "scene_matches": 0-10 (does the picture show what the scene and the words describe, including any counts),
  "anatomy_ok": true/false (no extra or missing limbs or fingers, no melted or merged faces or bodies),
  "cartoon_style": true/false (the WHOLE image, every face included, is a stylized 3D animated cartoon with large
                   simplified cartoon eyes and smooth skin; false if any face looks photorealistic: realistic
                   eyes, skin texture or teeth),
  "has_written_text": true/false (any letters, words or numbers drawn in the image),
  "problems": ["short, specific problems, empty if none"],
  "score": 0-10 overall quality for a published picture book,
  {ZONE_RULES},
  {REGION_RULES}
}}"""
    images = [page_png] + ([hero_png] if hero_png else [])
    r = _ask(instructions, images, meter)
    hero_needed = hero_png is not None
    r["passed"] = bool(
        r.get("score", 0) >= 7
        and r.get("scene_matches", 0) >= 6
        and r.get("anatomy_ok", False)
        and r.get("cartoon_style", True)
        and not r.get("has_written_text", True)
        and (not hero_needed or (r.get("hero_present") and r.get("hero_face_clear") and r.get("hero_matches_design", 0) >= 7))
    )
    r["regions"] = _clean_regions(r.get("regions"))
    r["zones"] = _clean_zones(r.get("text_zones"))
    return r


def _clean_zones(zones) -> dict:
    """{"top": True, "middle": False, ...}: which text spots the inspector says are clear."""
    out = {}
    for name in ZONES:
        z = (zones or {}).get(name)
        if isinstance(z, dict):
            out[name] = bool(z.get("clear"))
        elif isinstance(z, bool):
            out[name] = z
    return out


def inspect_hero(hero_png: bytes, photo_jpg: bytes, meter: Meter = None) -> dict:
    """Is the hero design recognizably the person in the photo, and a usable design sheet?"""
    if FAKE:
        if meter:
            meter.add("analysis", 0.0015)
        r = _fake_inspection(hero_png)
        r["regions"] = [{"label": "hero face", "kind": "face", "box": [330, 80, 670, 420]},
                        {"label": "hero", "kind": "character", "box": [200, 60, 800, 1000]}]
        return r
    instructions = f"""You check character designs for a personalized picture book. Image 1 is a cartoon character
design. Image 2 is a photo of the real person it must be based on.

Reply with JSON only:
{{
  "same_person": 0-10 (10 = instantly recognizable as the person in the photo: face shape, eyes, nose, mouth, skin tone, hair, any head covering),
  "age_kept": true/false (looks about the same age as the person in the photo),
  "single_character": true/false (exactly one character, nobody else),
  "cartoon_style": true/false (a stylized 3D animated cartoon with large simplified cartoon eyes and smooth skin, not photorealistic),
  "face_clear": true/false,
  "anatomy_ok": true/false,
  "has_written_text": true/false,
  "problems": ["short, specific problems, empty if none"],
  "score": 0-10 overall,
  {REGION_RULES}
}}"""
    r = _ask(instructions, [hero_png, photo_jpg], meter)
    r["passed"] = bool(
        r.get("same_person", 0) >= 7 and r.get("score", 0) >= 7 and r.get("single_character", False)
        and r.get("cartoon_style", True)
        and r.get("face_clear", False) and r.get("anatomy_ok", False) and not r.get("has_written_text", True)
    )
    r["regions"] = _clean_regions(r.get("regions"))
    return r


def _clean_regions(regions) -> list:
    out = []
    for r in regions or []:
        try:
            x0, y0, x1, y1 = (max(0.0, min(1000.0, float(v))) for v in r["box"])
        except (KeyError, TypeError, ValueError):
            continue
        if x1 - x0 < 5 or y1 - y0 < 5:
            continue
        out.append({"label": str(r.get("label", ""))[:60], "kind": r.get("kind", "object"), "box": [x0, y0, x1, y1]})
    return out


def _fake_inspection(png: bytes) -> dict:
    """Test mode: find the placeholder's drawn "character" and pass most of the time."""
    time.sleep(random.uniform(0.3, 1.0))
    img = open_small(png, 150).resize((100, 150))
    px = img.load()
    xs, ys = [], []
    for y in range(150):
        for x in range(100):
            r, g, b = px[x, y]
            if (r, g, b) == (240, 200, 170) or (r, g, b) == (80, 60, 120):
                xs.append(x)
                ys.append(y)
    regions = []
    if xs:
        regions.append({"label": "character", "kind": "character",
                        "box": [min(xs) * 10, min(ys) * 1000 / 150, max(xs) * 10 + 10, max(ys) * 1000 / 150 + 7]})
    fail = os.environ.get("FAKE_FAIL_RATE")
    passed = random.random() >= float(fail) if fail else random.random() > 0.15
    zones = {}
    for name, (zx0, zy0, zx1, zy1) in ZONES.items():
        zones[name] = not any(r["box"][0] < zx1 and zx0 < r["box"][2] and r["box"][1] < zy1 and zy0 < r["box"][3] for r in regions)
    return {"score": 8 if passed else 5, "passed": passed,
            "problems": [] if passed else ["(test mode) pretend problem"], "regions": regions, "zones": zones}
