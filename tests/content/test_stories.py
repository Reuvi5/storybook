"""The two stories: 20 pages each, the child's name in the text, titles, expressions and page rules."""

import re

import pytest

from storybook.content import stories

STORY_IDS = list(stories.STORIES)
TOKENS = re.compile(r"\{\w+\}")


@pytest.mark.parametrize("sid", STORY_IDS)
def test_twenty_pages_in_order(sid):
    pages = stories.STORIES[sid]["pages"]
    assert [p["number"] for p in pages] == list(range(1, 21))
    for p in pages:
        assert p["text"].strip() and p["scene"].strip(), p["number"]
        assert p["zone"].split("_")[0] in ("top", "middle", "bottom"), p["number"]
        assert isinstance(p.get("cast", []), list)


@pytest.mark.parametrize("sid", STORY_IDS)
@pytest.mark.parametrize("name", ["Simcha", "Alexandria-Rose", "José", "李明"])
def test_page_text_has_no_placeholders_left(sid, name):
    s = stories.STORIES[sid]
    for p in s["pages"]:
        text = stories.page_text(s, p, name)
        assert not TOKENS.search(text), (p["number"], text)


def test_jack_story_uses_the_childs_name():
    s = stories.STORIES["jack"]
    texts = [stories.page_text(s, p, "Simcha") for p in s["pages"]]
    assert not any(re.search(r"\bJack\b", t) for t in texts)
    assert sum("Simcha" in t for t in texts) >= 12


def test_no_he_or_she_for_the_child():
    """The child is always "they" (or named): no boy/girl choice is asked for."""
    s = stories.STORIES["jack"]
    p1 = stories.page_text(s, s["pages"][0], "Simcha")
    assert p1.startswith("Once upon a time, Simcha lived with Mother")
    red = stories.STORIES["red"]
    assert "called them Little Red Riding Hood" in stories.page_text(red, red["pages"][0], "Meira")


def test_titles():
    jack, red = stories.STORIES["jack"], stories.STORIES["red"]
    assert stories.book_title(jack, "Simcha") == "Simcha and the Beanstalk"
    assert stories.book_subtitle(jack, "Simcha") == ""
    assert stories.book_title(red, "Meira") == "Little Red Riding Hood"
    assert stories.book_subtitle(red, "Meira") == "FEATURING MEIRA"


@pytest.mark.parametrize("sid", STORY_IDS)
def test_every_page_has_an_expression(sid):
    s = stories.STORIES[sid]
    assert len(stories.EXPRESSIONS[sid]) == 20
    for p in s["pages"]:
        assert stories.expression(s, p)


def test_page_rules_point_at_real_pages():
    for sid, rules in stories.MUST.items():
        for n in rules:
            assert 1 <= n <= 20, (sid, n)
    for sid, n in stories.SHOWCASE.items():
        assert 1 <= n <= 20
    for sid, ns in stories.SAMPLES.items():
        assert all(1 <= n <= 20 for n in ns)


def test_drawing_prompt_carries_the_page_rules():
    s = stories.STORIES["jack"]
    hiding = s["pages"][12]                       # story page 13: hidden in the pot
    prompt = stories.swap_prompt(s, hiding, head_hidden=True)
    assert "THIS PAGE MUST SHOW" in prompt and "copper pot" in prompt
    assert "blurred out on purpose" in prompt
    assert "EXPRESSION ON THIS PAGE" in prompt and "exactly TWO arms" in prompt
    plain = stories.swap_prompt(s, s["pages"][2])
    assert "THIS PAGE MUST SHOW" not in plain and "blurred out" not in plain


def test_wolf_leaves_through_the_window():
    red = stories.STORIES["red"]
    p17 = red["pages"][16]
    assert "OUT through the open window" in p17["scene"]
    assert "NOT coming in" in stories.must(red, p17)
