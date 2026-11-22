"""The wallet: adding funds, paying $0.99 per book, refunds, printed copies, and the history."""

from storybook.money import ledger
from tests.conftest import add_funds

PRICE = ledger.BOOK_PRICE_CENTS


def session(user_id, cents, sid="cs_test_1"):
    return {"id": sid, "payment_status": "paid", "amount_total": cents,
            "metadata": {"user_id": user_id}, "payment_intent": "pi_test_1"}


def test_price_and_money_format():
    assert PRICE == 99
    assert ledger.money(99) == "$0.99" and ledger.money(3499) == "$34.99" and ledger.money(0) == "$0.00"


def test_adding_funds_counts_once(storage, user_id):
    assert ledger.credit_checkout_session(storage, session(user_id, 500)) == "ok"
    assert ledger.credit_checkout_session(storage, session(user_id, 500)) == "duplicate"  # webhook + success page
    assert storage.get_balance(user_id) == 500


def test_unpaid_session_adds_nothing(storage, user_id):
    s = {**session(user_id, 500), "payment_status": "unpaid"}
    assert ledger.credit_checkout_session(storage, s) == "not_paid"
    assert storage.get_balance(user_id) == 0


def test_a_book_costs_exactly_99_cents(storage, user_id):
    add_funds(storage, user_id, 500)
    assert ledger.charge_for_book(storage, user_id, "b1", "Simcha and the Beanstalk")
    assert storage.get_balance(user_id) == 500 - PRICE


def test_the_balance_never_goes_negative(storage, user_id):
    add_funds(storage, user_id, 50)
    assert not ledger.charge_for_book(storage, user_id, "b1", "too expensive")
    assert storage.get_balance(user_id) == 50


def test_a_failed_book_is_refunded_once(storage, user_id):
    add_funds(storage, user_id, 500)
    ledger.charge_for_book(storage, user_id, "b1", "x")
    ledger.refund_failed_book(storage, user_id, "b1")
    ledger.refund_failed_book(storage, user_id, "b1")
    assert storage.get_balance(user_id) == 500


def test_no_refund_for_a_book_that_was_never_charged(storage, user_id):
    ledger.refund_failed_book(storage, user_id, "never-charged")
    assert storage.get_balance(user_id) == 0


def test_printed_copy_charge_and_refund(storage, user_id):
    add_funds(storage, user_id, 5000)
    assert ledger.charge_for_print(storage, user_id, "o1", ledger.PRINT_PRICE_CENTS, "Printed book")
    assert storage.get_balance(user_id) == 5000 - ledger.PRINT_PRICE_CENTS
    ledger.refund_print(storage, user_id, "o1", ledger.PRINT_PRICE_CENTS, "the printer said no")
    assert storage.get_balance(user_id) == 5000


def test_history_explains_every_change_and_adds_up(storage, user_id):
    add_funds(storage, user_id, 1000)
    ledger.charge_for_book(storage, user_id, "b1", "Book one")
    ledger.charge_for_book(storage, user_id, "b2", "Book two")
    ledger.refund_failed_book(storage, user_id, "b2")
    rows = ledger.history(storage, user_id)
    assert {r["kind"] for r in rows} >= {"deposit", "book", "book_refund"}
    assert all(r["description"] and r["created_at"] for r in rows)
    assert sum(r["amount_cents"] for r in rows) == storage.get_balance(user_id) == 1000 - PRICE
