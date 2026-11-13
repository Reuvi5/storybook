"""
Check the Lulu sandbox keys and see what one printed book really costs. Places NO order.

    python lulu_check.py

Reads LULU_CLIENT_KEY / LULU_CLIENT_SECRET from .env, then asks Lulu's sandbox:
  1. sign in (are the keys right?)
  2. the cover size for our 24-page 6x9 hardcover (is the product id valid?)
  3. the price of printing + shipping one copy to a sample US address
It prints the per-book math. It never prints the keys.
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()
os.environ.pop("FAKE_PRINT", None)

import printing  # noqa: E402  (needs the settings loaded first)

SAMPLE = {"name": "Sample Parent", "street1": "700 Park Offices Dr", "street2": "Suite 250",
          "city": "Research Triangle Park", "state_code": "NC", "postcode": "27709",
          "country_code": "US", "phone_number": "9195550100", "email": "parent@example.com"}
PAGES = 24
GENERATION = float(os.environ.get("GENERATION_COST", "0.70"))  # average OpenAI cost per book (Wallet page)


def main():
    if not printing.configured():
        sys.exit("LULU_CLIENT_KEY and LULU_CLIENT_SECRET aren't in .env yet.")
    print(f"Lulu: {printing.BASE}")
    try:
        printing._bearer()
        print("1. Sign-in: OK")
        w, h = printing.cover_dimensions(PAGES)
        print(f"2. Product {printing.POD_PACKAGE_ID}: OK, cover {w:.1f} x {h:.1f} pt ({w/72:.3f} x {h/72:.3f} in)")
        q = printing.quote(SAMPLE, PAGES)
    except printing.LuluError as e:
        print(f"Lulu said no ({e.status}): {e}")
        if e.detail:
            print(e.detail)
        sys.exit(1)
    print("3. Quote:", json.dumps(q))

    price = int(os.environ.get("PRINT_PRICE_CENTS", "3499")) / 100
    stripe = price * 0.029 + 0.30
    cost = GENERATION + q["total"] + stripe
    print()
    print(f"   generation (OpenAI)     ${GENERATION:6.2f}")
    print(f"   printing (Lulu)         ${q['printing']:6.2f}")
    print(f"   shipping (Lulu, {printing.SHIPPING_LEVEL:4s})  ${q['shipping']:6.2f}")
    print(f"   fulfillment (Lulu)      ${q['fulfillment']:6.2f}")
    print(f"   tax                     ${q['tax']:6.2f}")
    print(f"   Stripe 2.9% + 30c       ${stripe:6.2f}")
    print(f"   cost per book           ${cost:6.2f}")
    print(f"   price                   ${price:6.2f}")
    print(f"   margin                  ${price - cost:6.2f}  ({(price - cost) / price:.0%})")


if __name__ == "__main__":
    main()
