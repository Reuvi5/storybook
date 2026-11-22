"""
Shared setup for every test. Everything runs offline, in test mode:

  - placeholder pictures instead of OpenAI (FAKE_IMAGES), with no pretend waiting (FAKE_FAST)
  - a pretend Lulu (FAKE_PRINT), no Stripe, no AWS: a fresh temporary data folder per run
  - real keys in your .env are ignored (they are blanked here, before the app reads .env)

Run everything:            pytest
Run one part:              pytest tests/content   (or tests/making, tests/money, tests/web)
Run one file or one test:  pytest tests/money/test_ledger.py   /   pytest -k refund
"""

import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.update({
    "FAKE_IMAGES": "1", "FAKE_PRINT": "1", "FAKE_FAST": "1", "STORYBOOK_TESTING": "1",
    "LOCAL_DATA_DIR": tempfile.mkdtemp(prefix="storybook-tests-"),
    "FLASK_SECRET_KEY": "test-secret", "GOOGLE_CLIENT_ID": "test", "GOOGLE_CLIENT_SECRET": "test",
    "BOOKS_PER_HOUR": "1000", "LOG_LEVEL": "WARNING",
})
for key in ("S3_BUCKET", "DYNAMODB_TABLE", "OPENAI_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "LULU_CLIENT_KEY", "LULU_CLIENT_SECRET", "LULU_API_BASE"):
    os.environ[key] = ""  # set (to empty) so load_dotenv() can't fill them in from .env

import pytest  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402


# ---- pictures ---------------------------------------------------------------------------------------
def jpeg(color=(200, 180, 150), size=(600, 900), face=True) -> bytes:
    """A simple test picture: a plain background with a face-like oval."""
    img = Image.new("RGB", size, color)
    if face:
        w, h = size
        ImageDraw.Draw(img).ellipse((w * .35, h * .25, w * .65, h * .5), fill=(240, 205, 170))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


@pytest.fixture
def photo():
    return jpeg()


# ---- storage and the two prepared stories ----------------------------------------------------------
@pytest.fixture(scope="session")
def storage():
    from storybook.storage import get_storage
    return get_storage()


@pytest.fixture(scope="session")
def prepared(storage):
    """Both stories' ready-made scenes and characters, drawn once per test run (placeholders)."""
    from storybook.content import stories
    from storybook.making import assets
    quiet = lambda *a, **k: None  # noqa: E731
    for sid in stories.STORIES:
        failed = assets.prepare_bible(storage, sid, say=quiet)
        failed += assets.prepare_plates(storage, sid, say=quiet)
        assert assets.mark_ready(storage, sid, failed=failed, say=quiet), f"{sid} didn't prepare"
    return storage


# ---- the website -----------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def app(storage):
    from storybook.web import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


_users = iter(range(10_000))


@pytest.fixture
def user_id():
    return f"t{int(time.time())}{next(_users):04d}"


def sign_in(client, user_id):
    with client.session_transaction() as s:
        s["user"] = {"id": user_id, "email": f"{user_id}@example.com", "name": "Test Parent", "picture": ""}


def add_funds(storage, user_id, cents):
    from storybook.money import ledger
    ledger.credit_checkout_session(storage, {
        "id": f"cs_test_{user_id}_{time.time_ns()}", "payment_status": "paid", "amount_total": cents,
        "metadata": {"user_id": user_id}, "payment_intent": f"pi_test_{time.time_ns()}"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signed_in(client, user_id):
    """A test client signed in as a brand-new user with an empty wallet."""
    sign_in(client, user_id)
    return client


@pytest.fixture
def funded(signed_in, storage, user_id):
    """Signed in, with $10.00 in the wallet."""
    add_funds(storage, user_id, 1000)
    return signed_in


def make_book(client, story="jack", name="Simcha", photo=None, wait=True, **details):
    """Submit the New book form; return (response, book_id). Waits for the book to finish by default."""
    data = {"story": story, "name": name, "photo": (io.BytesIO(photo or jpeg()), "me.jpg"), **details}
    r = client.post("/make", data=data, content_type="multipart/form-data")
    if r.status_code != 302:
        return r, None
    book_id = r.headers["Location"].rstrip("/").split("/")[-1]
    if wait:
        for _ in range(600):
            s = client.get(f"/book/{book_id}/status").get_json()
            if s["status"] != "generating":
                break
            time.sleep(0.05)
    return r, book_id


@pytest.fixture(scope="session")
def finished_book(app, prepared):
    """One finished Jack book, shared by the tests that only look at a book: (client, user_id, book_id)."""
    c = app.test_client()
    uid = f"tbook{int(time.time())}"
    sign_in(c, uid)
    add_funds(prepared, uid, 1000)
    r, book_id = make_book(c, "jack", "Simcha", age="7", favorite_color="Green")
    assert book_id, r.get_data(as_text=True)[:500]
    return c, uid, book_id
