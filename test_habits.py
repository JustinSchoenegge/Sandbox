"""
Fast sanity checks for habits logic. Run with: python3 test_habits.py
"""
import sys
import os
from datetime import datetime, timedelta

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from habits import calculate_streak, is_done_today

TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
TWO_AGO   = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
THREE_AGO = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

def check(label, got, expected):
    if got != expected:
        print(f"  FAIL  {label}: got {got!r}, expected {expected!r}")
        return False
    print(f"  ok    {label}")
    return True

passed = failed = 0

cases = [
    # (label, dates, expected_streak)
    ("empty",                         [],                                       0),
    ("done today only",               [TODAY],                                  1),
    ("done yesterday only",           [YESTERDAY],                              1),
    ("done today + yesterday",        [TODAY, YESTERDAY],                       2),
    ("3-day streak ending today",     [TODAY, YESTERDAY, TWO_AGO],              3),
    ("3-day streak ending yesterday", [YESTERDAY, TWO_AGO, THREE_AGO],          3),
    ("gap two days ago",              [TODAY, TWO_AGO],                         1),
    ("stale — 2+ days ago",           [TWO_AGO, THREE_AGO],                     0),
    ("only 3 days ago",               [THREE_AGO],                              0),
]

print("\ncalculate_streak:")
for label, dates, expected in cases:
    result = calculate_streak(dates)
    if result == expected:
        passed += 1
    else:
        failed += 1
    check(label, result, expected)

print("\nis_done_today:")
for label, dates, done_expected in [
    ("today in list",      [TODAY],     True),
    ("yesterday in list",  [YESTERDAY], False),
    ("empty list",         [],          False),
]:
    result = is_done_today(dates)
    if result == done_expected:
        passed += 1
    else:
        failed += 1
    check(label, result, done_expected)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
