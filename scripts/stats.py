"""
The running cost totals behind "average API cost per book".

    python scripts/stats.py           # show them
    python scripts/stats.py reset     # start counting again from zero (e.g. after test books skewed them)

Uses the same database as the app (AWS from .env, or local_data/).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # the repo, for "storybook"


from dotenv import load_dotenv

load_dotenv()

from storybook.making import generator  # noqa: E402
from storybook.storage import get_storage  # noqa: E402

storage = get_storage()
print("now:", generator.cost_stats(storage))
if sys.argv[1:] == ["reset"]:
    storage.put_record("STATS", "COSTS", {"books": 0, "usd_micro": 0, "image_calls": 0, "analysis_calls": 0, "retries": 0})
    print("reset:", generator.cost_stats(storage))
