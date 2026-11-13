"""
Ordering a printed copy (Lulu sandbox: nothing is really printed or shipped).

  1. /book/<id>/print          The print files are built and shown: the exact interior and cover PDFs
                                that would go to the printer.
  2. POST .../print/approve     The user confirms they reviewed them. Nothing can be ordered before this,
                                and the approval is tied to those exact files (a fingerprint of each).
  3. POST .../print/order       The user enters the delivery address. The app charges the wallet, places
                                the order with Lulu, and refunds automatically if Lulu refuses it.
  4. /orders                    Every order and its status at Lulu.

Order records live with the user's data: DynamoDB sk "ORDER#<id>".
"""

import hashlib
import logging
import re
import time

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

import book as pdf
import generator
import ledger
import printing
import stories
from auth import current_user, login_required
from storage import book_key

log = logging.getLogger("storybook.orders")
bp = Blueprint("orders", __name__)

US_STATES = ("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
             "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY").split()
ADDRESS_FIELDS = ["name", "street1", "street2", "city", "state_code", "postcode", "phone_number", "email"]


def _storage():
    return current_app.extensions["storybook_storage"]


def _own_book(book_id):
    user = current_user()
    b = _storage().get_book(user["id"], book_id)
    if not b or b.get("version", 1) < 2 or b["status"] != "done":
        abort(404)
    return user, b


def _url(key, seconds=900):
    return _storage().blob_url(key, seconds) if hasattr(_storage(), "s3") else url_for("blob", key=key)


# ---------------------------------------------------------------------------
# The print files
# ---------------------------------------------------------------------------
def prepare_print_files(storage, user_id, b, force=False) -> dict:
    """Build the interior and cover PDFs exactly as they'd be printed, store them, and remember their
    fingerprints. Older books are re-laid out first (free) so all text is 0.5 in inside the trim."""
    if b.get("print") and not force:
        return b["print"]
    if not generator.layouts_print_safe(b):
        generator.relayout(storage, user_id, b)
        b = storage.get_book(user_id, b["book_id"])
    s = stories.get_story(b["story_id"])
    bid, name = b["book_id"], b["details"]["name"]
    pages = generator.book_pages(storage, user_id, b)
    interior, page_count = pdf.build_print_interior(s, name, pages, bid, b["created_at"])
    width, height = printing.cover_dimensions(page_count)
    cover, geo = pdf.build_print_cover(s, name, generator.labeled_details(b["details"]),
                                       storage.get_blob(book_key(user_id, bid, "hero.png")),
                                       storage.get_image(user_id, bid, "photo"), width, height)
    storage.put_blob(book_key(user_id, bid, "print-interior.pdf"), interior)
    storage.put_blob(book_key(user_id, bid, "print-cover.pdf"), cover)
    info = {
        "built_at": int(time.time()), "page_count": page_count, "cover_size": [round(width, 2), round(height, 2)],
        "cover_geometry": geo, "pod_package_id": printing.POD_PACKAGE_ID,
        "interior_sha": hashlib.sha256(interior).hexdigest(), "cover_sha": hashlib.sha256(cover).hexdigest(),
    }
    storage.update_book(user_id, bid, print=info)
    log.info("print_files_built user=%s book=%s pages=%s cover=%sx%s", user_id, bid, page_count, round(width), round(height))
    return info


def _approved(info) -> bool:
    return bool(info.get("approved_at")) and info.get("approved_for") == info["interior_sha"] + info["cover_sha"]


