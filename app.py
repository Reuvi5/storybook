"""
Entry point for the website. Render starts it with `gunicorn app:app`; locally, `python app.py`.
All the code is in the storybook/ package (see storybook/__init__.py for the map).
"""

import os

from storybook.web import app  # noqa: F401  (gunicorn looks for "app" here)

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
