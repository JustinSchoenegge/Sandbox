import json
import os

from storage import atomic_save

NOTES_FILE = "data/notes.json"


def load_notes():
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_notes(notes):
    atomic_save(NOTES_FILE, notes)
