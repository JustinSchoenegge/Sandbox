import json
import os
from datetime import datetime

from storage import atomic_save

TASKS_FILE = "data/tasks.json"

TEMPLATES = ["Vacuum", "Clean Sink", "Clean Litter Box", "Review Stocks"]


def load_tasks():
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == today:
                return data["tasks"]
        except json.JSONDecodeError:
            pass
    tasks = [{"name": t, "done": False} for t in TEMPLATES]
    save_tasks(tasks)
    return tasks


def save_tasks(tasks):
    today = datetime.now().strftime("%Y-%m-%d")
    atomic_save(TASKS_FILE, {"date": today, "tasks": tasks})
