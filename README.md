# Storybook: Jack and the Beanstalk

A cartoon *Jack and the Beanstalk* starring the person in an uploaded photo. Sign in with
Google, make a book, watch each picture appear as it's drawn, and download it as one PDF.
Books are saved to your account, so they're still there when you come back.

Live site: https://storybook.kupchikgames.shop

## How it works

1. **Sign in with Google** (`auth.py`), using OAuth credentials from Google Cloud Console.
2. The uploaded photo becomes **one character design** of the person as Jack (one image call).
3. Every story page is drawn from **that character image**, not the photo, with the same
   style wording on every call, so Jack looks the same on every page. The pages are drawn
   **in parallel**, in a background thread (`generator.py`).
4. The book page polls the server every 2 seconds and shows a **progress bar per image**.
5. Each user's books are **stored in AWS** (`storage.py`): records in DynamoDB, images in a
   private S3 bucket. Locally, without AWS settings, they go in `local_data/` instead.
6. The **PDF** (`book.py`): cover, pages 1–3 with the story text drawn on top (never by the
   image model), and an About Me page with the real photo next to the cartoon.
7. **Logging**: sign-ins, books, each image's result and timing, downloads and errors go to the
   console (Render → Logs).

The prompts and pages are in `story.py`. Adding page 4 means adding one entry to `PAGES`.

## Setup

See **[SETUP.md](SETUP.md)** for Google sign-in, AWS and Render, step by step.

Quick local run:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys
python app.py             # http://localhost:5001
```
Set `FAKE_IMAGES=1` in `.env` to test with free placeholder images.

## What still needs work

See [to-do.md](to-do.md).
