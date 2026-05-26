"""
watcher.py — The Watcher: system monitor, compliance enforcer, presentation layer.

Observes all bot output. Enforces permission rules. Cannot be interacted with by bots.
Presents output to the operator. Maintains system health awareness.
"""

import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional


@dataclass
class SystemHealth:
    anthropic_api: bool = False
    memory_layer: bool = False
    music_system: bool = False
    bot_online: bool = False

    @property
    def all_online(self) -> bool:
        return self.anthropic_api and self.memory_layer and self.bot_online

    def render_line(self) -> str:
        checks = [
            ("API", self.anthropic_api),
            ("MEM", self.memory_layer),
            ("♪",   self.music_system),
            ("BOT", self.bot_online),
        ]
        parts = []
        for label, ok in checks:
            color = "#00c040" if ok else "#c03040"
            dot = "●" if ok else "○"
            parts.append(f"[{color}]{dot} {label}[/{color}]")
        return "  ".join(parts)


@dataclass
class WatcherFlag:
    timestamp: str
    severity: str   # "info" | "warning" | "violation"
    message: str
    bot_name: str = "SYSTEM"

    def render(self) -> str:
        colors = {"info": "#5f87af", "warning": "#e8a020", "violation": "#c03040"}
        color = colors.get(self.severity, "#5f87af")
        return f"[{color}][{self.timestamp}] {self.severity.upper()} — {self.message}[/{color}]"


@dataclass
class PresentationItem:
    bot_name: str
    output_type: str
    content: str
    timestamp: str
    presented: bool = False


class Watcher:
    """
    The Watcher monitors all systems and bots cannot reach it.
    It presents output, enforces permission boundaries, and observes health.
    There is nothing to negotiate with.
    """

    def __init__(self) -> None:
        self._health = SystemHealth()
        self._flags: list[WatcherFlag] = []
        self._queue: deque[PresentationItem] = deque(maxlen=30)
        self._last_check: str = "never"
        self._flag_callbacks: list[Callable] = []

    # ── health monitoring ─────────────────────────────────────────────────────

    def check_health(self, bot=None) -> SystemHealth:
        """Synchronous health check of all system components."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._health.anthropic_api = bool(
            api_key and "your-key" not in api_key.lower() and len(api_key) > 20
        )
        self._health.memory_layer = os.path.exists("data/")
        self._health.music_system = os.path.exists("assets/vicecity.m4a")
        self._health.bot_online = bot is not None and hasattr(bot, "persona")
        self._last_check = datetime.now().strftime("%H:%M:%S")
        return self._health

    # ── compliance ────────────────────────────────────────────────────────────

    def check_compliance(self, bot_name: str, action: str, trust_level: int) -> bool:
        """Verify bot action is within its trust level. Returns True if allowed."""
        import permissions
        if not permissions.can(trust_level, action):
            self._raise_flag(
                f"{bot_name} attempted '{action}' — exceeds trust level {trust_level}.",
                severity="violation",
                bot_name=bot_name,
            )
            return False
        return True

    # ── presentation queue ────────────────────────────────────────────────────

    def submit(self, bot_name: str, output_type: str, content: str) -> PresentationItem:
        """Bots submit output here. The Watcher queues it for presentation."""
        item = PresentationItem(
            bot_name=bot_name,
            output_type=output_type,
            content=content,
            timestamp=datetime.now().strftime("%H:%M"),
        )
        self._queue.append(item)
        return item

    def next_presentation(self) -> Optional[PresentationItem]:
        """Return the next unshown item from the queue."""
        for item in self._queue:
            if not item.presented:
                item.presented = True
                return item
        return None

    # ── flagging ──────────────────────────────────────────────────────────────

    def _raise_flag(self, message: str, severity: str = "info", bot_name: str = "SYSTEM") -> None:
        flag = WatcherFlag(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            severity=severity,
            message=message,
            bot_name=bot_name,
        )
        self._flags.append(flag)
        for cb in self._flag_callbacks:
            try:
                cb(flag)
            except Exception:
                pass

    def flag(self, message: str, severity: str = "info") -> None:
        self._raise_flag(message, severity)

    def on_flag(self, callback: Callable) -> None:
        self._flag_callbacks.append(callback)

    # ── accessors ─────────────────────────────────────────────────────────────

    @property
    def health(self) -> SystemHealth:
        return self._health

    @property
    def recent_flags(self) -> list[WatcherFlag]:
        return self._flags[-5:]

    @property
    def flag_count(self) -> int:
        return len(self._flags)

    @property
    def queue_depth(self) -> int:
        return sum(1 for item in self._queue if not item.presented)

    @property
    def last_check(self) -> str:
        return self._last_check
