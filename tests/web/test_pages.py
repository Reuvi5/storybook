"""Every page opens, shows the right things, and only ever shows a user their own books."""

import html

import pytest

from tests.conftest import sign_in


def test_home_page_for_visitors(client, prepared):
    page = client.get("/").get_data(as_text=True)
    assert "Your child is the" in page and "Sign in with Google" in page
    assert "{name}" not in page and "{him}" not in page            # story blurbs are filled in
    assert "magic beans" in page and "Big Bad Wolf" in page               # each story is pitched


@pytest.mark.parametrize("path", ["/books", "/wallet", "/orders"])
def test_signed_out_visitors_are_sent_to_sign_in(client, path):
    r = client.get(path)
    assert r.status_code in (302, 401)


@pytest.mark.parametrize("path,text", [
    ("/", "Make a new storybook"),
    ("/books", "My books"),
    ("/wallet", "Balance"),
    ("/orders", "Orders"),
    ("/privacy", "Privacy"),
])
def test_signed_in_pages_open(signed_in, prepared, path, text):
    r = signed_in.get(path)
    assert r.status_code == 200 and text in r.get_data(as_text=True)


def test_no_boy_or_girl_question(signed_in, prepared):
    page = signed_in.get("/").get_data(as_text=True)
    assert 'name="pronoun"' not in page and "Boy" not in page


def test_missing_pages_get_a_friendly_404(signed_in):
    r = signed_in.get("/no-such-page")
    assert r.status_code == 404 and "doesn't exist" in html.unescape(r.get_data(as_text=True))


def test_book_page_progress_and_download(finished_book):
    c, _uid, book_id = finished_book
    page = c.get(f"/book/{book_id}").get_data(as_text=True)
    assert "Simcha and the Beanstalk" in page and "Download PDF" in page and "of 3" in page
    status = c.get(f"/book/{book_id}/status").get_json()
    assert status["status"] == "done" and status["done"] == status["total"] == 21
    pdf = c.get(f"/book/{book_id}/download")
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    assert "Simcha-and-the-Beanstalk.pdf" in pdf.headers["Content-Disposition"]


def test_other_users_cannot_see_a_book(app, finished_book):
    _c, _uid, book_id = finished_book
    stranger = app.test_client()
    sign_in(stranger, "someone-else")
    assert stranger.get(f"/book/{book_id}").status_code == 404
    assert stranger.get(f"/book/{book_id}/download").status_code == 404
