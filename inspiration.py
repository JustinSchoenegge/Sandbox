"""
inspiration.py — Operator style corpus for NEON.

Drop any .md or .txt file into data/inspiration/ and NEON absorbs it
permanently into its system prompt. Cached after the first API call
per session — costs nothing on subsequent generations.
"""

import json
import os
from datetime import datetime
from pathlib import Path

INSPIRATION_DIR = "data/inspiration"
_MAX_TOTAL_CHARS = 6000
_MAX_FILE_CHARS  = 2000


def load_corpus() -> str:
    """Return formatted inspiration corpus for system prompt injection."""
    dir_path = Path(INSPIRATION_DIR)
    if not dir_path.exists():
        return ""

    files = sorted(dir_path.glob("*.md")) + sorted(dir_path.glob("*.txt"))
    if not files:
        return ""

    parts: list[str] = []
    total = 0

    for path in files:
        if total >= _MAX_TOTAL_CHARS:
            break
        try:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            remaining = _MAX_TOTAL_CHARS - total
            chunk = text[: min(_MAX_FILE_CHARS, remaining)]
            parts.append(f"[{path.stem}]\n{chunk}")
            total += len(chunk)
        except Exception:
            continue

    return "\n\n".join(parts)


def file_count() -> int:
    """Number of inspiration files present."""
    dir_path = Path(INSPIRATION_DIR)
    if not dir_path.exists():
        return 0
    return len(list(dir_path.glob("*.md")) + list(dir_path.glob("*.txt")))


def export_notes(notes_path: str = "data/notes.json") -> str:
    """
    Export notes.json to data/inspiration/notes_export.md.
    Skips junk entries (< 4 chars). Returns path written.
    """
    dir_path = Path(INSPIRATION_DIR)
    dir_path.mkdir(parents=True, exist_ok=True)

    try:
        with open(notes_path, encoding="utf-8") as f:
            notes: list[dict] = json.load(f)
    except Exception as e:
        return f"[error reading notes: {e}]"

    clean = [
        n for n in notes
        if len(n.get("text", "").strip()) >= 4
    ]

    if not clean:
        return "[no notes to export]"

    lines = [
        f"# Notes Export",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} — {len(clean)} entries_\n",
    ]

    for n in clean:
        ts   = n.get("timestamp", "")
        text = n.get("text", "").strip()
        tags = n.get("tags", [])
        tag_str = "  " + "  ".join(tags) if tags else ""
        lines.append(f"### {ts}{tag_str}")
        lines.append(f"{text}\n")

    out_path = dir_path / "notes_export.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
