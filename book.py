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


def _draw_text(c, layout):
    panel, ink = PANEL[layout["theme"]]
    x, y, w, h = layout["rect"]
    if layout["mode"] == "overlay":
        c.setFillColor(panel)
        c.roundRect(x, y, w, h, 12, stroke=0, fill=1)
    c.setFillColor(ink)
    size = layout["size"]
    leading = size * T.LEADING
    c.setFont(T.STORY_FONT, size)
    ty = y + h - T.PAD
    for line in layout["lines"]:
        ty -= leading
        c.drawCentredString(x + w / 2, ty + (leading - size) * 0.62, line)


def _story_page_v2(c, art_png, layout, number):
    if layout["mode"] == "band":
        c.setFillColor(PAPER)
        c.rect(0, 0, W, H, stroke=0, fill=1)
        ax, ay, aw, ah = layout["art_rect"]
        c.drawImage(_jpeg(art_png), ax, ay, aw, ah)
    else:
        c.drawImage(_jpeg(art_png), 0, 0, W, H)
    _draw_text(c, layout)  # the only text on the page (no page numbers: they could land on a face)
    c.showPage()


def cover_geometry(title):
    """Where everything on the cover goes (shared by the PDF and the web preview)."""
    lines = simpleSplit(title, STORY_FONT, 34, W - 60)
    title_bottom = H - 64 - 40 * (len(lines) - 1)
    by = 62
    box_h = min(450, title_bottom - 18 - by - 12)
    box_w = box_h * 2 / 3
    return {"lines": lines, "box": [(W - box_w) / 2, by, box_w, box_h]}


def _cover_v2(c, title, name, hero_png, story_id):
    c.setFillColor(COVER_COLORS.get(story_id, INK))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    cream = Color(1, 0.96, 0.86)
    g = cover_geometry(title)
    c.setFillColor(cream)
    c.setFont(STORY_FONT, 34)
    for i, line in enumerate(g["lines"]):
        c.drawCentredString(W / 2, H - 64 - 40 * i, line)
    # the hero, framed, between the title and the name: no text ever sits on the art
    bx, by, bw, bh = g["box"]
    c.roundRect(bx - 6, by - 6, bw + 12, bh + 12, 10, stroke=0, fill=1)
    c.drawImage(_jpeg(hero_png), bx, by, bw, bh)
    c.setFillColor(cream)
    c.setFont("Times-Italic", 20)
    c.drawCentredString(W / 2, 30, f"starring {name}")
    c.showPage()


def _about_me_v2(c, name, details, hero_png, photo):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont(STORY_FONT, 32)
    c.drawCentredString(W / 2, H - 54, "About Me")
    box_w, box_h, gap = 176, 250, 20
    top = H - 78
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
    left, max_width = 54, W - 108
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
                if y < 30:
                    break
                c.drawString(left, y, line)
                y -= 16
        else:
            c.setFont(BODY_BOLD, 12.5)
            c.drawString(left, y, f"{label}:")
            c.setFont(BODY_FONT, 12.5)
            c.drawString(left + c.stringWidth(f"{label}: ", BODY_BOLD, 12.5), y, value)
            y -= 19
    c.showPage()


def build_story_pdf(story: dict, name: str, details: list, hero_png: bytes, photo: bytes, pages: list) -> bytes:
    """pages: [(art_png, layout)] for the 20 story pages, in order."""
    with _jpeg_folder():
        return _build_story_pdf(story, name, details, hero_png, photo, pages)


def _build_story_pdf(story, name, details, hero_png, photo, pages):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"{story['title']}, starring {name}")
    _cover_v2(c, story["title"], name, hero_png, story["id"])
    for i, (art, layout) in enumerate(pages, 1):
        _story_page_v2(c, art, layout, i)
    _about_me_v2(c, name, details, hero_png, photo)
    c.save()
    return buf.getvalue()
