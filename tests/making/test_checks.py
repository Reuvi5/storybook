"""What the parent types is checked before anything is charged or printed."""

import pytest

from storybook.making import checks

GOOD_NAMES = ["Sarah", "José María", "Zoë O'Brien-Smith", "李明", "Yisroel", "Mary-Kate"]
BAD_NAMES = ["Stupid", "Big Loser", "asdf", "Test", "x", "Bob123", "aaaaa"]


@pytest.mark.parametrize("name", GOOD_NAMES)
def test_real_names_pass(name):
    assert "name" not in checks.rule_checks({"name": name})


@pytest.mark.parametrize("name", BAD_NAMES)
def test_fake_names_and_insults_are_rejected(name):
    assert "name" in checks.rule_checks({"name": name})


@pytest.mark.parametrize("field,value", [
    ("about", "Call me at 555-123-4567"),
    ("about", "We live at 12 Oak Street"),
    ("about", "see www.example.com"),
    ("favorite_animal", "stupid cat"),
])
def test_contact_details_and_unkind_words_are_rejected(field, value):
    assert field in checks.rule_checks({"name": "Sarah", field: value})


def test_age_must_be_a_number():
    assert "age" in checks.rule_checks({"name": "Sarah", "age": "old"})
    assert "age" not in checks.rule_checks({"name": "Sarah", "age": "7"})


def test_check_details_passes_a_normal_child_in_test_mode():
    assert checks.check_details({"name": "Sarah", "age": "7", "about": "Loves horses."}) == {}
