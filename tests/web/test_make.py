"""The New book form: what it refuses, and what it charges."""

from storybook.money import ledger
from tests.conftest import make_book


def test_needs_a_photo(funded, prepared):
    r = funded.post("/make", data={"story": "jack", "name": "Simcha"})
    assert r.status_code == 200 and "Please upload a photo" in r.get_data(as_text=True)


def test_needs_a_story(funded, prepared):
    r, book_id = make_book(funded, story="nope")
    assert book_id is None and "Please choose a story" in r.get_data(as_text=True)


def test_rejects_an_insult_as_a_name(funded, prepared, storage, user_id):
    r, book_id = make_book(funded, name="Stupid")
    assert book_id is None and "real name" in r.get_data(as_text=True)
    assert storage.get_balance(user_id) == 1000                   # nothing was charged


def test_refuses_when_the_balance_is_short(signed_in, prepared, storage, user_id):
    r, book_id = make_book(signed_in)
    assert book_id is None and "Add funds" in r.get_data(as_text=True)
    assert storage.get_balance(user_id) == 0


def test_a_lowercase_name_is_capitalized(funded, prepared, storage, user_id):
    _r, book_id = make_book(funded, name="deens", wait=False)
    assert storage.get_book(user_id, book_id)["details"]["name"] == "Deens"


def test_making_a_book_charges_99_cents(funded, prepared, storage, user_id):
    r, book_id = make_book(funded, story="red", name="Meira")
    assert book_id
    assert storage.get_balance(user_id) == 1000 - ledger.BOOK_PRICE_CENTS
    assert storage.get_book(user_id, book_id)["status"] == "done"
