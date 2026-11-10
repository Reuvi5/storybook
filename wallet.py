"""
Wallet pages: balance, add funds (Stripe Checkout, test mode), refunds, and the full history.

Settings (in .env locally, Render's Environment tab when deployed; never in the code):
  STRIPE_SECRET_KEY      - the class sandbox key, sk_test_...
  STRIPE_WEBHOOK_SECRET  - optional, whsec_... (only if a webhook endpoint is set up in Stripe)

Money is credited when the user comes back from Checkout (the success page asks Stripe whether
the session was really paid; nothing in the URL is trusted). If a webhook is configured, it
credits the same payment too, and the ledger ignores the duplicate.
"""

import logging
import os

import stripe
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for

import ledger
from auth import current_user, login_required

log = logging.getLogger("storybook.wallet")
bp = Blueprint("wallet", __name__)


def _storage():
    return current_app.extensions["storybook_storage"]


@bp.get("/wallet")
@login_required
def wallet():
    user = current_user()
    return render_template(
        "wallet.html",
        balance=_storage().get_balance(user["id"]),
        txns=ledger.history(_storage(), user["id"]),
        options=ledger.FUND_OPTIONS_CENTS,
        price=ledger.BOOK_PRICE_CENTS,
        money=ledger.money,
        stripe_ready=bool(os.environ.get("STRIPE_SECRET_KEY")),
    )


@bp.post("/wallet/fund")
@login_required
def fund():
    user = current_user()
    try:
        cents = int(request.form.get("amount", 0))
    except ValueError:
        cents = 0
    if cents not in ledger.FUND_OPTIONS_CENTS:
        abort(400)
    if not os.environ.get("STRIPE_SECRET_KEY"):
        flash("Payments aren't set up yet (missing STRIPE_SECRET_KEY).")
        return redirect(url_for("wallet.wallet"))
    session = ledger.plain(stripe.checkout.Session.create(
        api_key=ledger.stripe_key(),
        mode="payment",
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "usd",
                "unit_amount": cents,
                "product_data": {"name": f"Storybook credit ({ledger.money(cents)})"},
            },
        }],
        client_reference_id=user["id"],
        metadata={"user_id": user["id"]},
        customer_email=user.get("email") or None,
        success_url=url_for("wallet.funded", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("wallet.wallet", _external=True),
    ))
    log.info("checkout_started user=%s cents=%s session=%s", user["id"], cents, session["id"])
    return redirect(session["url"], code=303)


@bp.get("/wallet/funded")
@login_required
def funded():
    user = current_user()
    session_id = request.args.get("session_id", "")
    if not session_id.startswith("cs_"):
        abort(400)
    session = ledger.plain(stripe.checkout.Session.retrieve(session_id, api_key=ledger.stripe_key()))
    if (session.get("metadata") or {}).get("user_id") != user["id"]:
        abort(404)  # someone else's payment
    result = ledger.credit_checkout_session(_storage(), session)
    if result in ("ok", "duplicate"):
        flash(f"{ledger.money(session['amount_total'])} added to your balance.")
    else:
        flash("That payment hasn't gone through yet. If it does, it will appear here.")
    return redirect(url_for("wallet.wallet"))


@bp.post("/wallet/refund/<deposit_id>")
@login_required
def refund(deposit_id):
    user = current_user()
    try:
        req = ledger.request_refund(_storage(), user["id"], deposit_id)
    except ValueError:
        abort(404)
    if not req:
        flash("There's nothing left to refund from that payment.")
        return redirect(url_for("wallet.wallet"))
    if ledger.process_refund(_storage(), user["id"], req):
        flash(f"Refund of {ledger.money(-req['amount_cents'])} processed. It goes back to the card the payment came from.")
    else:
        flash("Stripe couldn't process that refund, so the money is back in your balance.")
    return redirect(url_for("wallet.wallet"))


@bp.post("/stripe/webhook")
def webhook():
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        return jsonify(error="webhook not configured"), 400
    try:
        event = stripe.Webhook.construct_event(request.get_data(), request.headers.get("Stripe-Signature", ""), secret)
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify(error="bad signature"), 400
    if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session = ledger.plain(event["data"]["object"])
        result = ledger.credit_checkout_session(_storage(), session)
        log.info("webhook event=%s session=%s result=%s", event["type"], session["id"], result)
    return jsonify(received=True)
