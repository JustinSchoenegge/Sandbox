import json
import os

from storage import atomic_save

NOTES_FILE = "data/notes.json"
NOTES_META_FILE = "data/notes_meta.json"


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
    # Keep a tiny sidecar so HUD widgets never load the full list just for count/preview
    last_text = notes[-1]["text"] if notes else ""
    atomic_save(NOTES_META_FILE, {
        "count": len(notes),
        "last_text": last_text[:120],
    })


def get_notes_meta() -> dict:
    """Return {count, last_text} without loading the full notes list."""
    if not os.path.exists(NOTES_META_FILE):
        # Cold start: build sidecar from main file
        notes = load_notes()
        if notes:
            save_notes(notes)
            return {"count": len(notes), "last_text": notes[-1]["text"][:120]}
        return {"count": 0, "last_text": ""}
    try:
        with open(NOTES_META_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"count": 0, "last_text": ""}
