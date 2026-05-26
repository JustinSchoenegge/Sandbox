"""
storage.py — atomic JSON I/O for all data files.

Every write goes through atomic_save():
  1. Write JSON to a sibling .tmp file in the same directory
  2. os.replace() — atomic rename on POSIX; readers always see a complete file
  3. If the process crashes mid-write, only the .tmp is affected; the original is intact

Multi-agent note: concurrent readers are safe because os.replace is atomic.
Concurrent writers should coordinate externally (e.g. fcntl.flock) if true
simultaneous writes are needed — upgrade this layer then, not each call site.
"""

import json
import os
import tempfile


def load_json(path: str, default=None):
    """Load and parse JSON from path. Returns default on missing file or parse error."""
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def atomic_save(path: str, data) -> None:
    """Serialize data to JSON and write to path atomically.

    Writes to a temp file in the same directory as path, then renames.
    Concurrent readers always see either the old or the new complete file —
    never a partial write.
    """
    abs_path = os.path.abspath(path)
    dir_name = os.path.dirname(abs_path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        os.chmod(tmp_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, abs_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
