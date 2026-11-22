"""Lulu (test mode: no network). Quotes, print jobs, and the sandbox-only guard."""

import importlib

import pytest

from storybook.money import printing

ADDRESS = {"name": "Sample Parent", "street1": "700 Park Offices Dr", "street2": "", "city": "Durham",
           "state_code": "NC", "postcode": "27709", "country_code": "US", "phone_number": "9195550100",
           "email": "parent@example.com"}


def test_quote_adds_up():
    q = printing.quote(ADDRESS, 24)
    assert q["currency"] == "USD"
    parts = q["printing"] + q["shipping"] + q["fulfillment"] + q["tax"]
    assert abs(parts - q["total"]) < 0.02


def test_cover_size_for_a_24_page_hardcover():
    w, h = printing.cover_dimensions(24)
    assert (w, h) == (1008.0, 774.0)


def test_a_print_job_gets_an_id():
    job = printing.create_job(title="Simcha and the Beanstalk", interior_url="https://x/i.pdf",
                              cover_url="https://x/c.pdf", page_count=24, address=ADDRESS,
                              email="parent@example.com", external_id="o1")
    assert job["id"]


def test_only_the_sandbox_is_allowed(monkeypatch):
    monkeypatch.setenv("FAKE_PRINT", "0")                 # the guard matters when talking to the real Lulu
    monkeypatch.setenv("LULU_API_BASE", "https://api.lulu.com")
    try:
        with pytest.raises(RuntimeError):
            importlib.reload(printing)
    finally:
        monkeypatch.setenv("FAKE_PRINT", "1")
        monkeypatch.setenv("LULU_API_BASE", "")
        importlib.reload(printing)
    assert "sandbox" in printing.BASE and printing.FAKE


def test_an_empty_setting_means_the_sandbox():
    assert printing.BASE == "https://api.sandbox.lulu.com"
