"""
Builds the downloadable PDF.

Pages, in order:
  - Cover: Jack's character, with the title and "starring <name>"
  - The story pages: full-bleed art with the story text drawn on top
  - About Me: the uploaded photo next to the cartoon, the child's name, and the
    details the uploader typed in

All text is drawn here, never by the image model, so it is always readable.
"""

import hashlib
import io
import os
import tempfile
import threading

from PIL import Image
from reportlab import rl_config
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

import story

# 6 x 9 inch pages: the same 2:3 shape as the 1024x1536 images, so art fills the page exactly.
W, H = 432, 648

STORY_FONT = "Times-Bold"
BODY_FONT = "Helvetica"
BODY_BOLD = "Helvetica-Bold"

THEMES = {
    # panel color (with transparency), text color
    "light": (Color(1, 0.98, 0.94, alpha=0.82), Color(0.23, 0.15, 0.08)),
    "dark": (Color(0.05, 0.04, 0.08, alpha=0.55), Color(1, 0.96, 0.86)),
}


# Store pictures as binary in the PDF. reportlab's default (ASCII85 text encoding) runs in plain Python
# when its C speedups aren't installed: minutes per book on a small server.
rl_config.useA85 = 0

_tmp = threading.local()


def _jpeg(png_bytes: bytes):
    """What to hand reportlab for one picture.

    A JPEG goes in as a FILE PATH: that's the only way reportlab embeds the JPEG data as it is. Given
    bytes or a PIL image, it decodes every picture into raw pixels (about 5 MB each) and zip-compresses
    them, which took minutes and ran out of memory on Render's small server."""
    if png_bytes[:3] != b"\xff\xd8\xff":  # a PNG (older books): convert once
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        png_bytes = buf.getvalue()
    folder = getattr(_tmp, "dir", None)
    if folder is None:  # not inside a build: fall back to the slow way
        return ImageReader(io.BytesIO(png_bytes))
    path = os.path.join(folder, hashlib.sha1(png_bytes).hexdigest() + ".jpg")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(png_bytes)
    return path


def _old_jpeg(png_bytes: bytes) -> ImageReader:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    buf.seek(0)
    return ImageReader(buf)


def _text_panel(c, lines_spec, area: str, theme: str):
    """Draw a rounded, see-through panel with centered text in the top or bottom of the page.

    lines_spec: list of (text, font, size) blocks, drawn top to bottom."""
    panel_color, text_color = THEMES[theme]
    margin, pad = 22, 16
    max_width = W - 2 * margin - 2 * pad

    # Wrap every block and work out the panel height.
    wrapped = []
    for text, font, size in lines_spec:
        for line in simpleSplit(text, font, size, max_width):
            wrapped.append((line, font, size, size * 1.3))
    height = sum(leading for *_, leading in wrapped) + 2 * pad

    y0 = 28 if area == "bottom" else H - 28 - height
    c.setFillColor(panel_color)
    c.roundRect(margin, y0, W - 2 * margin, height, 14, stroke=0, fill=1)

    c.setFillColor(text_color)
    y = y0 + height - pad
    for line, font, size, leading in wrapped:
        y -= leading
        c.setFont(font, size)
        c.drawCentredString(W / 2, y + (leading - size) * 0.6, line)


def _cover(c, name: str, character: bytes):
    c.drawImage(_jpeg(character), 0, 0, W, H)
    # Jack's face is in the upper part of the character image, so the title goes at the bottom.
    _text_panel(
        c,
        [(story.BOOK_TITLE, STORY_FONT, 30), (f"starring {name}", "Times-Italic", 20)],
        area="bottom",
        theme="light",
    )
    c.showPage()


def _story_page(c, page: dict, art: bytes):
    c.drawImage(_jpeg(art), 0, 0, W, H)
    _text_panel(c, [(page["text"], STORY_FONT, 22)], area=page["text_area"], theme=page["theme"])
    c.showPage()


