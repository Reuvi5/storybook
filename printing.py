"""
Printed books, through Lulu's Print API, in its SANDBOX only: no real book is printed, shipped or
charged. (https://api.sandbox.lulu.com; keys from https://developers.sandbox.lulu.com)

Settings (.env locally, Render's Environment tab when deployed; never in the code):
  LULU_CLIENT_KEY, LULU_CLIENT_SECRET   - sandbox API key and secret
  LULU_POD_PACKAGE_ID                   - optional; default: 6x9 full-color premium hardcover (casewrap), gloss
  FAKE_PRINT=1                          - optional; pretend to talk to Lulu (for tests)

The product: a 6 x 9 in hardcover, full color. Lulu's hardcover minimum is 24 pages, so the interior is
copyright page + 20 story pages + The End + blank endpapers (book.build_print_interior).
"""

import logging
import os
import threading
import time
import uuid

import requests

log = logging.getLogger("storybook.printing")

BASE = os.environ.get("LULU_API_BASE", "https://api.sandbox.lulu.com").rstrip("/")
TOKEN_URL = f"{BASE}/auth/realms/glasstree/protocol/openid-connect/token"
# 6"x9" (0600X0900), full color (FC), premium (PRE), casewrap hardcover (CW), 80# coated white paper (080CW444),
# gloss cover (G), no linen (X), no foil (X)
POD_PACKAGE_ID = os.environ.get("LULU_POD_PACKAGE_ID", "0600X0900FCPRECW080CW444GXX")
SHIPPING_LEVEL = os.environ.get("LULU_SHIPPING_LEVEL", "MAIL")
FAKE = os.environ.get("FAKE_PRINT") == "1"
FINAL = {"SHIPPED", "REJECTED", "CANCELED", "ERROR"}

if "sandbox" not in BASE and not FAKE:
    # This project is sandbox only: refuse to place real orders.
    raise RuntimeError("LULU_API_BASE must be Lulu's sandbox (https://api.sandbox.lulu.com)")


class LuluError(Exception):
    def __init__(self, message, status=None, detail=None):
        super().__init__(message)
        self.status = status
        self.detail = detail


def configured() -> bool:
    return FAKE or bool(os.environ.get("LULU_CLIENT_KEY") and os.environ.get("LULU_CLIENT_SECRET"))


_token = {"value": None, "expires": 0}
_token_lock = threading.Lock()


def _bearer() -> str:
    with _token_lock:
        if _token["value"] and time.time() < _token["expires"] - 60:
            return _token["value"]
        r = requests.post(TOKEN_URL, data={"grant_type": "client_credentials"},
                          auth=(os.environ["LULU_CLIENT_KEY"], os.environ["LULU_CLIENT_SECRET"]), timeout=30)
        if r.status_code != 200:
            raise LuluError("Lulu sign-in failed: check LULU_CLIENT_KEY and LULU_CLIENT_SECRET (sandbox keys)", r.status_code, r.text[:300])
        data = r.json()
        _token.update(value=data["access_token"], expires=time.time() + int(data.get("expires_in", 3600)))
        return _token["value"]


