"""
Storybook: a 20-page picture book starring the child in the uploaded photo.

The code is in four parts (each has its own tests in tests/<part>/):

  content/  what a book says and looks like
            stories.py   the two stories: pages, scenes, the child's name, expressions, page rules
            layout.py    where the words go on each page (never over a face)
            pdf.py       the PDFs: the book to download, and the print files (cover, inside pages)
            legacy.py    the very first version's book (books made before the 20-page template)

  making/   turning a photo into a finished book
            ai.py        OpenAI: drawing pictures and checking them, and what every call costs
            checks.py    checking what the parent types (a real name, nothing unkind, no contact details)
            assets.py    the ready-made scenes and characters every book starts from
            generator.py making one book, start to finish, in the background

  money/    ledger.py    the wallet: funding, charging $0.99, refunds, printed copies
            printing.py  Lulu's print API (sandbox only)

  web/      the website (Flask): __init__.py sets it up, pages.py has the pages,
            wallet.py, orders.py (printed copies) and auth.py (Google sign-in)

  storage.py  where everything is saved: DynamoDB + S3, or a local folder when testing

Command-line tools are in scripts/ (prepare_story.py, lulu_check.py, stats.py).
"""
