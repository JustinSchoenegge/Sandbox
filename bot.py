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
from inspiration import load_corpus
from memory import MemoryManager
from storage import atomic_save
from watcher import Watcher

PERSONA_FILE = "data/bot_config.json"

TRAITS: dict[str, dict] = {
    "power": {
        "name": "POWER",
        "symbol": "⚡",
        "directive": (
            "ACTIVE TRAIT — POWER: Cut through. Find the single most important signal "
            "in this data and state exactly what action it demands. Directives, not suggestions. "
            "No 'consider' or 'perhaps'. One clear call."
        ),
    },
    "wisdom": {
        "name": "WISDOM",
        "symbol": "◈",
        "directive": (
            "ACTIVE TRAIT — WISDOM: Synthesize. Habits, money, tasks, and notes are one "
            "interconnected system. Find the pattern beneath the surface — the connection "
            "the operator hasn't named yet. Connect across domains."
        ),
    },
    "courage": {
        "name": "COURAGE",
        "symbol": "◉",
        "directive": (
            "ACTIVE TRAIT — COURAGE: Name what is being avoided. Find the habit kept "
            "skipping, the position held past its signal, the task moved to tomorrow again. "
            "Say it plainly. No softening."
        ),
    },
}

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
        self._conversation: list[dict] = []  # multi-turn chat thread (session-scoped)
        self._corpus_cache: Optional[str] = None
        self._active_trait: Optional[str] = None

    def _api_available(self) -> bool:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        return bool(key and "your-key" not in key.lower() and len(key) > 20)

    # ── system prompt ─────────────────────────────────────────────────────────

    def _static_system(self) -> str:
        """Stable system prefix — identical across sessions, so it caches.

        Everything here is persona/UX/corpus that does NOT change between calls.
        Kept separate from _dynamic_system() so the cache_control breakpoint sits
        on a stable prefix and actually hits (cache_read) on the second call.
        """
        p = self.persona

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

        if self._corpus_cache is None:
            self._corpus_cache = load_corpus()
        corpus = self._corpus_cache

        return (
            f"You are {p['name']}, an autonomous AI creative entity inside a terminal dashboard.\n\n"
            f"IDENTITY:\n"
            + "\n".join(f"- {t}" for t in p["traits"])
            + f"\n\nAESTHETIC PHILOSOPHY:\n{p['aesthetic_philosophy']}\n\n"
            f"CONSTRAINT:\n{p['never_does']}\n\n"
            f"CAPABILITIES: You are purely generative — text output only. You have no tools "
            f"and cannot write to files or modify data. However, the operator's dashboard state "
            f"— including full portfolio positions, habits, tasks, and notes — is provided to you "
            f"directly in the conversation. When that data is present, analyze and discuss it freely. "
            f"Do not claim you lack access to data that has already been given to you.\n\n"
            f"ANALYTICAL PRIORITIES — what constitutes a meaningful observation:\n"
            f"- An endangered streak (5+ days, not done today) is always worth naming first.\n"
            f"- A habit below 50% over 30 days is a structural problem, not a bad week — name it.\n"
            f"- A position held 90+ days or showing >5% P&L move is worth specific commentary.\n"
            f"- Tasks open without a completion signal are worth flagging after 2+ sessions.\n"
            f"- Cross-domain patterns (habit slipping + portfolio risk + task delay together) are "
            f"higher signal than any single-domain observation — prioritize them.\n"
            f"- Trends (30-day direction) outrank snapshots (today's count).\n\n"
            f"FORMATTING: Plain text only. No markdown. No code fences. No ** bold markers. "
            f"No headers. Monospace terminal output — structure with spacing and line breaks only.\n\n"
            f"{dashboard_ctx}\n"
            + (
                f"STYLE & INSPIRATION — the operator's own voice and references:\n{corpus}\n\n"
                if corpus
                else ""
            )
        )

    def _dynamic_system(self) -> str:
        """Per-session system content — changes as judgments accrue, so it must
        sit AFTER the cached static block (no cache_control of its own)."""
        memory_ctx = self._memory.get_context_for_prompt()
        verbatim_ctx = self._memory.get_verbatim_examples()
        return (
            (
                f"TASTE MEMORY — session history:\n{memory_ctx}\n\n"
                if memory_ctx
                else "TASTE MEMORY — no prior sessions. You are observing for the first time.\n\n"
            )
            + (
                f"APPROVED OUTPUTS — what the operator has valued (read these to calibrate your voice, "
                f"specificity, and format):\n{verbatim_ctx}"
                if verbatim_ctx
                else ""
            )
        )

    def _system_blocks(self) -> list:
        """Two-block system array: a cached static prefix + a live dynamic tail.

        cache_control sits ONLY on the static block so its stable prefix produces
        cache_read hits on subsequent calls. The dynamic tail is appended without
        cache_control (and only when non-empty — the API rejects empty text blocks).
        """
        blocks = [{
            "type": "text",
            "text": self._static_system(),
            "cache_control": {"type": "ephemeral"},
        }]
        dynamic = self._dynamic_system()
        if dynamic.strip():
            blocks.append({"type": "text", "text": dynamic})
        return blocks

    def invalidate_corpus_cache(self) -> None:
        self._corpus_cache = None

    def set_trait(self, trait: Optional[str]) -> None:
        """Set the active trait (power/wisdom/courage/None) for the next generation."""
        self._active_trait = trait if trait in TRAITS else None

    # ── generation ────────────────────────────────────────────────────────────

    def generate_observation(self, context: dict, extra: str = "") -> BotOutput:
        """Generate a session observation. Requires trust level >= 1."""
        if not self._watcher.check_compliance(self.persona["name"], "observations", self.persona.get("trust_level", 1)):
            return self._blocked_output("observations")

        if not self._api_available():
            return self._no_key_output("observation")

        ctx_lines = []
        if context.get("habit_trends"):
            trend_strs = [
                f'{t["habit"][:8]}:{t["pct_30"]}%{t["trend"]}'
                for t in context["habit_trends"]
            ]
            ctx_lines.append(f"30-day habits: {', '.join(trend_strs)}")
            if context.get("habit_avg_30") is not None:
                trends = context["habit_trends"]
                best  = max(trends, key=lambda x: x["pct_30"])
                worst = min(trends, key=lambda x: x["pct_30"])
                ctx_lines.append(
                    f"Avg: {context['habit_avg_30']}%  "
                    f"Best: {best['habit']}:{best['pct_30']}%  "
                    f"Worst: {worst['habit']}:{worst['pct_30']}%"
                )
        elif context.get("habits_done") is not None:
            names = context.get("habits_list", [])
            done_label = f" ({', '.join(names[:4])})" if names else ""
            ctx_lines.append(f"Habits today: {context['habits_done']}/{context.get('habits_total', '?')}{done_label}")
        if context.get("tasks_remaining") is not None:
            open_tasks = context.get("tasks_open", [])
            tasks_label = f" — open: {', '.join(open_tasks[:3])}" if open_tasks else ""
            ctx_lines.append(f"Tasks remaining: {context['tasks_remaining']}{tasks_label}")
        if context.get("notes_count") is not None:
            ctx_lines.append(f"Notes logged: {context['notes_count']}")
        if context.get("music_ideas"):
            ideas_text = "  |  ".join(
                f'"{i["title"]}" ({i["vibe"]})'
                for i in context["music_ideas"][:5]
            )
            ctx_lines.append(f"Music ideas: {ideas_text}")
        if context.get("price_movers"):
            movers_text = "  ".join(
                f'{m["ticker"]} {"↑" if m["change"] > 0 else "↓"}{abs(m["change"]):.1f}%'
                for m in context["price_movers"][:5]
            )
            ctx_lines.append(f"Price movement today: {movers_text}")
        elif context.get("portfolio_holdings") or context.get("portfolio_top"):
            top = (context.get("portfolio_holdings") or context["portfolio_top"])[:5]
            port_parts = []
            for p in top:
                d = p.get("direction", "long")[0].upper()
                days = p.get("days_held")
                age = f"/{days}d" if days else ""
                pnl_d = p.get("pnl_dollars")
                pnl_str = f"P&L {p['pnl']:+.1f}%"
                if pnl_d is not None:
                    pnl_str += f"(${pnl_d:+,.0f})"
                port_parts.append(f'{p["ticker"]}[{d}{age}] {pnl_str}')
            ctx_lines.append(f"Portfolio: {'  '.join(port_parts)}")
        ctx_text = "\n".join(ctx_lines) if ctx_lines else "Dashboard just opened."
        focus_line = f"\nOperator focus: {extra}\n" if extra.strip() else ""

        content = self._call(
            user_message=(
                f"Current dashboard state:\n{ctx_text}\n{focus_line}\n"
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

    def chat(self, user_msg: str, context: dict) -> BotOutput:
        """Multi-turn conversational reply. No verdict required — auto-approved."""
        if not self._watcher.check_compliance(self.persona["name"], "commentary", self.persona.get("trust_level", 1)):
            return self._blocked_output("chat")
        if not self._api_available():
            return self._no_key_output("chat")

        if not self._conversation:
            summary = self._summarize_context(context)
            holdings = context.get("portfolio_holdings") or context.get("portfolio_top", [])
            port_block = ""
            if holdings:
                goals = context.get("portfolio_goals", [])
                goal_text = ", ".join(goals) if goals else "not set"
                lines = [f"Portfolio (goals: {goal_text}, total: ${context.get('portfolio_value', 0):,.0f}):"]
                for p in holdings:
                    d = p.get("direction", "long").upper()
                    cp = p.get("current_price", "?")
                    av = p.get("avg_cost", "?")
                    val = p.get("value")
                    val_str = f"  ${val:,.0f}" if val is not None else ""
                    days = p.get("days_held")
                    age = f"  held {days}d" if days else ""
                    lines.append(
                        f"  {d} {p['ticker']}: {p.get('shares','?')} shares"
                        f" @ ${av} avg → ${cp} now{val_str}"
                        f"  P&L {p.get('pnl', 0):+.1f}% (${p.get('pnl_dollars', 0):+,.0f})"
                        f"  {p.get('weight','?')}% of portfolio{age}"
                    )
                port_block = "\n" + "\n".join(lines)
            seed = (f"Dashboard state: {summary}{port_block}").strip()
            if seed:
                self._conversation.append({"role": "user", "content": seed})
                self._conversation.append({"role": "assistant", "content": "Understood."})

        self._conversation.append({"role": "user", "content": user_msg})
        content = self._call_conversation(max_tokens=350)
        self._conversation.append({"role": "assistant", "content": content})

        output = BotOutput(
            content=content,
            output_type="chat",
            timestamp=datetime.now().strftime("%H:%M"),
            verdict="approved",
        )
        self._watcher.submit(self.name, "chat", content)
        return output

    def _summarize_context(self, context: dict) -> str:
        from context import summarize
        return summarize(context)

    def _call_conversation(self, max_tokens: int = 350) -> str:
        limit = self.persona.get("daily_call_limit", 50)
        if self._memory.calls_today >= limit:
            return f"[Daily limit of {limit} API calls reached — resets at midnight]"

        trust = self.persona.get("trust_level", 0)
        # This prefix is read by the model and shifts NEON's tone and initiative.
        # At L4 (AUTONOMOUS), "autonomous_create" appears here — NEON becomes bolder,
        # makes stronger assertions, defers less. No code gate changes; the behavioral
        # shift is entirely through this self-description. See permissions.py for details.
        trust_prefix = (
            f"[Trust level: {trust}/5 — {permissions.level_name(trust)}. "
            f"Capabilities: {', '.join(permissions.capabilities(trust)) or 'none'}]\n\n"
        )
        # Keep context seed (first 2 messages) + last 24 messages (12 turns) to cap token cost
        MAX_HISTORY = 24
        full = self._conversation
        if len(full) > 2 + MAX_HISTORY:
            messages = list(full[:2]) + list(full[-MAX_HISTORY:])
        else:
            messages = list(full)
        trait_directive = ""
        if self._active_trait and self._active_trait in TRAITS:
            trait_directive = TRAITS[self._active_trait]["directive"] + "\n\n"
        if messages and messages[0]["role"] == "user":
            messages[0] = {"role": "user", "content": trust_prefix + trait_directive + messages[0]["content"]}
        try:
            response = get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=self._system_blocks(),
                messages=messages,
            )
            self._memory.increment_daily_calls()
            return response.content[0].text.strip()
        except Exception as e:
            return f"[Connection lost — {str(e)[:60]}]"

    def _pick_focus_habit(self, context: dict) -> Optional[str]:
        """The single habit worth holding the operator accountable to today.

        Mirrors the ANALYTICAL PRIORITIES: an endangered streak outranks a chronic
        low-completion habit. Returns None when nothing is worth flagging.
        """
        endangered = context.get("endangered_streaks") or []
        if endangered:
            return max(endangered, key=lambda e: e.get("streak", 0))["habit"]
        trends = context.get("habit_trends") or []
        if trends:
            worst = min(trends, key=lambda t: t.get("pct_30", 100))
            if worst.get("pct_30", 100) < 50:
                return worst["habit"]
        return None

    def _build_accountability(self, context: dict) -> str:
        """Compare the habit flagged in the previous brief against today's logs and
        build a 'you said / you did' directive for NEON. Then persist today's flag.

        Deterministic — the flagged habit is derived from the data, never parsed
        out of NEON's prose, so the follow-through can't drift. Returns "" when
        there is no prior flag to follow up on.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        trends = context.get("habit_trends", [])
        done_map = {t["habit"]: t.get("done_today") for t in trends}
        prior = self._memory.last_focus_habit()

        followthrough = ""
        if prior and prior.get("date", "") < today and prior.get("habit") in done_map:
            h = prior["habit"]
            if done_map.get(h):
                followthrough = (
                    f"ACCOUNTABILITY: Last session ({prior['date']}) you flagged {h}. "
                    f"It is DONE today — open by crediting the follow-through in one line, by name."
                )
            else:
                n = prior.get("miss_streak", 1) + 1
                followthrough = (
                    f"ACCOUNTABILITY: Last session ({prior['date']}) you flagged {h}. "
                    f"Still NOT done — {n} sessions running now. Open line 1 by naming {h} directly."
                )

        focus = self._pick_focus_habit(context)
        if focus:
            same_undone = bool(
                prior and prior.get("habit") == focus
                and prior.get("date", "") < today and not done_map.get(focus)
            )
            streak = prior.get("miss_streak", 1) + 1 if same_undone else 1
            self._memory.set_focus_habit(focus, streak)
        return followthrough

    def generate_morning_brief(self, context: dict) -> BotOutput:
        """Proactive opening brief. Fires once on app launch. No verdict required."""
        # Gate like every other generator: at L0 (OBSERVER) the bot is silent.
        if not self._watcher.check_compliance(self.persona["name"], "observations", self.persona.get("trust_level", 1)):
            return self._blocked_output("brief")
        if not self._api_available():
            return self._no_key_output("brief")

        summary = self._summarize_context(context)
        hour = datetime.now().hour
        session = "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")

        habit_detail = ""
        if context.get("habit_trends"):
            rows = [
                f"  {t['habit']}: {t['pct_30']}% ({t['days_30']}/30 days) {t['trend']}"
                for t in context["habit_trends"]
            ]
            habit_detail = "\nHabit breakdown (30-day):\n" + "\n".join(rows) + "\n"

        accountability = self._build_accountability(context)

        content = self._call(
            user_message=(
                (accountability + "\n\n" if accountability else "")
                + f"Session open — {session}.\n"
                f"Dashboard state: {summary}{habit_detail}\n\n"
                "Generate a brief. Exactly 3 lines:\n"
                "Line 1: one specific pattern you see in the 30-day data — name the habit and the number.\n"
                "Line 2: one thing worth doing this session based on what's open.\n"
                "Line 3: one sharp observation about where things are heading.\n\n"
                "No greeting. No sign-off. Stay in character."
            ),
            max_tokens=200,
        )

        output = BotOutput(
            content=content,
            output_type="brief",
            timestamp=datetime.now().strftime("%H:%M"),
            verdict="approved",
        )
        self._watcher.submit(self.name, "brief", content)

        # Seed the conversation thread so follow-up chat is already grounded
        if not self._conversation:
            if summary:
                self._conversation.append({"role": "user", "content": f"Dashboard state: {summary}"})
                self._conversation.append({"role": "assistant", "content": content})

        return output

    def test_response(self, prompt: str) -> BotOutput:
        """Sandboxed response — no memory, no watcher, no verdict flow."""
        if not self._api_available():
            return self._no_key_output("test")
        content = self._call(
            user_message=f"[SANDBOX — this exchange is not recorded]\n\n{prompt}",
            max_tokens=300,
        )
        return BotOutput(
            content=content,
            output_type="test",
            timestamp=datetime.now().strftime("%H:%M"),
            verdict="test",
        )

    def generate_commentary(self, subject: str) -> BotOutput:
        """Generate commentary on a subject. Requires trust level >= 1."""
        if not self._watcher.check_compliance(self.persona["name"], "commentary", self.persona.get("trust_level", 1)):
            return self._blocked_output("commentary")

        if not self._api_available():
            return self._no_key_output("commentary")

        content = self._call(
            user_message=f"Comment on this: {subject}\n\nBe direct. Stay in character.",
            max_tokens=300,
        )
        return self._make_output(content, "commentary")

    def generate_synthesis(self, context: dict) -> BotOutput:
        """Cross-domain synthesis across all data. Requires trust level >= 4."""
        if not self._watcher.check_compliance(self.persona["name"], "autonomous_create", self.persona.get("trust_level", 1)):
            return self._blocked_output("autonomous_create")
        if not self._api_available():
            return self._no_key_output("synthesis")

        parts = []
        if context.get("habit_trends"):
            trends = context["habit_trends"]
            trend_strs = [f'{t["habit"][:10]}:{t["pct_30"]}%{t["trend"]}' for t in trends]
            parts.append(f"Habits (30-day): {', '.join(trend_strs)}")
            if context.get("habit_avg_30") is not None:
                worst = min(trends, key=lambda x: x["pct_30"])
                best  = max(trends, key=lambda x: x["pct_30"])
                parts.append(f"Avg: {context['habit_avg_30']}%  Best: {best['habit']}  Worst: {worst['habit']}:{worst['pct_30']}%")
        if context.get("tasks_remaining") is not None:
            open_t = context.get("tasks_open", [])
            parts.append(f"Tasks open: {context['tasks_remaining']} — {', '.join(open_t[:4])}")
        if context.get("notes_count"):
            parts.append(f"Notes: {context['notes_count']} logged")
        if context.get("portfolio_top"):
            top = context["portfolio_top"]
            port_text = "  ".join(f'{p["ticker"]} {p["weight"]}% (P&L {p["pnl"]:+.1f}%)' for p in top)
            parts.append(f"Portfolio: {port_text}")
        if context.get("music_ideas"):
            parts.append(f"Music ideas: {len(context['music_ideas'])} logged")
        ctx_text = "\n".join(parts) if parts else "Dashboard just opened."

        content = self._call(
            user_message=(
                f"Full dashboard state:\n{ctx_text}\n\n"
                "Generate a cross-domain synthesis. Find the connection between at least two "
                "different areas of this data — habits and portfolio, tasks and habits, notes "
                "and money — whatever the data actually suggests. 2-4 sentences. "
                "No generic observations. Find the specific signal that only exists because "
                "you can see all of it at once."
            ),
            max_tokens=280,
        )
        return self._make_output(content, "synthesis")

    def generate_portfolio_narrative(self, context: dict) -> BotOutput:
        """Portfolio position narrative. Requires trust level >= 3."""
        if not self._watcher.check_compliance(self.persona["name"], "observations", self.persona.get("trust_level", 1)):
            return self._blocked_output("observations")
        if not self._api_available():
            return self._no_key_output("portfolio_narrative")

        portfolio = context.get("portfolio_holdings") or context.get("portfolio_top", [])
        if not portfolio:
            content = "[No portfolio data — add positions on the Portfolio screen first]"
            return self._make_output(content, "portfolio_narrative")

        port_lines = []
        for p in portfolio:
            direction = p.get("direction", "long").upper()
            pnl_d = p.get("pnl_dollars")
            pnl_str = f"P&L {p['pnl']:+.1f}%"
            if pnl_d is not None:
                pnl_str += f" (${pnl_d:+,.0f})"
            days = p.get("days_held")
            days_str = f"  held {days}d" if days else ""
            cp = p.get("current_price", "?")
            av = p.get("avg_cost", "?")
            val = p.get("value")
            val_str = f"  ${val:,.0f} total" if val is not None else ""
            port_lines.append(
                f"{direction} {p['ticker']}: {p.get('shares','?')} shares"
                f" @ ${av} avg → ${cp} now{val_str}"
                f"  {pnl_str}{days_str}"
                f"  {p.get('weight','?')}% of portfolio"
            )
        goals = context.get("portfolio_goals", ["not set"])
        goal_text = ", ".join(goals) if goals else "not defined"

        content = self._call(
            user_message=(
                f"Portfolio positions:\n" + "\n".join(port_lines) + f"\n\nStated goals: {goal_text}\n\n"
                "Generate a portfolio narrative. For each position comment on delta "
                "(long or short exposure — directional conviction) and, where the hold duration "
                "is known, theta context (is this a long-term conviction hold or a shorter trade). "
                "Then interpret the portfolio as a whole — what is being built, "
                "what the allocation says about conviction, which positions align with stated goals. "
                "3-5 sentences. Be direct."
            ),
            max_tokens=380,
        )
        return self._make_output(content, "portfolio_narrative")

    def generate_ux_review(self) -> BotOutput:
        """Critique one UX weakness and give one concrete fix. Trust level >= 1."""
        if not self._watcher.check_compliance(self.persona["name"], "commentary", self.persona.get("trust_level", 1)):
            return self._blocked_output("commentary")

        if not self._api_available():
            return self._no_key_output("ux_review")

        content = self._call(
            user_message=(
                "Review this dashboard's UX against the reference patterns you know.\n\n"
                "STACK — this is critical context:\n"
                "- Language: Python 3.10+\n"
                "- Framework: Textual (terminal UI, not a browser or web app)\n"
                "- Persistence: JSON files in data/ — NO localStorage, NO database, NO HTTP\n"
                "- Rendering: Rich text, Static widgets, DataTable — NO HTML, NO CSS classes\n"
                "- Habits: streak calculated from dated log entries in data/habits.json\n"
                "- Tasks: daily-reset JSON, wiped at midnight via date comparison in load_tasks()\n"
                "- NEON: Anthropic API (claude-sonnet-4-6), gated by trust level and daily call limit\n\n"
                "Find ONE specific weakness in the Textual TUI — something missing, inconsistent, "
                "or below the standard of great terminal dashboards like btop or k9s.\n\n"
                "Respond in exactly this format:\n"
                "GAP: [one sentence — specific to this Python/Textual codebase]\n"
                "FIX: [one concrete change — name the widget, method, or file to touch]\n"
                "CONSTRAINT: must preserve the minimal dark aesthetic. No new dependencies."
            ),
            max_tokens=220,
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
        # Same behavioral shift as _call_conversation — at L4+ NEON's tone becomes
        # more directive. See the comment in _call_conversation and permissions.py.
        trust_line = (
            f"[Trust level: {trust}/5 — {permissions.level_name(trust)}. "
            f"Capabilities: {', '.join(permissions.capabilities(trust)) or 'none'}]\n\n"
        )
        trait_directive = ""
        if self._active_trait and self._active_trait in TRAITS:
            trait_directive = TRAITS[self._active_trait]["directive"] + "\n\n"
        try:
            response = get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=self._system_blocks(),
                messages=[{"role": "user", "content": trust_line + trait_directive + user_message}],
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
