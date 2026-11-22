"""The PDFs: the book to download (24 pages), and the print files (inside pages and the one-piece cover)."""

import io

import pytest
from pypdf import PdfReader

from storybook.content import pdf, stories
from tests.conftest import jpeg

DETAILS = [("Age", "7"), ("Favorite color", "Green"), ("Favorite food", ""), ("Favorite animal", ""), ("About me", "")]


def pages_for(sid, name="Simcha"):
    s = stories.STORIES[sid]
    from storybook.content import layout
    out = []
    for p in s["pages"]:
        art = jpeg((120 + p["number"] * 5, 160, 140), (1024, 1536))
        out.append((art, layout.place_text(stories.page_text(s, p, name), [], p["zone"], art, None)))
    return out


@pytest.mark.parametrize("sid,name,title", [("jack", "Simcha", "Simcha and the Beanstalk"),
                                            ("red", "Meira", "Little Red Riding Hood, featuring Meira")])
def test_book_pdf(sid, name, title):
    data = pdf.build_story_pdf(stories.STORIES[sid], name, DETAILS, jpeg(), jpeg(), pages_for(sid, name))
    r = PdfReader(io.BytesIO(data))
    assert len(r.pages) == 24                       # cover, copyright, 20 pages, The End, About Me
    assert (float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height)) == (432, 648)
    assert r.metadata.title == title
    story_text = r.pages[2].extract_text()
    assert "{" not in story_text
    first = stories.page_text(stories.STORIES[sid], stories.STORIES[sid]["pages"][0], name).split()[0:4]
    assert story_text.count(" ".join(first)) == 1   # each sentence is real type, and only once


def test_cover_puts_the_title_where_the_picture_is_empty():
    jack = pdf.cover_spec(stories.STORIES["jack"], "Simcha")
    red = pdf.cover_spec(stories.STORIES["red"], "Meira")
    assert jack["where"] == "bottom" and jack["lines"][0]["text"] == "SIMCHA" and jack["ribbon"] is None
    assert red["where"] == "top" and red["ribbon"]["text"] == "FEATURING MEIRA"
    long = pdf.cover_spec(stories.STORIES["jack"], "Alexandria-Rose")
    for line in long["lines"]:
        width = pdf.pdfmetrics.stringWidth(line["text"], long["font"], line["size"])
        assert width <= pdf.W - 2 * pdf.COVER_MARGIN + 1


def test_print_interior_is_printable():
    out = pdf.build_print_interior(stories.STORIES["jack"], "Simcha", pages_for("jack"), "abc12345", 0)
    data, count = out if isinstance(out, tuple) else (out, None)
    r = PdfReader(io.BytesIO(data))
    assert len(r.pages) >= 24 and len(r.pages) % 2 == 0      # Lulu's hardcover minimum, even
    assert (float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height)) == (450, 666)  # with bleed


def test_print_cover_is_the_size_lulu_asked_for():
    out = pdf.build_print_cover(stories.STORIES["red"], "Meira", DETAILS, jpeg(), jpeg(), 1008, 774,
                                pages=pages_for("red", "Meira"))
    data = out[0] if isinstance(out, tuple) else out
    page = PdfReader(io.BytesIO(data)).pages[0]
    assert (float(page.mediabox.width), float(page.mediabox.height)) == (1008, 774)