def _call(method, path, body=None):
    r = requests.request(method, f"{BASE}{path}", json=body, timeout=60,
                         headers={"Authorization": f"Bearer {_bearer()}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        log.error("lulu_error method=%s path=%s status=%s body=%s", method, path, r.status_code, r.text[:500])
        raise LuluError(_readable(r), r.status_code, r.text[:1000])
    return r.json() if r.text else {}


def _readable(r) -> str:
    """Lulu's validation errors are nested JSON; turn them into one readable line."""
    try:
        data = r.json()
    except ValueError:
        return f"Lulu returned an error ({r.status_code})."
    msgs = []

    def walk(prefix, v):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(f"{prefix}{k}." if k not in ("detail", "message") else prefix, x)
        elif isinstance(v, list):
            for x in v:
                walk(prefix, x)
        elif v is not None:
            msgs.append(f"{prefix.rstrip('.')}: {v}" if prefix else str(v))
    walk("", data)
    return "; ".join(msgs)[:400] or f"Lulu returned an error ({r.status_code})."


# ---------------------------------------------------------------------------
# What we ask Lulu
# ---------------------------------------------------------------------------
def cover_dimensions(page_count: int) -> tuple:
    """The exact one-piece cover size (points) for this product and page count."""
    if FAKE:
        return 990.0, 756.0
    data = _call("POST", "/cover-dimensions/", {"pod_package_id": POD_PACKAGE_ID, "interior_page_count": page_count, "unit": "pt"})
    return float(data["width"]), float(data["height"])


def lulu_address(a: dict) -> dict:
    out = {"name": a["name"], "street1": a["street1"], "city": a["city"], "country_code": a["country_code"],
           "postcode": a["postcode"], "phone_number": a["phone_number"], "email": a.get("email", "")}
    if a.get("street2"):
        out["street2"] = a["street2"]
    if a.get("state_code"):
        out["state_code"] = a["state_code"]
    return out


def quote(address: dict, page_count: int, level: str = SHIPPING_LEVEL) -> dict:
    """What Lulu will charge us for one book shipped to this address (dollars)."""
    if FAKE:
        return {"currency": "USD", "printing": 13.84, "shipping": 4.99, "fulfillment": 0.75, "tax": 0.0, "total": 19.58}
    data = _call("POST", "/print-job-cost-calculations/", {
        "line_items": [{"pod_package_id": POD_PACKAGE_ID, "page_count": page_count, "quantity": 1}],
        "shipping_address": lulu_address(address), "shipping_option": level,
    })
    item = (data.get("line_item_costs") or [{}])[0]
    ship = data.get("shipping_cost") or {}
    fulfil = data.get("fulfillment_cost") or {}
    num = lambda v: float(v) if v not in (None, "") else 0.0  # noqa: E731
    return {
        "currency": data.get("currency", "USD"),
        "printing": num(item.get("total_cost_excl_tax")),
        "shipping": num(ship.get("total_cost_excl_tax")),
        "fulfillment": num(fulfil.get("total_cost_excl_tax")),
        "tax": num(data.get("total_tax")),
        "total": num(data.get("total_cost_incl_tax")),
    }


def create_job(*, title, interior_url, cover_url, page_count, address, email, external_id, level=SHIPPING_LEVEL) -> dict:
    """Place the order with Lulu (sandbox). Returns {"id", "status", "message"}."""
    if FAKE:
        return {"id": int(time.time()) % 1000000, "status": "CREATED", "message": ""}
    data = _call("POST", "/print-jobs/", {
        "contact_email": email,
        "external_id": external_id,
        "shipping_level": level,
        "shipping_address": lulu_address({**address, "email": email}),
        "line_items": [{
            "external_id": external_id,
            "title": title[:255],
            "quantity": 1,
            "printable_normalization": {
                "pod_package_id": POD_PACKAGE_ID,
                "interior": {"source_url": interior_url},
                "cover": {"source_url": cover_url},
            },
        }],
    })
    status = data.get("status") or {}
    return {"id": data["id"], "status": status.get("name", "CREATED"), "message": status.get("message", "")}


def job_status(job_id) -> dict:
    if FAKE:
        return {"status": "CREATED", "message": "Test mode: no request was sent to Lulu."}
    data = _call("GET", f"/print-jobs/{job_id}/")
    status = data.get("status") or {}
    items = data.get("line_items") or [{}]
    return {"status": status.get("name", ""), "message": status.get("message", ""),
            "item_status": (items[0].get("status") or {}).get("name", ""),
            "tracking": (items[0].get("tracking_urls") or [None])[0]}


def new_order_id() -> str:
    return uuid.uuid4().hex[:16]
