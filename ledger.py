"""
The money side: every credit and debit on a user's account, and why it happened.

All amounts are whole cents. Every change to a balance is one ledger entry ("transaction"),
written together with the balance change (see storage.add_txn), so the history always adds up
to the balance.

Kinds of entry:
  deposit         + money added with Stripe Checkout
  book            - $0.99 charged when a book is started
  book_refund     + the $0.99 given back automatically if a book fails completely
  refund          - money sent back to the card through Stripe (requested, then processed)
  refund_reversed + a refund Stripe rejected, put back into the balance
"""

import logging
import os
import time
import uuid

import stripe

log = logging.getLogger("storybook.ledger")

BOOK_PRICE_CENTS = 99
FUND_OPTIONS_CENTS = [500, 1000, 2000]


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def plain(obj):
    """Stripe's objects aren't dicts (no .get). Convert them to plain dicts, all the way down."""
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


def stripe_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if key and not key.startswith(("sk_test_", "rk_test_")):
        # This project is test mode only. Refuse a live key rather than move real money.
        raise RuntimeError("STRIPE_SECRET_KEY must be a test-mode key (sk_test_...)")
    return key


def _txn(kind, amount_cents, description, **extra):
    return {
        "txn_id": extra.pop("txn_id", None) or f"{kind}-{uuid.uuid4().hex}",
        "created_at": int(time.time()),
        "seq": time.time_ns() // 1000,  # microseconds: keeps entries in true order within a second
        "kind": kind,
        "amount_cents": int(amount_cents),
        "description": description,
        "status": extra.pop("status", "done"),
        **extra,
    }


# ---------------------------------------------------------------------------
# Adding money
# ---------------------------------------------------------------------------
def credit_checkout_session(storage, session) -> str:
    """Credit a paid Stripe Checkout session to its user. Safe to call more than once for the
    same session (from the success page AND the webhook): the second call is a "duplicate"."""
    session = plain(session)
    user_id = (session.get("metadata") or {}).get("user_id") or session.get("client_reference_id")
    if not user_id or session.get("payment_status") != "paid":
        return "not_paid"
    txn = _txn(
        "deposit", session["amount_total"], "Added funds with a card (Stripe)",
        txn_id=f"dep-{session['id']}",
        stripe_session=session["id"],
        stripe_payment_intent=session.get("payment_intent"),
        refunded_cents=0,
    )
    result = storage.add_txn(user_id, txn)
    if result == "ok":
        log.info("funds_added user=%s cents=%s session=%s", user_id, txn["amount_cents"], session["id"])
    return result


# ---------------------------------------------------------------------------
# Paying for a book
# ---------------------------------------------------------------------------
def charge_for_book(storage, user_id, book_id, name) -> bool:
    """Take $0.99 for a new book. False if the balance is too low."""
    txn = _txn("book", -BOOK_PRICE_CENTS, f"Book: {name}", txn_id=f"book-{book_id}", book_id=book_id)
    result = storage.add_txn(user_id, txn)
    if result == "ok":
        log.info("book_charged user=%s book=%s cents=%s", user_id, book_id, BOOK_PRICE_CENTS)
    return result in ("ok", "duplicate")


def refund_failed_book(storage, user_id, book_id) -> None:
    """A book that failed completely gives its $0.99 back to the balance (once)."""
    if not storage.get_txn(user_id, f"book-{book_id}"):
        return
    txn = _txn("book_refund", BOOK_PRICE_CENTS, "Refund: book could not be made",
               txn_id=f"bookrefund-{book_id}", book_id=book_id)
    if storage.add_txn(user_id, txn) == "ok":
        log.info("book_refunded user=%s book=%s", user_id, book_id)


# ---------------------------------------------------------------------------
# Refunds to the card
# ---------------------------------------------------------------------------
def refundable_cents(storage, user_id, deposit: dict) -> int:
    """What can still go back to the card from this deposit: what's left of it, but never more
    than the money still in the account (money already spent on books stays spent)."""
    if deposit.get("kind") != "deposit":
        return 0
    left = deposit["amount_cents"] - deposit.get("refunded_cents", 0)
    return max(0, min(left, storage.get_balance(user_id)))


def request_refund(storage, user_id, deposit_id) -> dict:
    """Step 1: record the refund request and take the money out of the balance, so it can't be
    spent while Stripe processes it. Returns the refund entry, or None if nothing is refundable."""
    deposit = storage.get_txn(user_id, deposit_id)
    if not deposit:
        return None
    amount = refundable_cents(storage, user_id, deposit)
    if amount <= 0:
        return None
    txn = _txn("refund", -amount, "Refund to card", status="requested",
               deposit_id=deposit_id, requested_at=int(time.time()))
    if storage.add_txn(user_id, txn, deposit_id=deposit_id) != "ok":
        return None
    log.info("refund_requested user=%s refund=%s deposit=%s cents=%s", user_id, txn["txn_id"], deposit_id, amount)
    return txn


def process_refund(storage, user_id, refund: dict) -> bool:
    """Step 2: send the refund through Stripe. If Stripe says no, the money goes back into the
    balance and the request is marked failed."""
    deposit = storage.get_txn(user_id, refund["deposit_id"])
    amount = -refund["amount_cents"]
    try:
        stripe_refund = stripe.Refund.create(
            api_key=stripe_key(),
            payment_intent=deposit["stripe_payment_intent"],
            amount=amount,
            metadata={"user_id": user_id, "refund_txn": refund["txn_id"]},
            idempotency_key=refund["txn_id"],  # a retry can never refund twice
        )
        stripe_refund = plain(stripe_refund)
    except Exception as e:  # noqa: BLE001 - any Stripe/network error
        log.error("refund_failed user=%s refund=%s error=%s", user_id, refund["txn_id"], e)
        storage.add_txn(user_id, _txn("refund_reversed", amount, "Refund failed: money returned to balance",
                                      txn_id=f"rev-{refund['txn_id']}", deposit_id=refund["deposit_id"]),
                        deposit_id=refund["deposit_id"])
        storage.update_txn(user_id, refund["txn_id"], status="failed", error=str(e)[:200])
        return False
    status = "processed" if stripe_refund["status"] in ("succeeded", "pending") else stripe_refund["status"]
    storage.update_txn(user_id, refund["txn_id"], status=status,
                       stripe_refund=stripe_refund["id"], processed_at=int(time.time()))
    log.info("refund_processed user=%s refund=%s stripe=%s status=%s",
             user_id, refund["txn_id"], stripe_refund["id"], stripe_refund["status"])
    return True


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
def history(storage, user_id) -> list:
    """Every entry, newest first, each with the balance right after it."""
    txns = sorted(storage.list_txns(user_id), key=lambda t: (t.get("seq", t["created_at"] * 1_000_000), t["txn_id"]))
    running = 0
    balance = storage.get_balance(user_id)
    for t in txns:
        running += t["amount_cents"]
        t["balance_after"] = running
        if t["kind"] == "deposit":
            t["refundable"] = max(0, min(t["amount_cents"] - t.get("refunded_cents", 0), balance))
    return list(reversed(txns))
