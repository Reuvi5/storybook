"""The page check's pass/fail rules (the AI's answers are faked, so no OpenAI call is made)."""

import pytest

from storybook.content import stories
from storybook.making import ai

GOOD = {"score": 9, "scene_matches": 8, "anatomy_ok": True, "extra_limbs": False, "hero_arms": 2,
        "hero_face_same": 9, "hero_build_same": 9, "hero_scale_ok": True, "must_ok": True,
        "hero_face_clear": True, "cartoon_style": True, "has_written_text": False, "hero_present": True,
        "hero_matches_design": 9}


@pytest.fixture
def answer(monkeypatch):
    """Make the page check see a given AI answer; returns a function that runs the check."""
    monkeypatch.setattr(ai, "FAKE", False)

    def run(must=None, **changes):
        monkeypatch.setattr(ai, "_ask", lambda *a, **k: {**GOOD, **changes})
        return ai.inspect_page(b"page", "a scene", "some text", b"hero", "", face_png=b"face", must=must)["passed"]
    return run


def test_a_good_page_passes(answer):
    assert answer()


@pytest.mark.parametrize("change", [
    {"hero_build_same": 5},       # the child got chubbier
    {"hero_face_same": 5},        # a look-alike, not the same child
    {"extra_limbs": True},        # three arms
    {"hero_arms": 3},
    {"hero_scale_ok": False},     # as tall as Mother
    {"anatomy_ok": False},
    {"score": 5},
    {"has_written_text": True},   # the AI drew lettering into the picture
])
def test_problems_fail_the_page(answer, change):
    assert not answer(**change)


def test_a_broken_page_rule_fails(answer):
    must = stories.must(stories.STORIES["jack"], stories.STORIES["jack"]["pages"][12])
    assert answer(must=must)
    assert not answer(must=must, must_ok=False)


def test_the_rule_and_the_body_check_are_in_the_question(monkeypatch):
    monkeypatch.setattr(ai, "FAKE", False)
    seen = {}

    def fake_ask(instructions, images, meter=None):
        seen["text"], seen["images"] = instructions, len(images)
        return GOOD
    monkeypatch.setattr(ai, "_ask", fake_ask)
    ai.inspect_page(b"p", "scene", "text", b"hero", "", face_png=b"face", must="The wolf leaps OUT.")
    assert "The wolf leaps OUT." in seen["text"]
    assert "hero_build_same" in seen["text"] and "IGNORE the expression" in seen["text"]
    assert seen["images"] == 3          # the page, the character sheet, the face close-up