def _framed_image(c, image_bytes: bytes, box_x: float, box_y: float, box_w: float, box_h: float, ink):
    """Draw an image as large as fits in the box, keeping its shape, bottom-centered, with a frame."""
    w, h = Image.open(io.BytesIO(image_bytes)).size
    scale = min(box_w / w, box_h / h)
    dw, dh = w * scale, h * scale
    x, y = box_x + (box_w - dw) / 2, box_y
    c.drawImage(_jpeg(image_bytes), x, y, dw, dh)
    c.setStrokeColor(ink)
    c.setLineWidth(1.5)
    c.rect(x, y, dw, dh, stroke=1, fill=0)


def _about_me(c, name: str, details: list, character: bytes, photo: bytes = None):
    # Warm paper background
    c.setFillColor(Color(0.99, 0.96, 0.89))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    ink = Color(0.23, 0.15, 0.08)

    c.setFillColor(ink)
    c.setFont(STORY_FONT, 34)
    c.drawCentredString(W / 2, H - 58, "About Me")

    box_h = 200
    box_y = H - 80 - box_h
    if photo:
        # The real photo and the cartoon side by side, so they can be compared.
        box_w, gap = 160, 24
        left_x = (W - 2 * box_w - gap) / 2
        right_x = left_x + box_w + gap
        _framed_image(c, photo, left_x, box_y, box_w, box_h, ink)
        _framed_image(c, character, right_x, box_y, box_w, box_h, ink)
        c.setFillColor(ink)
        c.setFont("Times-Italic", 13)
        c.drawCentredString(left_x + box_w / 2, box_y - 16, "Real me")
        c.drawCentredString(right_x + box_w / 2, box_y - 16, "Cartoon me")
        y = box_y - 46
    else:
        # Older books without a saved photo: just the cartoon.
        _framed_image(c, character, (W - box_h * 2 / 3) / 2, box_y, box_h * 2 / 3, box_h, ink)
        y = box_y - 34

    c.setFillColor(ink)
    c.setFont(STORY_FONT, 26)
    c.drawCentredString(W / 2, y, name)
    y -= 30

    left = 54
    max_width = W - 2 * left
    for label, value in details:
        if not value:
            continue
        if label == "About me":
            y -= 8
            c.setFont(BODY_BOLD, 13)
            c.drawString(left, y, "About me")
            y -= 18
            c.setFont(BODY_FONT, 12.5)
            for line in simpleSplit(value, BODY_FONT, 12.5, max_width):
                if y < 36:  # out of room on the page
                    break
                c.drawString(left, y, line)
                y -= 17
        else:
            c.setFont(BODY_BOLD, 13)
            c.drawString(left, y, f"{label}:")
            label_width = c.stringWidth(f"{label}: ", BODY_BOLD, 13)
            c.setFont(BODY_FONT, 13)
            c.drawString(left + label_width, y, value)
            y -= 20
    c.showPage()


class _jpeg_folder:
    """Temporary folder for the JPEG files of one PDF build (deleted afterwards)."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        _tmp.dir = self.tmp.name

    def __exit__(self, *exc):
        _tmp.dir = None
        self.tmp.cleanup()


def build_pdf(name: str, details: list, images: dict) -> bytes:
    with _jpeg_folder():
        return _build_pdf(name, details, images)


def _build_pdf(name: str, details: list, images: dict) -> bytes:
    """Version 1 books (3 pages, made before the 20-page template). Kept so old books still download.
    name: the child's name. details: [(label, value)]. images: {"character": png, 1: png, 2: png, ...}"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"{story.BOOK_TITLE}, starring {name}")

    _cover(c, name, images["character"])
    for page in story.PAGES:
        _story_page(c, page, images[page["number"]])
    _about_me(c, name, details, images["character"], images.get("photo"))

    c.save()
    return buf.getvalue()


# ===========================================================================
# Version 2: the 20-page template (template.py), shared by both stories
# ===========================================================================
import template as T  # noqa: E402

