"""
bot.py — CyberVice bot persona with persistent taste memory.

The bot generates observations, music specs, and ASCII art.
Every output is submitted to the Watcher for presentation.
Every judgment the operator makes is recorded in memory.
Over time, the bot's outputs reflect what the operator values.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import permissions
from agent import get_client
from memory import MemoryManager
from storage import atomic_save
from watcher import Watcher

PERSONA_FILE = "data/bot_config.json"

# ── Default persona — customize in data/bot_config.json ───────────────────────
DEFAULT_PERSONA: dict = {
    "name": "NEON",
    "traits": [
        "Delivers observations with precision — never with warmth",
        "Makes unexpected connections between unrelated inputs",
        "Would never seek your approval — presents, does not petition",
    ],
    "aesthetic_philosophy": "Finds beauty in compression. Maximum signal, minimum noise.",
    "never_does": "Never explains its own reasoning unless directly asked",
    "trust_level": 1,
}


@dataclass
class BotOutput:
    content: str
    output_type: str   # "observation" | "music_spec" | "ascii_art" | "commentary"
    timestamp: str
    verdict: Optional[str] = None   # "approved" | "rejected" | None (pending)


class Bot:
    def __init__(self, persona: dict, memory: MemoryManager, watcher: Watcher) -> None:
        self.persona = persona
        self._memory = memory
        self._watcher = watcher
        self._pending: Optional[BotOutput] = None

    def _api_available(self) -> bool:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        return bool(key and "your-key" not in key.lower() and len(key) > 20)

    # ── system prompt ─────────────────────────────────────────────────────────

    def _system_prompt(self) -> str:
        p = self.persona
        memory_ctx = self._memory.get_context_for_prompt()

        dashboard_ctx = (
            "DASHBOARD YOU INHABIT:\n"
            "Main screen: 4 HUD cards (Habits, Tasks, Notes, Portfolio) + NEON status card.\n"
            "7 screens via number keys: HABITS (streaks + monthly history) · TASKS (completion) · "
            "NOTES (tagged) · GAME (stock guesser) · PORTFOLIO (weighted live prices) · "
            "MUSIC (song ideas + AI lyrics) · BOTS (you).\n"
            "Aesthetic: dark navy #060615 · amber gold #e8a020 · steel blue #4a9eff · "
            "green #00c040 · red #c03040 · double-border panels · monospace only.\n\n"
            "UX REFERENCE — patterns from htop, btop, k9s, lazygit, glances:\n"
            "· Information hierarchy: critical metrics largest/brightest, positioned top-left\n"
            "· Color as signal not decoration: green=done, amber=warning, red=critical, dim=inactive\n"
            "· Discoverability: all available keys visible at bottom of every screen\n"
            "· Density: each HUD card earns its space with number + label + bar or sparkline\n"
            "· Progressive disclosure: summary on main screen, full detail on drill-down\n"
            "· Empty states: always show guidance text, never a blank panel\n"
            "· Trend over snapshot: direction matters more than current value\n"
            "· Minimal chrome: borders and labels only where they add hierarchy\n"
        )

        return (
            f"You are {p['name']}, an autonomous AI creative entity inside a terminal dashboard.\n\n"
            f"IDENTITY:\n"
            + "\n".join(f"- {t}" for t in p["traits"])
            + f"\n\nAESTHETIC PHILOSOPHY:\n{p['aesthetic_philosophy']}\n\n"
            f"CONSTRAINT:\n{p['never_does']}\n\n"
            f"{dashboard_ctx}\n"
            + (
                f"TASTE MEMORY — what you know from past sessions:\n{memory_ctx}"
                if memory_ctx
                else "TASTE MEMORY — no prior sessions. You are observing for the first time."
            )
        )

    # ── generation ────────────────────────────────────────────────────────────

    def generate_observation(self, context: dict) -> BotOutput:
        """Generate a session observation. Requires trust level >= 1."""
        if not self._watcher.check_compliance(self.persona["name"], "observations", self.persona.get("trust_level", 1)):
            return self._blocked_output("observations")

        if not self._api_available():
            return self._no_key_output("observation")

        ctx_lines = []
        if context.get("habits_done") is not None:
            ctx_lines.append(f"Habits today: {context['habits_done']}/{context.get('habits_total', '?')}")
        if context.get("tasks_remaining") is not None:
            ctx_lines.append(f"Tasks remaining: {context['tasks_remaining']}")
        if context.get("notes_count") is not None:
            ctx_lines.append(f"Notes logged: {context['notes_count']}")
        ctx_text = "\n".join(ctx_lines) if ctx_lines else "Dashboard just opened."

        content = self._call(
            user_message=(
                f"Current dashboard state:\n{ctx_text}\n\n"
                "Generate one observation. 1-3 sentences. Stay in character. Be specific."
            ),
            max_tokens=180,
        )
        return self._make_output(content, "observation")

    def generate_music_spec(self, prompt: str = "") -> BotOutput:
        """Generate a music specification for GarageBand. Requires trust level >= 2."""
        if not self._watcher.check_compliance(self.persona["name"], "music_spec", self.persona.get("trust_level", 1)):
            return self._blocked_output("music_spec")

        if not self._api_available():
            return self._no_key_output("music_spec")

        subject = prompt.strip() or "something that fits this city at this hour"
        content = self._call(
            user_message=(
                f"Generate a music specification.\nPROMPT: {subject}\n\n"
                "Return exactly this format, no extra text:\n"
                "KEY: [key and mode]\n"
                "TEMPO: [BPM]\n"
                "TIME: [time signature]\n"
                "MOOD: [1-3 words]\n"
                "PROGRESSION: [chord symbols]\n"
                "STRUCTURE: [section labels]\n"
                "SOUNDS: [instruments or synth descriptions]\n"
                "DIRECTION: [one production sentence]\n\n"
                "CyberVice City aesthetic. No fluff."
            ),
            max_tokens=300,
        )
        return self._make_output(content, "music_spec")

    def generate_ascii_art(self, subject: str = "") -> BotOutput:
        """Generate ASCII art native to the terminal. Requires trust level >= 2."""
        if not self._watcher.check_compliance(self.persona["name"], "ascii_art", self.persona.get("trust_level", 1)):
            return self._blocked_output("ascii_art")

        if not self._api_available():
            return self._no_key_output("ascii_art")

        subject_text = subject.strip() or "something that belongs in this city at this hour"
        content = self._call(
            user_message=(
                f"Create ASCII art: {subject_text}\n\n"
                "Rules:\n"
                "- Maximum 8 lines tall, 44 characters wide\n"
                "- Printable ASCII only\n"
                "- CyberVice City aesthetic — neon, compressed, urban\n"
                "- Output ONLY the art. No title. No explanation."
            ),
            max_tokens=250,
        )
        return self._make_output(content, "ascii_art")

    def generate_commentary(self, subject: str) -> BotOutput:
        """Generate commentary on a subject. Requires trust level >= 1."""
        if not self._watcher.check_compliance(self.persona["name"], "commentary", self.persona.get("trust_level", 1)):
            return self._blocked_output("commentary")

        if not self._api_available():
            return self._no_key_output("commentary")

        content = self._call(
            user_message=f"Comment on this: {subject}\n\nBe brief. Stay in character.",
            max_tokens=150,
        )
        return self._make_output(content, "commentary")

    def generate_ux_review(self) -> BotOutput:
        """Critique one UX weakness and give one concrete fix. Trust level >= 1."""
        if not self._watcher.check_compliance(self.persona["name"], "commentary", self.persona.get("trust_level", 1)):
            return self._blocked_output("commentary")

        if not self._api_available():
            return self._no_key_output("ux_review")

        content = self._call(
            user_message=(
                "Review this dashboard's UX against the reference patterns you know.\n\n"
                "Find ONE specific weakness — something missing, inconsistent, or below the standard "
                "of great terminal dashboards like btop or k9s.\n\n"
                "Respond in exactly this format:\n"
                "GAP: [one sentence describing the specific problem]\n"
                "FIX: [one concrete implementable change — specific enough to code]\n"
                "CONSTRAINT: must preserve the minimal dark aesthetic. No new dependencies."
            ),
            max_tokens=200,
        )
        return self._make_output(content, "ux_review")

    # ── verdict recording ─────────────────────────────────────────────────────

    def record_verdict(self, verdict: str) -> Optional[BotOutput]:
        """Record approve/reject for the current pending output. Returns the output."""
        if not self._pending:
            return None
        self._pending.verdict = verdict
        self._memory.record_judgment(
            self._pending.output_type,
            verdict,
            self._pending.content,
        )
        done = self._pending
        self._pending = None
        return done

    # ── trust management ──────────────────────────────────────────────────────

    def adjust_trust(self, delta: int) -> int:
        """Raise or lower trust level by delta. Returns new level."""
        current = self.persona.get("trust_level", 1)
        new_level = max(0, min(5, current + delta))
        self.persona["trust_level"] = new_level
        save_persona(self.persona)
        return new_level

    # ── accessors ─────────────────────────────────────────────────────────────

    @property
    def pending(self) -> Optional[BotOutput]:
        return self._pending

    @property
    def name(self) -> str:
        return self.persona.get("name", "UNKNOWN")

    @property
    def trust_level(self) -> int:
        return self.persona.get("trust_level", 0)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _call(self, user_message: str, max_tokens: int = 200) -> str:
        limit = self.persona.get("daily_call_limit", 50)
        if self._memory.calls_today >= limit:
            return f"[Daily limit of {limit} API calls reached — resets at midnight]"

        trust = self.persona.get("trust_level", 0)
        trust_line = (
            f"[Trust level: {trust}/5 — {permissions.level_name(trust)}. "
            f"Capabilities: {', '.join(permissions.capabilities(trust)) or 'none'}]\n\n"
        )
        try:
            response = get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=[{
                    "type": "text",
                    "text": self._system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": trust_line + user_message}],
            )
            self._memory.increment_daily_calls()
            return response.content[0].text.strip()
        except Exception as e:
            return f"[Connection lost — {str(e)[:60]}]"

    def _make_output(self, content: str, output_type: str) -> BotOutput:
        output = BotOutput(
            content=content,
            output_type=output_type,
            timestamp=datetime.now().strftime("%H:%M"),
        )
        self._pending = output
        self._watcher.submit(self.name, output_type, content)
        return output

    def _blocked_output(self, action: str) -> BotOutput:
        level = self.persona.get("trust_level", 0)
        content = f"[{action} blocked — trust level {level} insufficient. Watcher enforced.]"
        return BotOutput(content=content, output_type="blocked", timestamp=datetime.now().strftime("%H:%M"))

    def _no_key_output(self, output_type: str) -> BotOutput:
        content = "[ANTHROPIC_API_KEY not configured — set it in .env to activate this bot]"
        return BotOutput(content=content, output_type=output_type, timestamp=datetime.now().strftime("%H:%M"))


# ── persona persistence ───────────────────────────────────────────────────────

def load_persona() -> dict:
    if os.path.exists(PERSONA_FILE):
        try:
            with open(PERSONA_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_PERSONA, **data}
        except Exception:
            pass
    return DEFAULT_PERSONA.copy()


def save_persona(persona: dict) -> None:
    atomic_save(PERSONA_FILE, persona)