@bp.get("/book/<book_id>/print")
@login_required
def print_page(book_id):
    user, b = _own_book(book_id)
    s = stories.get_story(b["story_id"])
    if not printing.configured():
        return render_template("print.html", book=b, story=s, ready=False, price=ledger.PRINT_PRICE_CENTS)
    try:
        info = prepare_print_files(_storage(), user["id"], b, force=request.args.get("rebuild") == "1")
    except printing.LuluError as e:
        log.error("print_prepare_failed user=%s book=%s error=%s", user["id"], book_id, e)
        return render_template("print.html", book=b, story=s, ready=True, error=f"The printer couldn't size the cover: {e}",
                               price=ledger.PRINT_PRICE_CENTS)
    return render_template(
        "print.html", book=b, story=s, ready=True, info=info, approved=_approved(info),
        interior_url=_url(book_key(user["id"], book_id, "print-interior.pdf")),
        cover_url=_url(book_key(user["id"], book_id, "print-cover.pdf")),
        price=ledger.PRINT_PRICE_CENTS, balance=_storage().get_balance(user["id"]),
        address=request.args, states=US_STATES, errors={},
    )


@bp.post("/book/<book_id>/print/approve")
@login_required
def approve(book_id):
    user, b = _own_book(book_id)
    info = b.get("print")
    if not info:
        return redirect(url_for("orders.print_page", book_id=book_id))
    if request.form.get("approve") != "yes" or request.form.get("fingerprint") != info["interior_sha"][:12]:
        flash("Please tick the box to confirm you've reviewed the book.")
        return redirect(url_for("orders.print_page", book_id=book_id))
    info.update(approved_at=int(time.time()), approved_for=info["interior_sha"] + info["cover_sha"])
    _storage().update_book(user["id"], book_id, print=info)
    log.info("print_approved user=%s book=%s", user["id"], book_id)
    return redirect(url_for("orders.print_page", book_id=book_id) + "#address")


def check_address(form) -> tuple:
    a = {k: form.get(k, "").strip() for k in ADDRESS_FIELDS}
    a["country_code"] = "US"
    a["state_code"] = a["state_code"].upper()
    errors = {}
    if not 2 <= len(a["name"]) <= 60:
        errors["name"] = "Enter the recipient's name."
    if not 3 <= len(a["street1"]) <= 80:
        errors["street1"] = "Enter the street address."
    if len(a["street2"]) > 80:
        errors["street2"] = "That's too long."
    if not 2 <= len(a["city"]) <= 50:
        errors["city"] = "Enter the city."
    if a["state_code"] not in US_STATES:
        errors["state_code"] = "Choose a state."
    if not re.fullmatch(r"\d{5}(-\d{4})?", a["postcode"]):
        errors["postcode"] = "Enter a 5-digit ZIP code."
    digits = re.sub(r"\D", "", a["phone_number"])
    if not 10 <= len(digits) <= 15:
        errors["phone_number"] = "The printer needs a phone number for the delivery (10 digits)."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", a["email"]):
        errors["email"] = "Enter an email for delivery updates."
    return a, errors


