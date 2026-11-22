"""
Sign in with Google (OAuth 2.0 / OpenID Connect), using your own credentials from
Google Cloud Console:

  GOOGLE_CLIENT_ID      - from Google Cloud Console > Credentials
  GOOGLE_CLIENT_SECRET  - same place. Keep it in .env / Render, never in the code.

The signed-in user is kept in Flask's signed session cookie as:
  session["user"] = {"id": <Google's unique user id>, "email": ..., "name": ..., "picture": ...}
"""

import functools
import logging
import os

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, current_app, flash, redirect, request, session, url_for

log = logging.getLogger("storybook.auth")

oauth = OAuth()
bp = Blueprint("auth", __name__)


def init_auth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "prompt": "select_account"},
    )
    app.register_blueprint(bp)
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        log.warning("GOOGLE_CLIENT_ID is not set: sign-in will not work until it is")


def current_user():
    return session.get("user")


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.method == "GET":
                session["next"] = request.path
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapper


@bp.get("/login")
def login():
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        flash("Sign-in isn't set up yet (missing GOOGLE_CLIENT_ID).")
        return redirect(url_for("index"))
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.get("/auth/callback")
def callback():
    if request.args.get("error"):  # e.g. the user clicked Cancel on Google's page
        log.info("login_cancelled error=%s", request.args.get("error"))
        flash("Sign-in was cancelled.")
        return redirect(url_for("index"))
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        log.warning("login_failed error=%s", e)
        flash("Sign-in failed. Please try again.")
        return redirect(url_for("index"))

    info = token.get("userinfo") or {}
    if not info.get("sub") or not info.get("email_verified"):
        log.warning("login_rejected reason=unverified_email")
        flash("Your Google account's email isn't verified.")
        return redirect(url_for("index"))

    user = {
        "id": info["sub"],
        "email": info["email"],
        "name": info.get("name") or info["email"].split("@")[0],
        "picture": info.get("picture", ""),
    }
    next_page = session.get("next")
    if not (next_page and next_page.startswith("/") and not next_page.startswith("//")):
        next_page = url_for("index")  # only ever redirect within this site
    session.clear()
    session["user"] = user
    session.permanent = True
    current_app.extensions["storybook_storage"].save_user(user)
    log.info("login user=%s", user["id"])
    return redirect(next_page)


@bp.post("/logout")
def logout():
    user = current_user()
    session.clear()
    if user:
        log.info("logout user=%s", user["id"])
    return redirect(url_for("index"))
