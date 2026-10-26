"""
Builds the downloadable PDF.

Pages, in order:
  - Cover: Jack's character, with the title and "starring <name>"
  - The story pages: full-bleed art with the story text drawn on top
  - About Me: the child's name and the details the uploader typed in

All text is drawn here, never by the image model, so it is always readable.
"""

import io

from PIL import Image
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


def _jpeg(png_bytes: bytes) -> ImageReader:
    """Convert a PNG to JPEG before embedding, which keeps the PDF much smaller."""
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


def _about_me(c, name: str, details: list, character: bytes):
    # Warm paper background
    c.setFillColor(Color(0.99, 0.96, 0.89))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    ink = Color(0.23, 0.15, 0.08)

    c.setFillColor(ink)
    c.setFont(STORY_FONT, 34)
    c.drawCentredString(W / 2, H - 58, "About Me")

    # The character image, scaled down (2:3 shape), with a thin frame
    img_h = 210
    img_w = img_h * 2 / 3
    img_x, img_y = (W - img_w) / 2, H - 80 - img_h
    c.drawImage(_jpeg(character), img_x, img_y, img_w, img_h)
    c.setStrokeColor(ink)
    c.setLineWidth(1.5)
    c.rect(img_x, img_y, img_w, img_h, stroke=1, fill=0)

    y = img_y - 34
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


def build_pdf(name: str, details: list, images: dict) -> bytes:
    """name: the child's name. details: [(label, value)]. images: {"character": png, 1: png, 2: png, ...}"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"{story.BOOK_TITLE}, starring {name}")

    _cover(c, name, images["character"])
    for page in story.PAGES:
        _story_page(c, page, images[page["number"]])
    _about_me(c, name, details, images["character"])

    c.save()
    return buf.getvalue()
