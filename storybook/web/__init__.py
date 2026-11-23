"""
The website: a Flask app. Render runs it through the small app.py at the top of the repo
(gunicorn app:app). This file sets the app up (settings, sign-in, the two blueprints, template
helpers, error pages); the pages themselves are in pages.py, the wallet in wallet.py, printed
orders in orders.py and Google sign-in in auth.py.

Secrets come from environment variables (.env locally, Render's Environment tab when deployed),
never from the code. See .env.example and SETUP.md.
"""

import logging
import os
import secrets
import threading
import time
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # must run before the other modules read their settings

from flask import Flask, render_template, request  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from storybook.content import stories  # noqa: E402
from storybook.content.pdf import full_title  # noqa: E402
from storybook.making import ai, assets, generator  # noqa: E402
from storybook.money import ledger  # noqa: E402
from storybook.storage import get_storage  # noqa: E402
from storybook.web import orders, wallet  # noqa: E402
from storybook.web.auth import current_user, init_auth  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]  # the repo folder (templates/, fonts/, samples/)

# ---------------------------------------------------------------------------
# Logging: one line per event, e.g. "... INFO storybook.generator page_done user=... page=4 tries=1 seconds=21.4"
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # the OpenAI library is chatty
log = logging.getLogger("storybook.app")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder=str(ROOT / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB photo cap

# On Render, requests come through Render's proxy. This makes Flask see the visitor's real
# address and that the site is https (needed for Google's sign-in redirect).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

secret = os.environ.get("FLASK_SECRET_KEY")
if not secret:
    log.warning("FLASK_SECRET_KEY is not set: using a temporary key (everyone is signed out on restart)")
    secret = secrets.token_hex(32)
app.secret_key = secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),  # https-only cookies on Render
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

storage = get_storage()
app.extensions["storybook_storage"] = storage
init_auth(app)
app.register_blueprint(wallet.bp)
app.register_blueprint(orders.bp)


def _find_stand_in_heads():
    """Once, in the background: find where the stand-in's head is in every pre-drawn scene (saved, so this
    is a quick read on every later start). Pages blur it out so they copy the child's face, not hers."""
    for s in stories.STORIES.values():
        try:
            if not assets.story_ready(storage, s["id"]):
                continue
            for p in s["pages"]:
                assets.hero_head(storage, s["id"], p["number"])
        except Exception:  # noqa: BLE001 - pages fall back to finding it themselves
            log.exception("stand_in_heads_failed story=%s", s["id"])



_heads_started = threading.Lock()
_heads_running = False


@app.before_request
def _start_background_jobs():
    """Start the stand-in head job on the first visit, inside the process that serves the site.
    Starting it while the app loads is unsafe on Render: gunicorn there loads the app first and then
    splits off the web process, and a split in the middle of a running job can freeze the copy."""
    global _heads_running
    if _heads_running or os.environ.get("STORYBOOK_TESTING") or not (os.environ.get("OPENAI_API_KEY") or ai.FAKE):
        return
    with _heads_started:
        if not _heads_running:
            _heads_running = True
            threading.Thread(target=_find_stand_in_heads, name="stand-in-heads", daemon=True).start()


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
@app.template_filter("datetime")
def _datetime(ts):
    return time.strftime("%b %d, %Y %H:%M UTC", time.gmtime(int(ts))) if ts else ""


app.jinja_env.globals["full_title"] = full_title


@app.context_processor
def inject_costs():
    def avg_cost():
        try:
            return generator.cost_stats(storage)
        except Exception:  # noqa: BLE001
            log.exception("cost_stats_failed")
            return {"books": 0, "avg_usd": None}
    def print_stats():
        try:
            return orders.print_stats(storage)
        except Exception:  # noqa: BLE001
            return {"orders": 0, "avg_lulu": None}
    return {"avg_cost": avg_cost, "print_stats": print_stats, "print_price": ledger.PRINT_PRICE_CENTS}


@app.context_processor
def inject_user():
    user = current_user()
    balance = None
    if user:
        try:
            balance = storage.get_balance(user["id"])
        except Exception:  # never break a page over the header
            log.exception("balance_lookup_failed")
    return {"user": user, "fake_images": generator.FAKE_IMAGES, "balance": balance,
            "money": ledger.money, "price": ledger.BOOK_PRICE_CENTS}


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_):
    return render_template("message.html", title="Not found",
                           message="That page doesn't exist, or it isn't yours."), 404


@app.errorhandler(413)
def too_large(_):
    return render_template("message.html", title="Photo too big",
                           message="That photo is too big (15 MB max)."), 413


@app.errorhandler(500)
def server_error(e):
    log.exception("server_error path=%s", request.path)
    return render_template("message.html", title="Something went wrong",
                           message="Sorry, something went wrong on our side. Please try again."), 500


from storybook.web import pages  # noqa: E402,F401  (registers the pages on the app)
