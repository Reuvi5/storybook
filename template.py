"""
The book template: one layout system for every page of both stories.

  Page:     6 x 9 inches (432 x 648 pt), the same 2:3 shape as the art, so art fills the page.
  Book:     cover, 20 story pages, About Me back page.
  Text:     always drawn by us (never by the image model), on a soft panel, in one of three slots:
            top, middle or bottom. Each story page asks for a slot (the scene was drawn to keep it
            empty), but the final choice is made from the finished picture: the panel may never
            cover a face, a character, or an object the page needs (regions found by the image
            inspector, padded). If no slot is clear at any allowed text size, the page switches to
            the "band" layout: the art is shrunk and the text gets its own strip below it, so text
            can never cover anything. That is the guarantee; the slots are the normal case.
"""

import io

from PIL import Image
from reportlab.lib.utils import simpleSplit

W, H = 432.0, 648.0                 # page size in points
MARGIN = 36.0                       # text stays 0.5 inch inside the trim (the printer's safety margin)
PAD = 13.0                          # space inside the panel around the text
REGION_PAD = 0.025                  # protected boxes grow by 2.5% of the page on every side
STORY_FONT = "Times-Bold"
FONT_SIZES = [18, 17, 16, 15, 14, 13, 12]   # largest first; never smaller than 12 pt
LEADING = 1.28
BAND_MIN = 0.16                     # in band layout, the text strip is at least 16% of the page