PAPER = Color(0.99, 0.96, 0.89)
INK = Color(0.23, 0.15, 0.08)
COVER_COLORS = {"jack": Color(0.18, 0.36, 0.22), "red": Color(0.55, 0.12, 0.12)}
PANEL = {
    "light": (Color(1, 0.98, 0.94, alpha=0.88), INK),
    "dark": (Color(0.06, 0.05, 0.09, alpha=0.62), Color(1, 0.96, 0.86)),
    "paper": (PAPER, INK),
}


PUBLISHER = os.environ.get("PUBLISHER", "Kupchik Games")
PUBLISHER_URL = os.environ.get("PUBLISHER_URL", "storybook.kupchikgames.shop")


# The words sit on the picture itself, like a printed picture book: no box. Behind them is a soft, feathered
# patch of light (or shade, on dark art) that fades into the picture, and a faint glow around the letters.
# The layout already puts the words on the plainest part of the page, so this is enough to read them easily.
GLOW = {
    "light": ((255, 250, 240), 0.70, Color(1, 0.98, 0.94)),   # wash color, wash strength, (unused)
    "dark": ((14, 12, 22), 0.56, Color(0.06, 0.05, 0.09)),
}
_wash_cache = {}


def _wash(theme, w, h):
    """A soft-edged patch (RGBA PNG) for behind the words: full strength in the middle, fading to nothing."""
    key = (theme, round(w / h, 1))
    if key not in _wash_cache:
        from PIL import Image, ImageDraw, ImageFilter
        rgb, strength, _ = GLOW[theme]
        px_w = 320
        px_h = max(40, int(px_w * h / w))
        feather = int(min(px_w, px_h) * 0.22)
        alpha = Image.new("L", (px_w, px_h), 0)
        ImageDraw.Draw(alpha).rounded_rectangle([feather, feather, px_w - feather, px_h - feather],
                                                radius=feather, fill=int(255 * strength))
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather * 0.55))
        img = Image.new("RGBA", (px_w, px_h), rgb + (0,))
        img.putalpha(alpha)
        _wash_cache[key] = ImageReader(img)
    return _wash_cache[key]


def _draw_text(c, layout):
    _, ink = PANEL[layout["theme"]]
    x, y, w, h = layout["rect"]
    size = layout["size"]
    leading = size * T.LEADING
    lines = []
    ty = y + h - T.PAD
    for line in layout["lines"]:
        ty -= leading
        lines.append((line, ty + (leading - size) * 0.62))
    glow = GLOW.get(layout["theme"]) if layout["mode"] == "overlay" else None
    if glow:
        # the soft patch runs a little past the text block, so its fading edge is outside the words
        grow_x, grow_y = w * 0.10, h * 0.35
        c.drawImage(_wash(layout["theme"], w + 2 * grow_x, h + 2 * grow_y), x - grow_x, y - grow_y,
                    w + 2 * grow_x, h + 2 * grow_y, mask="auto")
    c.setFillColor(ink)
    c.setFont(T.STORY_FONT, size)
    for line, ly in lines:
        c.drawCentredString(x + w / 2, ly, line)


def _fill(c, color, bleed=0):
    """Fill the whole page, including the bleed (print) area."""
    c.setFillColor(color)
    c.rect(-bleed, -bleed, W + 2 * bleed, H + 2 * bleed, stroke=0, fill=1)


def _full_art(c, art, bleed=0):
    """Art filling the page; with bleed it runs past the trim edge (scaled up a few %, centered)."""
    w = W + 2 * bleed
    h = w * 1.5  # the art is 2:3
    if h < H + 2 * bleed:
        h = H + 2 * bleed
        w = h / 1.5
    c.drawImage(_jpeg(art), (W - w) / 2, (H - h) / 2, w, h)


def _story_page_v2(c, art_png, layout, bleed=0):
    """Everything is drawn in trim coordinates (0..W, 0..H); the caller moves the origin for print."""
    if layout["mode"] == "band":
        _fill(c, PAPER, bleed)
        ax, ay, aw, ah = layout["art_rect"]
        c.drawImage(_jpeg(art_png), ax, ay, aw, ah)
    else:
        _full_art(c, art_png, bleed)
    _draw_text(c, layout)  # the only text on the page (no page numbers: they could land on a face)


