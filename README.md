# Storybook: Jack and the Beanstalk

A cartoon *Jack and the Beanstalk* starring the child in an uploaded photo. This build makes
the first 3 pages, and the whole book downloads as one PDF.

Live site: _(paste your Render URL here)_

## How it works

1. The uploaded photo becomes **one character design** of the child as Jack (one image call).
2. Every story page is drawn from **that character image**, not the photo, using the same
   style wording and shared prompt on every call, so the child looks the same on every page.
3. The story text is drawn onto the pages in the PDF, never by the image model.
4. The PDF: cover, pages 1–3 with text on top of full-bleed art, and an About Me page with the
   details typed in on the form.

The prompts and page definitions are in `story.py`. Adding page 4 means adding one entry to
`PAGES` there.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then put your real key in .env
python app.py             # open http://localhost:5001
```

## Deploy on Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --timeout 300`
- Environment variable: `OPENAI_API_KEY`

## What still needs work

See [to-do.md](to-do.md).
