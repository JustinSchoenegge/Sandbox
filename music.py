import json
import os

from storage import atomic_save

MUSIC_FILE = "data/music.json"


def load_ideas():
    if not os.path.exists(MUSIC_FILE):
        return []
    try:
        with open(MUSIC_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_ideas(ideas):
    atomic_save(MUSIC_FILE, ideas)