def full_title(story, name):
    """"Simcha and the Beanstalk" / "Little Red Riding Hood, featuring Meira"."""
    import stories
    title = stories.book_title(story, name)
    return title if story.get("title_with_name") else f"{title}, featuring {name}"


def copyright_lines(story, name, book_id, made_at):
    import stories
    import time as _t
    year = _t.strftime("%Y", _t.gmtime(made_at))
    month = _t.strftime("%B %Y", _t.gmtime(made_at))
    title = stories.book_title(story, name)
    sub = "" if story.get("title_with_name") else f"featuring {name}"
    return [
        ("title", title),
        ("italic", sub),
        ("gap", ""),
        ("body", f"Text and illustrations copyright \u00a9 {year} {PUBLISHER}."),
        ("body", "All rights reserved. No part of this book may be reproduced"),
        ("body", "in any form without written permission from the publisher."),
        ("gap", ""),
        ("bold", f"Published by {PUBLISHER}"),
        ("body", PUBLISHER_URL),
        ("gap", ""),
        ("body", "Adapted from the traditional folk tale."),
        ("body", f"Illustrated with AI from a photo of {name}."),
        ("gap", ""),
        ("body", f"First edition, {month}"),
        ("small", f"Book {book_id[:8]}"),
    ]


def _copyright_page(c, story, name, book_id, made_at, bleed=0):
    """The inside page: copyright notice and publisher. The story starts on the next page."""
    _fill(c, PAPER, bleed)
    c.setFillColor(INK)
    fonts = {"title": (STORY_FONT, 15, 20), "italic": ("Times-Italic", 12, 18), "body": (BODY_FONT, 9, 12.5),
             "bold": (BODY_BOLD, 9, 12.5), "small": (BODY_FONT, 7.5, 11), "gap": (BODY_FONT, 9, 9)}
    lines = copyright_lines(story, name, book_id, made_at)
    total = sum(fonts[k][2] for k, _ in lines)
    y = 72 + total  # set low on the page, like a real copyright page
    for kind, text in lines:
        font, size, lead = fonts[kind]
        y -= lead
        if text:
            c.setFont(font, size)
            c.drawCentredString(W / 2, y, text)


def _the_end_page(c, story, name, bleed=0):
    _fill(c, PAPER, bleed)
    c.setFillColor(INK)
    c.setFont(STORY_FONT, 44)
    c.drawCentredString(W / 2, H / 2 + 10, "The End")
    c.setFont("Times-Italic", 16)
    if not story.get("title_with_name"):
        c.drawCentredString(W / 2, H / 2 - 22, f"featuring {name}")


# ---- The front cover --------------------------------------------------------------------------------
# The book's own most exciting page (Jack climbing the beanstalk, Red Riding Hood with the wolf), full
# bleed, with a big playful title in the band that picture leaves empty for words, so it never covers a
# face. Jack's book is named after the child ("SIMCHA and the Beanstalk"); Red Riding Hood keeps her
# title with a "FEATURING MEIRA" ribbon. cover_spec() is shared by the PDF, the print cover and the web.
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
TITLE_FONT = STORY_FONT
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("Fredoka-Bold", os.path.join(FONT_DIR, "Fredoka-Bold.ttf")))
    TITLE_FONT = "Fredoka-Bold"
except Exception:  # noqa: BLE001 - the cover still works in Times
    pass

SUN, CREAM, NAVY = "#ffc845", "#fff7e6", "#1b1f4a"
COVER_MARGIN = 42.0  # inside the 0.5 inch print safety margin


def _fit(text, font, size, width):
    while size > 14 and pdfmetrics.stringWidth(text, font, size) > width:
        size -= 1
    return size


