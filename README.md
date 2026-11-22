# Storybook

A 20-page picture book starring the child in an uploaded photo: **"Simcha and the Beanstalk"** or
**Little Red Riding Hood, featuring Meira**. Sign in with Google, add funds, make a book in about a
minute, download it as a PDF, or order a printed hardcover.

Live site: https://storybook.kupchikgames.shop

## How the code is organized

```
app.py                  the entry point (Render runs: gunicorn app:app)
storybook/
  content/              what a book says and looks like
    stories.py            the two stories: text, scenes, the child's name, expressions, page rules
    layout.py             where the words go on each page (never over a face)
    pdf.py                the PDFs: the book to download, and the print files (cover + inside)
    legacy.py             books made before the 20-page template
  making/               turning a photo into a finished book
    ai.py                 OpenAI: drawing and checking pictures, and what each call costs
    checks.py             checking what the parent types (real name, kind, no contact details)
    assets.py             the ready-made scenes and characters every book starts from
    generator.py          making one book, start to finish, in the background
  money/
    ledger.py             the wallet: funds, $0.99 per book, refunds, printed copies
    printing.py           Lulu's print API (sandbox only)
  web/                  the website (Flask)
    __init__.py           app setup, template helpers, error pages
    pages.py              home, new book, book page, my books, downloads
    wallet.py  orders.py  auth.py
  storage.py            DynamoDB + S3 (or a local folder when testing)
scripts/                command-line tools
  prepare_story.py        draw the ready-made scenes (run once per story, or to redraw pages)
  lulu_check.py           check the Lulu keys and get a real price quote
  stats.py                cost statistics
tests/                  one folder per part: content, making, money, web
templates/  fonts/  samples/
```

## How a book is made

1. The photo becomes **one character design** of the child (checked: same person, cartoon style).
2. Each of the 20 pages starts from a **ready-made scene** drawn once per story with a stand-in
   child. The stand-in's face is blurred out and the child is drawn in, with an expression that
   fits the moment. All 20 pages are drawn **in parallel**.
3. Every picture is **checked** by a vision model: same face and body as the character, two arms,
   child-sized next to adults, the page's rules (Jack hidden in the pot, the wolf leaving through
   the window...). Up to 3 tries; the best one is kept.
4. The words are placed on the plainest part of each page (never over a face) and the book is
   saved as a **24-page PDF**: cover, copyright page, 20 pages, The End, About Me.
5. Everything is **stored in AWS**, so books are still there next time. Every step is logged.

## Run it locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env      # then fill in your keys (see SETUP.md)
python app.py             # http://localhost:5001
```
Set `FAKE_IMAGES=1` and `FAKE_PRINT=1` in `.env` to try it with free placeholder pictures.

## Run the tests

The tests run offline in test mode: placeholder pictures, a pretend printer, a temporary data
folder. No OpenAI, Stripe, Lulu or AWS calls, even if your `.env` has real keys.

```bash
pytest                       # everything (about 10 seconds)
pytest tests/content         # stories, page layout, PDFs
pytest tests/making          # the detail checks, the page check, scenes, making a whole book
pytest tests/money           # the wallet and printing
pytest tests/web             # the pages, the New book form, printed orders
pytest -k refund             # just the tests with "refund" in their name
```

## More

- [SETUP.md](SETUP.md): Google sign-in, AWS, Stripe, Lulu and Render, step by step
- [WRITEUP.md](WRITEUP.md): what was built, the business model and pricing
- [to-do.md](to-do.md) and [review-log.md](review-log.md): open defects and review runs