# Text spots, in image coordinates (0-1000 from the top-left); the inspector says which are clear.
ZONES = {
    "top": (0, 0, 1000, 250), "middle": (0, 375, 1000, 625), "bottom": (0, 750, 1000, 1000),
    "top_left": (0, 0, 540, 320), "top_right": (460, 0, 1000, 320),
    "bottom_left": (0, 680, 540, 1000), "bottom_right": (460, 680, 1000, 1000),
}
ORDER = {  # full-width spots first (the scene was drawn to leave the preferred one empty), then half-width
    "top": ["top", "bottom", "middle", "top_left", "top_right", "bottom_left", "bottom_right"],
    "bottom": ["bottom", "top", "middle", "bottom_left", "bottom_right", "top_left", "top_right"],
    "middle": ["middle", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right"],
}


def _wrap(text, size, width):
    lines = []
    for para in text.split("\n"):
        lines += simpleSplit(para, STORY_FONT, size, width)
    return lines


def _zone_page_rect(zone):
    """A zone (image coords, top-left origin) -> page rect (x0, y0, x1, y1), bottom-left origin."""
    x0, y0, x1, y1 = ZONES[zone]
    return (x0 / 1000 * W, H - y1 / 1000 * H, x1 / 1000 * W, H - y0 / 1000 * H)


def _panel(zone, text, size):
    """The text panel for this zone at this size, or None if it doesn't fit inside the zone."""
    zx0, zy0, zx1, zy1 = _zone_page_rect(zone)
    x0, x1 = max(zx0, MARGIN), min(zx1, W - MARGIN)
    lines = _wrap(text, size, x1 - x0 - 2 * PAD)
    h = len(lines) * size * LEADING + 2 * PAD
    top_edge, bottom_edge = zy1 - (MARGIN if zy1 >= H else 0), zy0 + (MARGIN if zy0 <= 0 else 0)
    if h > top_edge - bottom_edge:
        return None
    if zone.startswith("top"):
        y = top_edge - h
    elif zone.startswith("bottom"):
        y = bottom_edge
    else:
        y = (H - h) / 2
    return (x0, y, x1, y + h), lines


def _to_page(box):
    """Image box [x0, y0, x1, y1] (0-1000, origin top-left) -> page rect (x0, y0, x1, y1), origin bottom-left, padded."""
    x0, y0, x1, y1 = box
    px, py = REGION_PAD * W, REGION_PAD * H
    return (x0 / 1000 * W - px, H - y1 / 1000 * H - py, x1 / 1000 * W + px, H - y0 / 1000 * H + py)


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


PLAIN = 6.0    # busyness below this: plain wall, sky or ground: always fine for text
BUSY = 18.0    # busyness above this: people, faces, detail: never, whatever the inspector said


def busyness(art: bytes):
    """A function rect -> how busy the picture is there (average edge strength, 0-255), measured on a
    small copy. Plain areas measure about 1-5, characters and detailed scenery 15-40."""
    from PIL import ImageFilter
    import ai
    with ai.IMAGE_WORK:
        img = Image.open(io.BytesIO(art))
        if img.format == "JPEG":
            img.draft("L", (256, 384))
        edges = img.convert("L").resize((128, 192)).filter(ImageFilter.FIND_EDGES)
    w, h = edges.size

    def measure(rect):
        x0, y0, x1, y1 = rect  # page coordinates, origin bottom-left
        box = (int(x0 / W * w) + 1, int((H - y1) / H * h) + 1, int(x1 / W * w) - 1, int((H - y0) / H * h) - 1)
        if box[2] <= box[0] or box[3] <= box[1]:
            return 0.0
        px = edges.crop(box).histogram()
        return sum(i * n for i, n in enumerate(px)) / max(1, sum(px))
    return measure


def place_text(text: str, regions: list, preferred: str = "bottom", art_png: bytes = None, zones: dict = None) -> dict:
    """Decide where the page's text goes. Returns a JSON-safe layout spec:
       {"mode": "overlay", "slot", "rect": [x, y, w, h], "size", "lines", "theme", "busy"}  or
       {"mode": "band", "art_rect": [...], "rect": [...], "size", "lines", "theme": "paper"}

    Every spot is tried at the largest text size that fits it without touching a face (faces are never
    covered: a face box blocks any spot that isn't measurably plain). A spot is allowed if the picture is plain there (measured), or if the image
    inspector says it's clear and the picture isn't busy there. Of the allowed spots, the plainest wins,
    with a strong preference for the scene's planned spot, full-width panels and large text. If none is
    allowed, the plainest face-free full-width spot is used if it isn't busy; only if every spot is busy
    does the page switch to the band layout."""
    faces = [_to_page(r["box"]) for r in regions if r.get("kind") == "face"]
    measure = busyness(art_png) if art_png else (lambda rect: 0.0)
    order = ORDER.get(preferred, ORDER["bottom"])
    allowed, fallback = None, None
    for rank, zone in enumerate(order):
        for size in FONT_SIZES:
            placed = _panel(zone, text, size)
            if not placed:
                continue
            busy = measure(placed[0])
            # A face box blocks the spot, unless the picture there is measurably plain: a real face
            # (eyes, mouth, outlines) always measures busy, so a "face" in empty sky is a false box.
            if busy >= PLAIN and any(_overlaps(placed[0], f) for f in faces):
                continue
            half = "_" in zone
            # Lower is better: plain picture, the scene's planned spot, full width, big text.
            score = busy + 2.0 * rank + (8 if half else 0) - (size - FONT_SIZES[-1]) * 0.8
            # Without the inspector's answer (older data), measured plainness alone decides.
            said_clear = zones.get(zone, False) if zones is not None else True
            candidate = (score, zone, placed, size, busy)
            if busy < PLAIN or (said_clear and busy < BUSY):
                if allowed is None or score < allowed[0]:
                    allowed = candidate
            if not half and busy < BUSY and (fallback is None or busy < fallback[4]):
                fallback = candidate  # the plainest face-free full-width spot, in case nothing is allowed
            break  # the largest size that fits this spot is the one to judge
    best = allowed or fallback
    if best:
        _, zone, ((x0, y0, x1, y1), lines), size, busy = best
        return {"mode": "overlay", "slot": zone, "rect": [x0, y0, x1 - x0, y1 - y0], "size": size,
                "lines": lines, "theme": _theme(art_png, (x0, y0, x1, y1)), "busy": round(busy, 1)}
    # Nothing is clear: give the text its own strip under the art (rare).
    size = FONT_SIZES[2]
    lines = _wrap(text, size, W - 2 * MARGIN - 2 * PAD)
    height = len(lines) * size * LEADING + 2 * PAD
    band = max(height + 2 * MARGIN, BAND_MIN * H)
    art_h = H - band
    art_w = art_h * 2 / 3
    return {"mode": "band", "slot": "band", "art_rect": [(W - art_w) / 2, band, art_w, art_h],
            "rect": [MARGIN, (band - height) / 2, W - 2 * MARGIN, height],
            "size": size, "lines": lines, "theme": "paper"}


def _theme(art_png, rect):
    """Light panel with dark text over light art; dark panel with light text over dark art."""
    if not art_png:
        return "light"
    import ai
    with ai.IMAGE_WORK:
        return _theme_of(art_png, rect)


def _theme_of(art_png, rect):
    img = Image.open(io.BytesIO(art_png))
    if img.format == "JPEG":
        img.draft("L", (256, 384))
    img = img.convert("L")
    iw, ih = img.size
    x0, y0, x1, y1 = rect
    crop = img.crop((int(x0 / W * iw), int((H - y1) / H * ih), int(x1 / W * iw), int((H - y0) / H * ih)))
    pixels = list(crop.resize((40, 20)).getdata())
    return "light" if sum(pixels) / len(pixels) > 105 else "dark"


def check_layout(layout: dict, regions: list, zones: dict = None) -> bool:
    """True if the text panel is in a clear spot and touches no face (or, without zones, no region)."""
    if layout["mode"] == "band":
        return True
    x, y, w, h = layout["rect"]
    if zones is not None:
        if not zones.get(layout["slot"]):
            return False
        regions = [r for r in regions if r.get("kind") == "face"]
    return not any(_overlaps((x, y, x + w, y + h), _to_page(r["box"])) for r in regions)