def cover_spec(story: dict, name: str) -> dict:
    import stories
    n = stories.SHOWCASE.get(story["id"])
    zone = story["pages"][n - 1].get("zone", "top") if n else "top"
    where = "bottom" if zone.startswith("bottom") else "top"
    width = W - 2 * COVER_MARGIN
    lines = []
    if story.get("title_with_name"):
        rest = story["title_with_name"].replace("{name}", "").strip()
        lines.append({"text": name.upper(), "size": _fit(name.upper(), TITLE_FONT, 66, width), "color": SUN})
        lines.append({"text": rest, "size": _fit(rest, TITLE_FONT, 36, width), "color": CREAM})
        ribbon = None
    else:
        for part in simpleSplit(story["title"], TITLE_FONT, 50, width):
            lines.append({"text": part, "size": _fit(part, TITLE_FONT, 50, width), "color": CREAM})
        rt = f"FEATURING {name.upper()}"
        rsize = _fit(rt, TITLE_FONT, 16, width - 40)
        ribbon = {"text": rt, "size": rsize, "h": rsize * 2.1,
                  "w": pdfmetrics.stringWidth(rt, TITLE_FONT, rsize) + 2.2 * (len(rt) - 1) + rsize * 2.4}
    block = sum(l["size"] * 1.02 for l in lines) + (ribbon["h"] + 12 if ribbon else 0)
    top = H - COVER_MARGIN if where == "top" else COVER_MARGIN + block
    y = top
    for l in lines:
        y -= l["size"] * 1.02
        l["y"] = y + l["size"] * 0.18          # baseline
    if ribbon:
        y -= 12 + ribbon["h"]
        ribbon["y"] = y
        ribbon["x"] = (W - ribbon["w"]) / 2
    shade = [H - block - COVER_MARGIN - 70, H] if where == "top" else [0, block + COVER_MARGIN + 70]
    return {"page": n, "where": where, "lines": lines, "ribbon": ribbon, "shade": shade, "font": TITLE_FONT}


_shade_cache = {}


def _shade(where):
    """A vertical gradient (RGBA PNG): dark at the cover's edge, fading out, so the title pops off the art."""
    if where not in _shade_cache:
        img = Image.new("RGBA", (4, 256), (16, 18, 48, 0))
        px = img.load()
        for yy in range(256):
            t = yy / 255 if where == "bottom" else 1 - yy / 255   # 1 at the outer edge
            a = int(150 * (t ** 1.6))
            for xx in range(4):
                px[xx, yy] = (16, 18, 48, a)
        _shade_cache[where] = ImageReader(img)
    return _shade_cache[where]


def _outlined(c, text, x_center, y, font, size, fill, char_space=0.0):
    """Big storybook title text: soft shadow, thick dark outline, bright fill."""
    w = pdfmetrics.stringWidth(text, font, size) + char_space * (len(text) - 1)
    x = x_center - w / 2

    def put(mode, dx=0, dy=0):
        # each pass in its own graphics state: a PDF's text render mode otherwise carries over to the next text
        c.saveState()
        t = c.beginText()
        t.setTextRenderMode(mode)
        t.setFont(font, size)
        t.setCharSpace(char_space)
        t.setTextOrigin(x + dx, y + dy)
        t.textOut(text)
        c.drawText(t)
        c.restoreState()

    c.saveState()
    c.setLineJoin(1)
    c.setFillColor(Color(0.04, 0.05, 0.15, alpha=0.45))
    c.setStrokeColor(Color(0.04, 0.05, 0.15, alpha=0.45))
    c.setLineWidth(size * 0.16)
    put(2, size * 0.04, -size * 0.07)       # shadow
    c.setStrokeColor(_hex(NAVY))
    c.setLineWidth(size * 0.16)
    put(1)                                  # outline
    c.setFillColor(_hex(fill))
    put(0)                                  # fill
    c.restoreState()


