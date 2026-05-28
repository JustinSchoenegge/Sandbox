import json
import os
from datetime import datetime, timedelta

from storage import atomic_save

HABITS_FILE = "data/habits.json"

HABITS = [
    "AI", "Running", "Lifting", "Reading",
    "Eating Healthy", "Streaming", "Lawn Care", "Feed Cats", "Leveling Up",
]


def load_habits():
    if not os.path.exists(HABITS_FILE):
        return {"habits": list(HABITS), "logs": {}}
    try:
        with open(HABITS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"habits": list(HABITS), "logs": {}}


def save_habits(data):
    atomic_save(HABITS_FILE, data)


def calculate_streak(dates):
    if not dates:
        return 0
    sorted_dates = sorted(dates, reverse=True)
    today = datetime.now().date()
    most_recent = datetime.strptime(sorted_dates[0], "%Y-%m-%d").date()
    if most_recent < today - timedelta(days=1):
        return 0
    streak = 0
    current = most_recent
    for date_str in sorted_dates:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if date == current:
            streak += 1
            current -= timedelta(days=1)
        elif date < current:
            break
    return streak


def is_done_today(dates):
    today = datetime.now().strftime("%Y-%m-%d")
    return today in dates


def mark_done(data, habit):
    today = datetime.now().strftime("%Y-%m-%d")
    logs = data["logs"]
    if today not in logs.get(habit, []):
        if habit not in logs:
            logs[habit] = []
        logs[habit].append(today)
        save_habits(data)
        return True
    return False
