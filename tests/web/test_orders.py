"""Ordering a printed copy: approve first, a valid US address, the charge, and the Orders page."""

import pytest

from storybook.money import ledger
from tests.conftest import add_funds

ADDRESS = {"name": "Sample Parent", "street1": "700 Park Offices Dr", "street2": "", "city": "Durham",
           "state_code": "NC", "postcode": "27709", "phone_number": "9195550100", "email": "parent@example.com"}


@pytest.fixture
def book(finished_book, prepared):
    c, uid, book_id = finished_book
    add_funds(prepared, uid, 5000)
    assert c.get(f"/book/{book_id}/print").status_code == 200     # builds the print files
    return c, uid, book_id


def approve(c, prepared, uid, book_id, tick=True):
    sha = prepared.get_book(uid, book_id)["print"]["interior_sha"][:12]
    data = {"fingerprint": sha, **({"approve": "yes"} if tick else {})}
    return c.post(f"/book/{book_id}/print/approve", data=data)


def test_cannot_order_before_approving(book, prepared):
    c, uid, book_id = book
    before = prepared.get_balance(uid)
    c.post(f"/book/{book_id}/print/order", data=ADDRESS)
    assert prepared.get_balance(uid) == before


def test_approving_needs_the_tick(book, prepared):
    c, uid, book_id = book
    approve(c, prepared, uid, book_id, tick=False)
    assert "approved_for" not in prepared.get_book(uid, book_id)["print"]


def test_a_bad_address_is_explained(book, prepared):
    c, uid, book_id = book
    approve(c, prepared, uid, book_id)
    html = c.post(f"/book/{book_id}/print/order", data={**ADDRESS, "postcode": "12", "state_code": "ZZ"}).get_data(as_text=True)
    assert html.count('class="ferr"') >= 2


def test_ordering_charges_the_price_and_shows_the_order(book, prepared):
    c, uid, book_id = book
    approve(c, prepared, uid, book_id)
    before = prepared.get_balance(uid)
    r = c.post(f"/book/{book_id}/print/order", data=ADDRESS)
    assert r.status_code == 302
    assert prepared.get_balance(uid) == before - ledger.PRINT_PRICE_CENTS
    html = c.get("/orders").get_data(as_text=True)
    assert "Simcha and the Beanstalk" in html and "Durham" in html
