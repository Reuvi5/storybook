"""
The running cost totals behind "average API cost per book".

    python stats.py           # show them
    python stats.py reset     # start counting again from zero (e.g. after test books skewed them)

Uses the same database as the app (AWS from .env, or local_data/).
"""
import sys

from dotenv import load_dotenv

load_dotenv()

import generator  # noqa: E402
from storage import get_storage  # noqa: E402

storage = get_storage()
print("now:", generator.cost_stats(storage))
if sys.argv[1:] == ["reset"]:
    storage.put_record("STATS", "COSTS", {"books": 0, "usd_micro": 0, "image_calls": 0, "analysis_calls": 0, "retries": 0})
    print("reset:", generator.cost_stats(storage))
