"""Making one whole book in test mode: every picture, the layout, the PDF, and what it cost."""

import io

from pypdf import PdfReader

from storybook.making import generator
from storybook.storage import book_key


def test_a_book_is_made_start_to_finish(finished_book, prepared):
    _client, uid, book_id = finished_book
    b = prepared.get_book(uid, book_id)
    assert b["status"] == "done"
    names = generator.image_names(b)
    assert len(names) == 21                                   # the character + 20 pages
    assert all(b["images"][n]["status"] == "done" for n in names)
    assert all(b["images"][n].get("layout") for n in names[1:])
    assert generator.layouts_print_safe(b)
    pdf = PdfReader(io.BytesIO(prepared.get_blob(book_key(uid, book_id, "book.pdf"))))
    assert len(pdf.pages) == 24 and pdf.metadata.title == "Simcha and the Beanstalk"
    assert "cost" in b


def test_relayout_keeps_every_page(finished_book, prepared):
    _client, uid, book_id = finished_book
    changes = generator.relayout(prepared, uid, prepared.get_book(uid, book_id))
    assert len(changes) == 20