def _hex(h):
    h = h.lstrip("#")
    return Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def _front_cover(c, story, name, hero_png, cover_art=None, background=True, bleed=(0, 0, 0, 0)):
    """bleed = (left, bottom, right, top): how far the art runs past the trim (print cover: into the wrap)."""
    spec = cover_spec(story, name)
    bl, bb, br, bt = bleed
    if cover_art:
        aw, ah = W + bl + br, H + bb + bt
        w, h = aw, aw * 1.5
        if h < ah:
            h, w = ah, ah / 1.5
        cx, cy = -bl + aw / 2, -bb + ah / 2
        c.saveState()
        p = c.beginPath()
        p.rect(-bl, -bb, aw, ah)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(_jpeg(cover_art), cx - w / 2, cy - h / 2, w, h)
        c.restoreState()
    else:  # no finished page to use: the character, framed, on the story's color
        c.setFillColor(COVER_COLORS.get(story["id"], INK))
        c.rect(-bl, -bb, W + bl + br, H + bb + bt, stroke=0, fill=1)
        bh = 360
        bw = bh * 2 / 3
        by = 70 if spec["where"] == "top" else H - 70 - bh
        c.setFillColor(_hex(CREAM))
        c.roundRect((W - bw) / 2 - 6, by - 6, bw + 12, bh + 12, 10, stroke=0, fill=1)
        c.drawImage(_jpeg(hero_png), (W - bw) / 2, by, bw, bh)
    y0, y1 = spec["shade"]
    if spec["where"] == "top":
        y1 += bt
    else:
        y0 -= bb
    c.drawImage(_shade(spec["where"]), -bl, y0, W + bl + br, y1 - y0, mask="auto")
    for l in spec["lines"]:
        _outlined(c, l["text"], W / 2, l["y"], spec["font"], l["size"], l["color"], char_space=l["size"] * 0.01)
    r = spec["ribbon"]
    if r:
        c.saveState()
        c.setFillColor(Color(0.04, 0.05, 0.15, alpha=0.35))
        c.roundRect(r["x"] + 2, r["y"] - 3, r["w"], r["h"], r["h"] / 2, stroke=0, fill=1)
        c.setFillColor(_hex(SUN))
        c.setStrokeColor(_hex(NAVY))
        c.setLineWidth(2.2)
        c.roundRect(r["x"], r["y"], r["w"], r["h"], r["h"] / 2, stroke=1, fill=1)
        c.setFillColor(_hex(NAVY))
        t = c.beginText()
        t.setFont(spec["font"], r["size"])
        t.setCharSpace(2.2)
        tw = pdfmetrics.stringWidth(r["text"], spec["font"], r["size"]) + 2.2 * (len(r["text"]) - 1)
        t.setTextOrigin(W / 2 - tw / 2, r["y"] + r["h"] / 2 - r["size"] * 0.36)
        t.textOut(r["text"])
        c.drawText(t)
        c.restoreState()