@bp.post("/book/<book_id>/print/order")
@login_required
def place_order(book_id):
    user, b = _own_book(book_id)
    storage = _storage()
    info = b.get("print")
    if not printing.configured() or not info or not _approved(info):
        flash("Please review and approve the book before ordering.")
        return redirect(url_for("orders.print_page", book_id=book_id))
    address, errors = check_address(request.form)
    s = stories.get_story(b["story_id"])
    price = ledger.PRINT_PRICE_CENTS

    def again(message):
        return render_template(
            "print.html", book=b, story=s, ready=True, info=info, approved=True, error=message,
            interior_url=_url(book_key(user["id"], book_id, "print-interior.pdf")),
            cover_url=_url(book_key(user["id"], book_id, "print-cover.pdf")),
            price=price, balance=storage.get_balance(user["id"]), address=address, states=US_STATES, errors=errors)

    if errors:
        return again("Please check the delivery address.")
    if storage.get_balance(user["id"]) < price:
        return again(f"A printed book costs {ledger.money(price)}, and your balance is "
                     f"{ledger.money(storage.get_balance(user['id']))}. Add funds in your Wallet first.")
    try:
        cost = printing.quote(address, info["page_count"])
    except printing.LuluError as e:
        return again(f"The printer couldn't price this address: {e}")

    order_id = printing.new_order_id()
    title = f"{s['title']}, starring {b['details']['name']}"
    if not ledger.charge_for_print(storage, user["id"], order_id, price, f"Printed book: {title}"):
        return again("Your balance is too low for a printed book.")
    record = {
        "order_id": order_id, "book_id": book_id, "title": title, "created_at": int(time.time()),
        "price_cents": price, "quote": cost, "shipping_level": printing.SHIPPING_LEVEL,
        "pod_package_id": info["pod_package_id"], "page_count": info["page_count"],
        "files": {"interior_sha": info["interior_sha"], "cover_sha": info["cover_sha"]},
        "approved_at": info["approved_at"], "sandbox": True,
        # Only what the order page needs; Lulu keeps the full address for delivery.
        "ship_to": {"name": address["name"], "city": address["city"], "state": address["state_code"], "postcode": address["postcode"]},
    }
    try:
        # Lulu downloads the files from these links (valid 7 days), so they must be the approved files.
        job = printing.create_job(
            title=title,
            interior_url=_url(book_key(user["id"], book_id, "print-interior.pdf"), 7 * 24 * 3600),
            cover_url=_url(book_key(user["id"], book_id, "print-cover.pdf"), 7 * 24 * 3600),
            page_count=info["page_count"], address=address, email=address["email"], external_id=order_id)
    except printing.LuluError as e:
        ledger.refund_print(storage, user["id"], order_id, price, "the printer couldn't accept the order")
        record.update(status="failed", error=str(e)[:300])
        storage.put_record(user["id"], f"ORDER#{order_id}", record)
        log.error("print_order_failed user=%s order=%s error=%s", user["id"], order_id, e)
        return again(f"The printer couldn't accept the order, so your {ledger.money(price)} was returned: {e}")
    record.update(status="placed", lulu_job_id=job["id"], lulu_status=job["status"], lulu_message=job["message"],
                  checked_at=int(time.time()))
    storage.put_record(user["id"], f"ORDER#{order_id}", record)
    storage.add_counters("STATS", "PRINT", orders=1, revenue_cents=price, lulu_cost_micro=int(round(cost["total"] * 1e6)))
    log.info("print_order_placed user=%s order=%s lulu_job=%s cost=%.2f price=%.2f", user["id"], order_id, job["id"], cost["total"], price / 100)
    return redirect(url_for("orders.order", order_id=order_id))


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
def _refresh(user_id, rec):
    """Ask Lulu for the latest status of an order that isn't finished (at most once a minute)."""
    if rec.get("status") != "placed" or rec.get("lulu_status") in printing.FINAL or time.time() - rec.get("checked_at", 0) < 60:
        return rec
    try:
        st = printing.job_status(rec["lulu_job_id"])
    except printing.LuluError:
        return rec
    rec.update(lulu_status=st["status"], lulu_message=st.get("message", ""), tracking=st.get("tracking"), checked_at=int(time.time()))
    _storage().put_record(user_id, f"ORDER#{rec['order_id']}", {k: v for k, v in rec.items() if k != "sk"})
    return rec


@bp.get("/orders")
@login_required
def orders():
    user = current_user()
    recs = sorted(_storage().query_records(user["id"], "ORDER#"), key=lambda r: r["created_at"], reverse=True)
    recs = [_refresh(user["id"], r) for r in recs]
    return render_template("orders.html", orders=recs, one=None)


@bp.get("/orders/<order_id>")
@login_required
def order(order_id):
    user = current_user()
    if not re.fullmatch(r"[0-9a-f]{16}", order_id):
        abort(404)
    rec = _storage().get_record(user["id"], f"ORDER#{order_id}")
    if not rec:
        abort(404)
    return render_template("orders.html", orders=[_refresh(user["id"], rec)], one=True)


def print_stats(storage) -> dict:
    rec = storage.get_record("STATS", "PRINT") or {}
    n = int(rec.get("orders", 0))
    return {"orders": n, "avg_lulu": (rec.get("lulu_cost_micro", 0) / 1e6 / n) if n else None}
