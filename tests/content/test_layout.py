"""Where the words go on a page: they fit, stay inside the print margin, and wrap evenly."""

import pytest

from storybook.content import layout, stories


@pytest.mark.parametrize("sid", list(stories.STORIES))
def test_every_page_fits_at_a_readable_size(sid):
    s = stories.STORIES[sid]
    for p in s["pages"]:
        lay = layout.place_text(stories.page_text(s, p, "Alexandria-Rose"), [], p["zone"], None, None)
        assert lay["mode"] == "overlay", p["number"]
        assert lay["size"] >= 14, (p["number"], lay["size"])


@pytest.mark.parametrize("sid", list(stories.STORIES))
def test_text_stays_inside_the_print_margin(sid):
    s = stories.STORIES[sid]
    m = layout.MARGIN
    for p in s["pages"]:
        x, y, w, h = layout.place_text(stories.page_text(s, p, "Simcha"), [], p["zone"], None, None)["rect"]
        assert x >= m - 0.5 and y >= m - 0.5, p["number"]
        assert x + w <= layout.W - m + 0.5 and y + h <= layout.H - m + 0.5, p["number"]


def test_lines_are_balanced():
    """No lonely last word: the wrap evens the lines out."""
    text = ("Once upon a time there was a child who always wore a bright red hooded cape, "
            "so everyone called them Little Red Riding Hood.")
    lines = layout._wrap(text, 18, 360)
    assert len(lines) >= 2
    assert len(lines[-1].split()) >= 2
    widths = [layout.stringWidth(line, layout.STORY_FONT, 18) for line in lines] if hasattr(layout, "stringWidth") else None
    if widths:
        assert max(widths) - min(widths) < 160