def _about_me_v2(c, name, details, hero_png, photo, background=True):
    """The back cover: About Me. Everything at least 0.5 inch inside the trim."""
    if background:
        _fill(c, PAPER)
    else:
        c.setFillColor(PAPER)
        c.roundRect(22, 22, W - 44, H - 44, 14, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont(STORY_FONT, 32)
    c.drawCentredString(W / 2, H - 70, "About Me")
    box_w, box_h, gap = 160, 228, 20
    top = H - 92
    lx = (W - 2 * box_w - gap) / 2
    rx = lx + box_w + gap
    _framed_image(c, photo, lx, top - box_h, box_w, box_h, INK)
    _framed_image(c, hero_png, rx, top - box_h, box_w, box_h, INK)
    c.setFillColor(INK)
    c.setFont("Times-Italic", 13)
    c.drawCentredString(lx + box_w / 2, top - box_h - 16, "Real me")
    c.drawCentredString(rx + box_w / 2, top - box_h - 16, "Cartoon me")
    y = top - box_h - 50
    c.setFont(STORY_FONT, 24)
    c.drawCentredString(W / 2, y, name)
    y -= 30
    left, max_width = 56, W - 112
    for label, value in details:
        if not value:
            continue
        if label == "About me":
            y -= 6
            c.setFont(BODY_BOLD, 12.5)
            c.drawString(left, y, "About me")
            y -= 17
            c.setFont(BODY_FONT, 12)
            for line in simpleSplit(value, BODY_FONT, 12, max_width):
                if y < 44:
                    break
                c.drawString(left, y, line)
                y -= 16
        else:
            c.setFont(BODY_BOLD, 12.5)
            c.drawString(left, y, f"{label}:")
            c.setFont(BODY_FONT, 12.5)
            c.drawString(left + c.stringWidth(f"{label}: ", BODY_BOLD, 12.5), y, value)
            y -= 19


def _cover_art(story, pages):
    """The finished picture of the story's showcase page, used full-bleed on the front cover."""
    import stories
    n = stories.SHOWCASE.get(story["id"])
    if pages and n and n <= len(pages):
        return pages[n - 1][0]
    return None


def build_story_pdf(story: dict, name: str, details: list, hero_png: bytes, photo: bytes, pages: list,
                    book_id: str = "00000000", made_at: int = 0) -> bytes:
    """The book to read on screen and download: front cover, copyright page, the 20 story pages,
    The End, and About Me as the back cover. pages: [(art, layout)] for the 20 story pages."""
    with _jpeg_folder():
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(W, H))
        c.setTitle(full_title(story, name))
        c.setAuthor(PUBLISHER)
        _front_cover(c, story, name, hero_png, _cover_art(story, pages)); c.showPage()
        _copyright_page(c, story, name, book_id, made_at); c.showPage()
        for art, layout in pages:
            _story_page_v2(c, art, layout); c.showPage()
        _the_end_page(c, story, name); c.showPage()
        _about_me_v2(c, name, details, hero_png, photo); c.showPage()
        c.save()
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Print files (Lulu): an interior PDF with bleed, and a one-piece cover
# ---------------------------------------------------------------------------
BLEED = 9.0                  # 0.125 inch on every side
PRINT_PAGE_MIN = 24          # hardcover minimum; the interior is padded with blank endpapers


def build_print_interior(story, name, pages, book_id, made_at) -> bytes:
    """6.25 x 9.25 in pages (6 x 9 trim + bleed): copyright, 20 story pages, The End, then blank
    pages to reach the printer's minimum (and an even count)."""
    with _jpeg_folder():
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(W + 2 * BLEED, H + 2 * BLEED))
        c.setTitle(full_title(story, name) + " (interior)")
        count = 0

        def page(draw):
            nonlocal count
            c.saveState()
            c.translate(BLEED, BLEED)
            draw()
            c.restoreState()
            c.showPage()
            count += 1

        page(lambda: _copyright_page(c, story, name, book_id, made_at, BLEED))
        for art, layout in pages:
            page(lambda art=art, layout=layout: _story_page_v2(c, art, layout, BLEED))
        page(lambda: _the_end_page(c, story, name, BLEED))
        while count < PRINT_PAGE_MIN or count % 2:
            page(lambda: _fill(c, PAPER, BLEED))  # endpaper
        c.save()
        return buf.getvalue(), count


def build_print_cover(story, name, details, hero_png, photo, width, height, pages=None) -> bytes:
    """One-piece cover: back cover (About Me) | spine | front cover, at the exact size the printer asks
    for (width x height in points, including bleed and the hardcover board wrap)."""
    wrap = (height - H) / 2                     # bleed + board wrap, equal on every outer edge
    spine = width - 2 * W - 2 * wrap
    color = COVER_COLORS.get(story["id"], INK)
    with _jpeg_folder():
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(width, height))
        c.setTitle(full_title(story, name) + " (cover)")
        c.setFillColor(color)
        c.rect(0, 0, width, height, stroke=0, fill=1)
        c.saveState()                           # back cover, left
        c.translate(wrap, wrap)
        _about_me_v2(c, name, details, hero_png, photo, background=False)
        c.restoreState()
        c.saveState()                           # front cover, right
        c.translate(wrap + W + spine, wrap)
        _front_cover(c, story, name, hero_png, _cover_art(story, pages), background=False, bleed=(0, wrap, wrap, wrap))
        c.restoreState()
        c.showPage()
        c.save()
        return buf.getvalue(), {"wrap": round(wrap, 2), "spine": round(spine, 2)}
