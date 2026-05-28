"""
memory.py — Session memory for CyberVice bot personas.

Each session's judgments are compressed into a summary and persisted.
On the next session, recent summaries are injected into the bot's system prompt.
This creates continuity — the bot remembers what you valued, not just what it said.
"""

import json
import os
from datetime import datetime
from typing import Any, Optional

from storage import atomic_save

MEMORY_FILE = "data/bot_memory.json"
_MAX_SUMMARIES = 12   # total summaries kept on disk
_PROMPT_SUMMARIES = 5 # how many get injected into each prompt


class MemoryManager:
    def __init__(self) -> None:
        self._summaries: list[dict] = []
        self._session_judgments: list[dict] = []
        self._session_start = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._last_output_preview: str = ""
        self._daily_calls: int = 0
        self._call_date: str = ""
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not os.path.exists(MEMORY_FILE):
            return
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self._summaries = data.get("summaries", [])[-_MAX_SUMMARIES:]
            self._last_output_preview = data.get("last_output_preview", "")
            self._daily_calls = data.get("daily_calls", 0)
            self._call_date = data.get("call_date", "")
        except Exception:
            pass

    def _save(self) -> None:
        atomic_save(MEMORY_FILE, {
            "summaries": self._summaries,
            "last_output_preview": self._last_output_preview,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "daily_calls": self._daily_calls,
            "call_date": self._call_date,
        })

    # ── session recording ─────────────────────────────────────────────────────

    def record_judgment(self, output_type: str, verdict: str, content_preview: str) -> None:
        self._session_judgments.append({
            "type": output_type,
            "verdict": verdict,
            "time": datetime.now().strftime("%H:%M"),
            "preview": content_preview[:80],
        })
        if verdict == "approved":
            self._last_output_preview = content_preview[:120]

    def close_session(self) -> None:
        """Compress this session to a summary and persist. Call on app exit."""
        if not self._session_judgments:
            return

        approved = [j for j in self._session_judgments if j["verdict"] == "approved"]
        rejected = [j for j in self._session_judgments if j["verdict"] == "rejected"]
        total = len(self._session_judgments)

        parts = [f"{total} piece(s) judged"]
        if approved:
            types = sorted(set(j["type"] for j in approved))
            parts.append(f"{len(approved)} approved — types: {', '.join(types)}")
        if rejected:
            parts.append(f"{len(rejected)} rejected")
        if approved:
            parts.append(f"last approved: \"{approved[-1]['preview']}\"")
        if rejected:
            parts.append(f"last rejected: \"{rejected[-1]['preview']}\"")

        self._summaries.append({
            "date": self._session_start,
            "summary": ". ".join(parts),
            "total": total,
            "approved": len(approved),
            "rejected": len(rejected),
        })
        self._summaries = self._summaries[-_MAX_SUMMARIES:]
        self._save()

    # ── prompt context ────────────────────────────────────────────────────────

    def get_context_for_prompt(self) -> str:
        """Return recent summaries formatted for injection into a system prompt."""
        recent = self._summaries[-_PROMPT_SUMMARIES:]
        if not recent:
            return ""
        lines = [f"[{s['date']}] {s['summary']}" for s in recent]
        return "\n".join(lines)

    # ── stats ─────────────────────────────────────────────────────────────────

    @property
    def session_judgments(self) -> list[dict]:
        return list(self._session_judgments)

    @property
    def session_judgment_count(self) -> int:
        return len(self._session_judgments)

    @property
    def total_sessions(self) -> int:
        return len(self._summaries)

    @property
    def total_approved(self) -> int:
        return sum(s.get("approved", 0) for s in self._summaries)

    @property
    def calls_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._daily_calls if self._call_date == today else 0

    def increment_daily_calls(self) -> int:
        """Increment today's call count, auto-resetting if the date has changed."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._call_date != today:
            self._daily_calls = 0
            self._call_date = today
        self._daily_calls += 1
        self._save()
        return self._daily_calls

    @property
    def last_output_preview(self) -> str:
        return self._last_output_preview
