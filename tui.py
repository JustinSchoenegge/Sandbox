"""
tui.py  —  Dark Hour Dashboard (Textual TUI)
Persona 3 × GTA aesthetic.  Replaces app.py as the main entry point.
"""

import os
import signal
import shlex
import subprocess
from datetime import datetime, timedelta

from rich.text import Text
from rich.console import RenderableType

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, DataTable, Input
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widget import Widget
from textual import work
from textual import events

# ── project modules ────────────────────────────────────────────────────────────
from config import load_config, load_env
from dashboard import get_greeting, get_quote
from notify import notify
from habits import load_habits, is_done_today, calculate_streak, mark_done, save_habits
from tasks import load_tasks, save_tasks
from notes import load_notes, save_notes
from music import load_ideas, save_ideas
from portfolio import load_portfolio, calculate_weights, save_portfolio, check_alignment
from stocks import STOCKS, TIER_STYLES
from game import main as play_game
import vitals
import security
import permissions
from memory import MemoryManager
from watcher import Watcher
from bot import Bot, BotOutput, load_persona, save_persona
from inspiration import file_count as inspiration_count, export_notes
from prices import cached_changes

load_env()

# ── boot sound ─────────────────────────────────────────────────────────────────

def _boot_sound() -> None:
    path = "/System/Library/Sounds/Glass.aiff"
    if os.path.exists(path):
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


_MUSIC_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".music.pid")


def _kill_stale_music() -> None:
    """Kill any music process left over from a previous unclean exit."""
    try:
        with open(_MUSIC_PID_FILE) as f:
            pgid = int(f.read().strip())
        os.killpg(pgid, signal.SIGKILL)
    except Exception:
        pass
    try:
        os.remove(_MUSIC_PID_FILE)
    except Exception:
        pass


def _start_bg_music() -> "subprocess.Popen | None":
    """Loop vicecity.m4a in the background. Returns the process so it can be paused/terminated."""
    _kill_stale_music()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vicecity.m4a")
    if not os.path.exists(path):
        return None
    cmd = f"while true; do afplay {shlex.quote(path)}; done"
    proc = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # isolated process group so SIGSTOP/SIGCONT don't hit Python
    )
    try:
        pgid = os.getpgid(proc.pid)
        with open(_MUSIC_PID_FILE, "w") as f:
            f.write(str(pgid))
    except Exception:
        pass
    return proc


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard widgets
# ══════════════════════════════════════════════════════════════════════════════

class HUDWidget(Static):
    """Base for HUD cards: auto-refreshes on mount and when the screen is shown."""

    def on_mount(self) -> None:
        self.refresh_data()

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        pass


class DashboardHeader(Static):
    """Compact header: greeting + clock on line 1, daily quote on line 2."""

    def __init__(self, name: str, is_admin: bool = False) -> None:
        super().__init__()
        self._user_name = name
        self._is_admin = is_admin
        self._quote = get_quote()

    def on_mount(self) -> None:
        self._clock = ""
        self._date = ""
        self._tick()
        self.set_interval(1, self._tick)

    def _tick(self) -> None:
        now = datetime.now()
        self._clock = now.strftime("%I:%M %p")
        self._date = now.strftime("%a %b %d")
        self.refresh()

    def render(self) -> RenderableType:
        t = Text(justify="center")
        t.append("DARK HOUR", style="bold white")
        t.append("  ◐  ", style="dim #4a9eff")
        t.append(f"{get_greeting()}, {self._user_name}", style="bold #e8a020")
        if self._is_admin:
            t.append("  [ADMIN]", style="bold #ff2244")
        t.append(f"  ·  {self._date}  {self._clock}\n", style="dim #5f87af")
        t.append(f'"{self._quote}"', style="italic dim #5f87af")
        return t


# ── Screen navigation registry ────────────────────────────────────────────────
# To add a new screen: one entry here. NavSidebar and DashboardScreen both
# read from this list automatically.

_NAV = [
    ("1", "HABITS",    lambda _:    HabitsScreen()),
    ("2", "TASKS",     lambda _:    TasksScreen()),
    ("3", "NOTES",     lambda _:    NotesScreen()),
    ("4", "GAME",      lambda name: GameScreen(name)),
    ("5", "PORTFOLIO", lambda _:    PortfolioScreen()),
    ("6", "MUSIC",     lambda _:    MusicScreen()),
    ("7", "BOTS",      lambda _:    BotsScreen()),
    ("8", "SECURITY",  lambda _:    SecurityScreen()),
]


class NavSidebar(Widget):
    """Left-hand navigation sidebar — GTA mission-select style."""

    def compose(self) -> ComposeResult:
        nav = Text()
        for key, label, _ in _NAV:
            nav.append(f"[{key}]", style="bold #e8a020")
            nav.append(f"  {label}\n", style="bold white")
        nav.append("\n")
        nav.append("[q]", style="bold #e8a020")
        nav.append("  QUIT\n", style="bold white")
        yield Static(nav, id="nav-items")
        yield Static(
            "[dim #1e3a5f]· · · · · · · ·\n[/dim #1e3a5f][dim #2a3a5a] DARK  HOUR[/dim #2a3a5a]",
            id="nav-watermark",
        )


class HabitsWidget(Static):
    """HUD card: habits done today + best streak."""

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(10, self.refresh_data)

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            data = load_habits()
            habits = data["habits"]
            logs = data["logs"]
            total = len(habits)
            done = sum(1 for h in habits if is_done_today(logs.get(h, [])))
            filled = round(done / total * 12) if total else 0
            best = max(
                (calculate_streak(logs.get(h, [])) for h in habits), default=0
            )
            stat_style = "bold #e8a020" if done > 0 else "bold dim white"
            t = Text(justify="center")
            t.append(f"{done}/{total}\n", style=stat_style)
            t.append("HABITS TODAY\n", style="dim #4a5568")
            t.append("█" * filled, style="#00c040")
            t.append("░" * (12 - filled) + "\n", style="dim #2a3a5a")
            t.append(f"{best}d STREAK", style="dim #5f87af")
            self.update(t)
        except Exception:
            self.update(Text("Habits unavailable", style="dim"))


class TasksWidget(Static):
    """HUD card: tasks remaining."""

    def on_mount(self) -> None:
        self._last_date = datetime.now().strftime("%Y-%m-%d")
        self.refresh_data()
        self.set_interval(10, self.refresh_data)

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            tasks = load_tasks()
            today = datetime.now().strftime("%Y-%m-%d")
            reset_flag = today != self._last_date
            if reset_flag:
                self._last_date = today
            total = len(tasks)
            done_count = sum(1 for t in tasks if t["done"])
            remaining = total - done_count
            t = Text(justify="center")
            if remaining == 0 and total > 0:
                t.append("ALL DONE\n", style="bold #00c040")
                t.append("TASKS\n", style="dim #4a5568")
                t.append(f"{total} complete", style="dim #5f87af")
            elif total == 0:
                t.append("—\n", style="dim")
                t.append("NO TASKS\n", style="dim #4a5568")
                t.append("a = add one", style="dim #2a3a5a")
            else:
                t.append(f"{remaining}\n", style="bold #e8a020")
                t.append("REMAINING\n", style="dim #4a5568")
                t.append(f"{done_count} of {total} done", style="dim #5f87af")
            if reset_flag:
                t.append("\n↺ RESET", style="dim #5f87af")
            self.update(t)
        except Exception:
            self.update(Text("Tasks unavailable", style="dim"))


class NotesWidget(Static):
    """HUD card: note count + last note preview."""

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(10, self.refresh_data)

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            notes = load_notes()
            count = len(notes)
            t = Text(justify="center")
            t.append(f"{count}\n", style="bold #e8a020")
            t.append(f"NOTE{'S' if count != 1 else ''}\n", style="dim #4a5568")
            if notes:
                last_text = notes[-1]["text"]
                preview = (last_text[:28] + "…") if len(last_text) > 28 else last_text
                t.append(preview, style="italic dim #5f87af")
            else:
                t.append("no notes yet", style="dim #2a3a5a")
            self.update(t)
        except Exception:
            self.update(Text("Notes unavailable", style="dim"))


class PortfolioWidget(Static):
    """HUD card: total value + top 2 holdings."""

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(30, self.refresh_data)

    def on_show(self) -> None:
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        import asyncio
        try:
            portfolio = await asyncio.to_thread(load_portfolio)
            holdings = portfolio.get("holdings", [])
            goals = portfolio.get("goals", [])
            rows = await asyncio.to_thread(calculate_weights, holdings) if holdings else []
            t = Text()
            t.append("PORTFOLIO\n", style="bold #e8a020")
            t.append("──────────────────────\n", style="dim #1e3a5f")
            if goals:
                t.append("  ·  ".join(goals) + "\n", style="dim #4a9eff")
            if rows:
                total = sum(r["value"] for r in rows)
                t.append(f"${total:,.0f}  ·  {len(rows)} pos\n", style="bold #00c040")
                t.append("──────────────────────\n", style="dim #1e3a5f")
                for r in rows:
                    pnl = (r["current_price"] - r["avg_cost"]) / r["avg_cost"] * 100
                    up = pnl >= 0
                    arrow = "↑" if up else "↓"
                    filled = max(1, round(r["weight"] * 14))
                    wt = f"{r['weight']*100:.0f}%"
                    al_label, al_style = check_alignment(r.get("sector", ""), goals)
                    dot = "●" if "Strong" in al_label else ("◑" if "Partial" in al_label else "○")
                    t.append(f"{r['ticker']:<5}", style="bold white")
                    t.append(" ")
                    t.append("█" * filled, style="#4a9eff")
                    t.append("░" * (14 - filled) + " ", style="dim #1e3a5f")
                    t.append(f"{wt:>4}", style="dim white")
                    t.append(f"  {pnl:+.1f}%{arrow}", style=f"bold {'#00c040' if up else '#c03040'}")
                    t.append(f" {dot}\n", style=al_style)
            else:
                t.append("—\n", style="dim")
                t.append("no positions\n", style="dim #4a5568")
                t.append("[5] open portfolio", style="dim #2a3a5a")
            self.update(t)
        except Exception:
            self.update(Text("Portfolio unavailable", style="dim"))


class BotWidget(HUDWidget):
    """HUD card: bot persona presence — name, trust level, last output preview."""

    def refresh_data(self) -> None:
        try:
            bot: Bot | None = getattr(self.app, "_bot", None)
            mem: MemoryManager | None = getattr(self.app, "_memory", None)
            if bot is None:
                self.update(Text("Bot offline", style="dim"))
                return
            trust = bot.trust_level
            name = bot.name
            level_nm = permissions.level_name(trust)
            judged = mem.session_judgment_count if mem else 0
            calls = mem.calls_today if mem else 0
            limit = bot.persona.get("daily_call_limit", 50)
            preview = (mem.last_output_preview if mem else "")

            t = Text(justify="center")
            t.append(f"{name}", style="bold #4a9eff")
            t.append(f"  [L{trust}]\n", style="bold #e8a020")
            t.append(f"{level_nm}\n", style="dim #5f87af")
            if preview:
                short = (preview[:34] + "…") if len(preview) > 34 else preview
                t.append(f'"{short}"\n', style="italic dim #5f87af")
            else:
                t.append("no output yet\n", style="dim #2a3a5a")
            api_color = "#c03040" if calls >= limit else ("#e8a020" if calls >= limit * 0.8 else "#2a3a5a")
            t.append(f"{judged} judged  ·  ", style="dim #2a3a5a")
            t.append(f"API {calls}/{limit}", style=f"dim {api_color}")
            t.append("  ·  [7]", style="dim #2a3a5a")
            self.update(t)
        except Exception:
            self.update(Text("Bot unavailable", style="dim"))


class FooterControls(Static):
    """Footer bar: nav key hints left, music status indicator pinned right."""

    def on_mount(self) -> None:
        self.set_muted(False)

    def set_muted(self, muted: bool, song: str = "") -> None:
        from rich.table import Table as RichTable
        nav = Text()
        for key, label in [
            ("1", "HABITS"), ("2", "TASKS"), ("3", "NOTES"), ("4", "GAME"),
            ("5", "PORT"),   ("6", "MUSIC"), ("7", "BOTS"),  ("8", "SEC"),
        ]:
            nav.append(f"[{key}]", style="dim #e8a020")
            nav.append(f"{label} ", style="dim #5f87af")
        nav.append("  [M]", style="dim #e8a020")
        nav.append("MUTE  ", style="dim #5f87af")
        nav.append("[Q]", style="dim #e8a020")
        nav.append("QUIT", style="dim #5f87af")

        music = Text(justify="right")
        if muted:
            music.append("✕ MUTED", style="bold #c03040")
        else:
            music.append(f"♪  {song}" if song else "♪  LIVE", style="bold #00c040")

        grid = RichTable.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row(nav, music)
        self.update(grid)


class VitalsBar(Static):
    """Always-on bottom bar showing live system vitals."""

    def on_mount(self) -> None:
        self._refresh_vitals()
        self.set_interval(4, self._refresh_vitals)

    @work(exclusive=True)
    async def _refresh_vitals(self) -> None:
        import asyncio
        try:
            data = await asyncio.to_thread(vitals.gather)
            t = Text(justify="center")

            def _pct_style(pct):
                if pct is None:
                    return "dim"
                if pct >= 85:
                    return "bold #c03040"
                if pct >= 60:
                    return "#e8a020"
                return "#00c040"

            t.append("▸ ", style="dim #1e3a5f")

            cpu = data.get("cpu")
            t.append("CPU ", style="dim #5f87af")
            t.append(f"{cpu:.0f}%" if cpu is not None else "—", style=_pct_style(cpu))

            t.append("  ·  ", style="dim #1e3a5f")

            ram = data.get("ram_pct")
            ram_used = data.get("ram_used_gb")
            ram_total = data.get("ram_total_gb")
            t.append("RAM ", style="dim #5f87af")
            t.append(f"{ram:.0f}%" if ram is not None else "—", style=_pct_style(ram))
            if ram_used is not None:
                t.append(f" {ram_used}/{ram_total}GB", style="dim #4a5568")

            t.append("  ·  ", style="dim #1e3a5f")

            batt = data.get("batt_pct")
            plugged = data.get("batt_plugged")
            t.append("BATT ", style="dim #5f87af")
            if batt is not None:
                arrow = "⚡" if plugged else "↓"
                batt_style = "#00c040" if (plugged or batt > 40) else ("#e8a020" if batt > 20 else "bold #c03040")
                t.append(f"{batt}%{arrow}", style=batt_style)
            else:
                t.append("—", style="dim")

            t.append("  ·  ", style="dim #1e3a5f")

            disk = data.get("disk_pct")
            t.append("DISK ", style="dim #5f87af")
            t.append(f"{disk:.0f}%" if disk is not None else "—", style=_pct_style(disk))

            t.append("  ·  ", style="dim #1e3a5f")

            temp = data.get("temp")
            t.append("TEMP ", style="dim #5f87af")
            t.append(temp if temp else "—", style="dim #5f87af" if not temp else "#e8a020")

            t.append("  ·  ", style="dim #1e3a5f")

            fan = data.get("fan")
            t.append("FAN ", style="dim #5f87af")
            t.append(fan if fan else "—", style="dim #5f87af")

            self.update(t)
        except Exception:
            self.update(Text("vitals unavailable", style="dim"))


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard screen
# ══════════════════════════════════════════════════════════════════════════════

class DashboardScreen(Screen):
    BINDINGS = [
        ("1", "push_screen_nav_0", "Habits"),
        ("2", "push_screen_nav_1", "Tasks"),
        ("3", "push_screen_nav_2", "Notes"),
        ("4", "push_screen_nav_3", "Game"),
        ("5", "push_screen_nav_4", "Portfolio"),
        ("6", "push_screen_nav_5", "Music"),
        ("7", "push_screen_nav_6", "Bots"),
        ("8", "push_screen_nav_7", "Security"),
        ("m", "app.toggle_mute", "Mute"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, name: str, is_admin: bool = False) -> None:
        super().__init__()
        self._name = name
        self._is_admin = is_admin

    def compose(self) -> ComposeResult:
        yield DashboardHeader(self._name, self._is_admin)
        with Horizontal(id="body"):
            yield NavSidebar(id="sidebar")
            with Horizontal(id="main"):
                with Vertical(id="left-panel"):
                    with Horizontal(id="upper"):
                        yield HabitsWidget(id="habits-widget")
                        yield TasksWidget(id="tasks-widget")
                    with Horizontal(id="lower"):
                        yield NotesWidget(id="notes-widget")
                        yield BotWidget(id="bot-widget")
                yield PortfolioWidget(id="portfolio-widget")
        yield FooterControls(id="footer-controls")
        yield VitalsBar(id="vitals-bar")

    def on_show(self) -> None:
        try:
            muted = getattr(self.app, "_music_muted", False)
            song = getattr(self.app, "_current_song", "")
            self.query_one(FooterControls).set_muted(muted, song)
        except Exception:
            pass
        try:
            self.query_one("#habits-widget", HabitsWidget).refresh_data()
        except Exception:
            pass
        try:
            self.query_one("#tasks-widget", TasksWidget).refresh_data()
        except Exception:
            pass
        try:
            self.query_one("#notes-widget", NotesWidget).refresh_data()
        except Exception:
            pass
        try:
            self.query_one("#portfolio-widget", PortfolioWidget).refresh_data()
        except Exception:
            pass

    def action_push_screen_nav_0(self) -> None:
        self.app.push_screen(_NAV[0][2](self._name))

    def action_push_screen_nav_1(self) -> None:
        self.app.push_screen(_NAV[1][2](self._name))

    def action_push_screen_nav_2(self) -> None:
        self.app.push_screen(_NAV[2][2](self._name))

    def action_push_screen_nav_3(self) -> None:
        self.app.push_screen(_NAV[3][2](self._name))

    def action_push_screen_nav_4(self) -> None:
        self.app.push_screen(_NAV[4][2](self._name))

    def action_push_screen_nav_5(self) -> None:
        self.app.push_screen(_NAV[5][2](self._name))

    def action_push_screen_nav_6(self) -> None:
        self.app.push_screen(_NAV[6][2](self._name))

    def action_push_screen_nav_7(self) -> None:
        self.app.push_screen(_NAV[7][2](self._name))


# ══════════════════════════════════════════════════════════════════════════════
# Habits screen
# ══════════════════════════════════════════════════════════════════════════════

class HabitsScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("a", "add_mode", "Add"),
        ("r", "remove_mode", "Remove"),
        ("escape", "cancel_input", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  HABITS  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="habits-table", cursor_type="row", show_cursor=True)
        yield Input(placeholder="New habit name…", id="habit-input", classes="hidden")
        yield Static("", id="habits-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][↑↓][/bold #e8a020][white] navigate  [/white]"
            "[bold #e8a020][enter][/bold #e8a020][white] mark done  [/white]"
            "[bold #e8a020][1-9][/bold #e8a020][white] quick mark  [/white]"
            "[bold #e8a020][a][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][r][/bold #e8a020][white] remove  [/white]"
            "[bold #e8a020][q][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode = None
        table = self.query_one("#habits-table", DataTable)
        table.can_focus = True
        self._populate_table()
        table.focus()

    def _populate_table(self) -> None:
        table = self.query_one("#habits-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Habit", "Today", "Streak")
        try:
            data = load_habits()
            if not data["habits"]:
                self.query_one("#habits-msg", Static).update(
                    Text("No habits yet.  [a] to add one.", style="dim #5f87af")
                )
                return
            shortcut = 1
            for i, habit in enumerate(data["habits"]):
                dates = data["logs"].get(habit, [])
                done = is_done_today(dates)
                streak = calculate_streak(dates)
                if done:
                    num_cell = Text("✓", style="bold #00c040")
                else:
                    num_cell = Text(str(shortcut), style="bold #e8a020") if shortcut <= 9 else Text("·", style="dim")
                    shortcut += 1
                today_cell = Text("✓", style="bold #00c040") if done else Text("—", style="dim")
                streak_cell = Text(f"{streak}d", style="#e8a020" if streak > 0 else "dim")
                table.add_row(num_cell, habit, today_cell, streak_cell, key=str(i))
        except Exception as e:
            self.query_one("#habits-msg", Static).update(
                Text(f"Error loading habits: {e}", style="bold #c03040")
            )

    def _mark_habit_at_index(self, full_idx: int) -> None:
        try:
            data = load_habits()
            habits = data["habits"]
            if 0 <= full_idx < len(habits):
                habit = habits[full_idx]
                success = mark_done(data, habit)
                msg = self.query_one("#habits-msg", Static)
                if success:
                    msg.update(Text(f"{habit} marked done!", style="bold #00c040"))
                else:
                    msg.update(Text(f"{habit} already done today.", style="bold #c03040"))
                self._populate_table()
        except Exception:
            try:
                self.query_one("#habits-msg", Static).update(Text("Error saving habit.", style="bold #c03040"))
            except Exception:
                pass

    def _incomplete_indices(self) -> list[int]:
        """Return full list indices of habits not yet done today, in order."""
        try:
            data = load_habits()
            return [
                i for i, h in enumerate(data["habits"])
                if not is_done_today(data["logs"].get(h, []))
            ]
        except Exception:
            return []

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._mode is not None:
            return
        try:
            self._mark_habit_at_index(int(event.row_key.value))
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        if self._mode is not None:
            return
        if event.character and event.character.isdigit():
            event.stop()
            shortcut_idx = int(event.character) - 1  # 0-based shortcut position
            incomplete = self._incomplete_indices()
            if 0 <= shortcut_idx < len(incomplete):
                self._mark_habit_at_index(incomplete[shortcut_idx])

    def action_add_mode(self) -> None:
        self._mode = "add"
        inp = self.query_one("#habit-input", Input)
        inp.placeholder = "New habit name…"
        inp.remove_class("hidden")
        inp.focus()

    def action_remove_mode(self) -> None:
        self._mode = "remove"
        inp = self.query_one("#habit-input", Input)
        inp.placeholder = "Habit # to remove…"
        inp.remove_class("hidden")
        inp.focus()

    def action_cancel_input(self) -> None:
        self._mode = None
        inp = self.query_one("#habit-input", Input)
        inp.add_class("hidden")
        inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        msg = self.query_one("#habits-msg", Static)
        try:
            data = load_habits()
            habits = data["habits"]
            if self._mode == "add":
                if not value:
                    msg.update(Text("Name cannot be empty.", style="bold #c03040"))
                elif value in habits:
                    msg.update(Text(f"{value} already exists.", style="bold #c03040"))
                else:
                    data["habits"].append(value)
                    data["logs"].setdefault(value, [])
                    save_habits(data)
                    msg.update(Text(f"{value} added.", style="bold #00c040"))
            elif self._mode == "remove":
                if value.isdigit():
                    idx = int(value) - 1
                    if 0 <= idx < len(habits):
                        removed = habits.pop(idx)
                        save_habits(data)
                        msg.update(Text(f"{removed} removed.", style="bold #00c040"))
                    else:
                        msg.update(Text("Invalid habit number.", style="bold #c03040"))
                else:
                    msg.update(Text("Enter a habit number.", style="bold #c03040"))
        except Exception:
            msg.update(Text("Error updating habits.", style="bold #c03040"))
        self.action_cancel_input()
        self._populate_table()


# ══════════════════════════════════════════════════════════════════════════════
# Tasks screen
# ══════════════════════════════════════════════════════════════════════════════

class TasksScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("a", "add_mode", "Add"),
        ("escape", "cancel_input", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  TASKS  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="tasks-table", cursor_type="row", show_cursor=False)
        yield Input(placeholder="New task name…", id="task-input", classes="hidden")
        yield Static("", id="tasks-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][#][/bold #e8a020][white] complete  [/white]"
            "[bold #e8a020][a][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][q][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode = None
        self._populate_table()
        self.query_one("#tasks-table", DataTable).can_focus = False

    def _populate_table(self) -> None:
        table = self.query_one("#tasks-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Task", "✓")
        try:
            tasks = load_tasks()
            total = len(tasks)
            done_count = sum(1 for t in tasks if t["done"])
            remaining = total - done_count
            msg = self.query_one("#tasks-msg", Static)
            if total == 0:
                msg.update(Text("No tasks yet.", style="dim"))
            elif remaining == 0:
                msg.update(Text("All tasks complete ✓", style="bold #00c040"))
            else:
                msg.update(Text(f"{done_count} of {total} complete", style="dim #5f87af"))
            for i, task in enumerate(tasks, 1):
                name_cell = (
                    Text(task["name"], style="dim #5f87af")
                    if task["done"]
                    else Text(task["name"], style="bold white")
                )
                done_cell = (
                    Text("✓", style="bold #00c040")
                    if task["done"]
                    else Text("—", style="dim")
                )
                table.add_row(str(i), name_cell, done_cell)
        except Exception as e:
            self.query_one("#tasks-msg", Static).update(
                Text(f"Error loading tasks: {e}", style="bold #c03040")
            )

    def on_key(self, event: events.Key) -> None:
        if self._mode is not None:
            return
        if event.character and event.character.isdigit():
            event.stop()
            idx = int(event.character) - 1
            try:
                tasks = load_tasks()
                if 0 <= idx < len(tasks):
                    if tasks[idx]["done"]:
                        self.query_one("#tasks-msg", Static).update(
                            Text(f"{tasks[idx]['name']} is already done.", style="bold #c03040")
                        )
                    else:
                        task_name = tasks[idx]["name"]
                        tasks[idx]["done"] = True
                        save_tasks(tasks)
                        self.query_one("#tasks-msg", Static).update(
                            Text(f"{task_name} completed!", style="bold #00c040")
                        )
                    self._populate_table()
            except Exception:
                try:
                    self.query_one("#tasks-msg", Static).update(Text("Error saving task.", style="bold #c03040"))
                except Exception:
                    pass

    def action_add_mode(self) -> None:
        self._mode = "add"
        inp = self.query_one("#task-input", Input)
        inp.remove_class("hidden")
        inp.focus()

    def action_cancel_input(self) -> None:
        self._mode = None
        inp = self.query_one("#task-input", Input)
        inp.add_class("hidden")
        inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        msg = self.query_one("#tasks-msg", Static)
        if self._mode == "add":
            if not value:
                msg.update(Text("Task name cannot be empty.", style="bold #c03040"))
            else:
                try:
                    tasks = load_tasks()
                    tasks.append({"name": value, "done": False})
                    save_tasks(tasks)
                    msg.update(Text(f"'{value}' added.", style="bold #00c040"))
                except Exception:
                    msg.update(Text("Error saving task.", style="bold #c03040"))
        self.action_cancel_input()
        self._populate_table()


# ══════════════════════════════════════════════════════════════════════════════
# Notes screen
# ══════════════════════════════════════════════════════════════════════════════

class NotesScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("a", "add_mode", "Add"),
        ("escape", "cancel_input", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  NOTES  ═══[/bold white]", classes="sub-title")
        with ScrollableContainer(id="notes-scroll"):
            yield Static(id="notes-content")
        yield Input(placeholder="New note… (use #tag for tags)", id="note-input", classes="hidden")
        yield Static("", id="notes-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][a][/bold #e8a020][white] add note  [/white]"
            "[bold #e8a020][q][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode = None
        self._refresh_notes()

    def on_show(self) -> None:
        self._refresh_notes()

    def _refresh_notes(self) -> None:
        try:
            notes = load_notes()
            if not notes:
                t = Text("No notes yet. Press a to add one.", style="dim")
            else:
                t = Text()
                for note in reversed(notes):
                    tags = note.get("tags", [])
                    t.append(f"{note['timestamp']}", style="dim #5f87af")
                    if tags:
                        t.append(f"  {' '.join(tags)}", style="bold #008b8b")
                    t.append("\n")
                    for word in note["text"].split(" "):
                        if word.startswith("#"):
                            t.append(word, style="bold #008b8b")
                        else:
                            t.append(word, style="white")
                        t.append(" ")
                    t.append("\n\n")
            self.query_one("#notes-content", Static).update(t)
        except Exception:
            self.query_one("#notes-content", Static).update(
                Text("Notes unavailable", style="dim")
            )

    def action_add_mode(self) -> None:
        self._mode = "add"
        inp = self.query_one("#note-input", Input)
        inp.remove_class("hidden")
        inp.focus()

    def action_cancel_input(self) -> None:
        self._mode = None
        inp = self.query_one("#note-input", Input)
        inp.add_class("hidden")
        inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        msg = self.query_one("#notes-msg", Static)
        if self._mode == "add":
            if not value:
                msg.update(Text("Note cannot be empty.", style="bold #c03040"))
            else:
                try:
                    notes = load_notes()
                    tags = [w for w in value.split() if w.startswith("#")]
                    notes.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                        "text": value,
                        "tags": tags,
                    })
                    save_notes(notes)
                    msg.update(Text("Note saved.", style="bold #00c040"))
                except Exception:
                    msg.update(Text("Error saving note.", style="bold #c03040"))
        self.action_cancel_input()
        self._refresh_notes()


# ══════════════════════════════════════════════════════════════════════════════
# Music screen
# ══════════════════════════════════════════════════════════════════════════════

class MusicScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("a", "add_mode", "Add"),
        ("escape", "cancel_input", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  MUSIC IDEAS  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="music-table", cursor_type="row", show_cursor=False)
        with Horizontal(id="music-inputs", classes="hidden"):
            yield Input(id="music-title-in", placeholder="Song title…")
            yield Input(id="music-vibe-in", placeholder="Vibe / mood…")
        yield Static("", id="music-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][#][/bold #e8a020][white] view detail  [/white]"
            "[bold #e8a020][a][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][q][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode = None
        self._pending_title = ""
        self._populate_table()
        self.query_one("#music-table", DataTable).can_focus = False

    def on_show(self) -> None:
        self._populate_table()

    def _populate_table(self) -> None:
        table = self.query_one("#music-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Title", "Vibe", "Written")
        try:
            ideas = load_ideas()
            if not ideas:
                self.query_one("#music-msg", Static).update(
                    Text("No ideas yet.  [a] to add one.", style="dim #5f87af")
                )
                return
            for i, idea in enumerate(ideas, 1):
                written = Text("✓", style="bold #00c040") if idea.get("song") else Text("—", style="dim")
                table.add_row(str(i), idea["title"], idea.get("vibe", ""), written)
        except Exception as e:
            self.query_one("#music-msg", Static).update(
                Text(f"Error loading music: {e}", style="bold #c03040")
            )

    def on_key(self, event: events.Key) -> None:
        if self._mode is not None:
            return
        if event.character and event.character.isdigit():
            event.stop()
            idx = int(event.character) - 1
            try:
                ideas = load_ideas()
                if 0 <= idx < len(ideas):
                    idea = ideas[idx]
                    detail = Text()
                    detail.append(f"{idea['title']}", style="bold white")
                    detail.append(f"  ·  {idea.get('vibe', '')}  ", style="dim #5f87af")
                    detail.append(f"  added {idea.get('timestamp', '')}", style="dim #2a3a5a")
                    if idea.get("song"):
                        detail.append(f"\n{idea['song']}", style="italic #008b8b")
                    self.query_one("#music-msg", Static).update(detail)
                else:
                    self.query_one("#music-msg", Static).update(
                        Text(f"Enter 1–{len(ideas)}.", style="bold #c03040")
                    )
            except Exception:
                pass

    def action_add_mode(self) -> None:
        self._mode = "title"
        self._pending_title = ""
        inputs_bar = self.query_one("#music-inputs")
        inputs_bar.remove_class("hidden")
        title_in = self.query_one("#music-title-in", Input)
        title_in.value = ""
        vibe_in = self.query_one("#music-vibe-in", Input)
        vibe_in.value = ""
        title_in.focus()

    def action_cancel_input(self) -> None:
        self._mode = None
        self._pending_title = ""
        self.query_one("#music-inputs").add_class("hidden")
        self.query_one("#music-title-in", Input).value = ""
        self.query_one("#music-vibe-in", Input).value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = self.query_one("#music-msg", Static)
        if self._mode == "title":
            value = event.value.strip()
            if not value:
                msg.update(Text("Title cannot be empty.", style="bold #c03040"))
                self.action_cancel_input()
                return
            self._pending_title = value
            self._mode = "vibe"
            self.query_one("#music-vibe-in", Input).focus()
        elif self._mode == "vibe":
            vibe = event.value.strip() or "open"
            title = self._pending_title
            try:
                ideas = load_ideas()
                ideas.append({
                    "title": title,
                    "vibe": vibe,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                    "song": None,
                })
                save_ideas(ideas)
                msg.update(Text(f"'{title}' added.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error saving idea.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()


# ══════════════════════════════════════════════════════════════════════════════
# Portfolio screen
# ══════════════════════════════════════════════════════════════════════════════

class PortfolioScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("a", "add_mode", "Add"),
        ("e", "edit_mode", "Edit"),
        ("r", "remove_mode", "Remove"),
        ("g", "goals_mode", "Goals"),
        ("escape", "cancel_input", "Cancel"),
    ]

    _TIERS = ["S+", "S", "A", "B", "C", "D", "F"]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  PORTFOLIO  ═══[/bold white]", classes="sub-title")
        yield Static("", id="port-goals")
        yield DataTable(id="port-table", cursor_type="row", show_cursor=False)
        yield Input(placeholder="", id="port-input", classes="hidden")
        yield Static("", id="port-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][a][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][e][/bold #e8a020][white] edit  [/white]"
            "[bold #e8a020][r][/bold #e8a020][white] remove  [/white]"
            "[bold #e8a020][g][/bold #e8a020][white] goals  [/white]"
            "[bold #e8a020][q][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode: str | None = None
        self._pending: dict = {}
        self._edit_idx: int | None = None
        self._populate_table()
        self.query_one("#port-table", DataTable).can_focus = False

    def on_show(self) -> None:
        self._populate_table()

    def _populate_table(self) -> None:
        table = self.query_one("#port-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Ticker", "Sector", "Allocation", "Tier", "P&L", "Fit")
        try:
            portfolio = load_portfolio()
            goals = portfolio.get("goals", [])
            goals_str = "  ·  ".join(goals) if goals else "no goals — press g to add"
            try:
                self.query_one("#port-goals", Static).update(
                    Text(f"Goals: {goals_str}", style="dim #4a9eff")
                )
            except Exception:
                pass
            rows = calculate_weights(portfolio["holdings"]) if portfolio["holdings"] else []
            msg = self.query_one("#port-msg", Static)
            if not rows:
                msg.update(Text("No positions yet — press a to add one.", style="dim #2a3a5a"))
                return
            total = sum(r["value"] for r in rows)
            for i, r in enumerate(rows, 1):
                w = r["weight"]
                filled = max(1, round(w * 20))
                pct = f"{w * 100:.1f}%"
                alloc = Text()
                alloc.append("█" * filled, style="#4a9eff")
                alloc.append("░" * (20 - filled), style="dim #1e3a5f")
                alloc.append(f" {pct}", style="dim #5f87af")

                pnl_pct = (r["current_price"] - r["avg_cost"]) / r["avg_cost"] * 100
                up = pnl_pct >= 0
                pnl_cell = Text()
                pnl_cell.append(
                    f"{pnl_pct:+.1f}%{'↑' if up else '↓'}",
                    style="bold #00c040" if up else "bold #c03040",
                )

                al_label, al_style = check_alignment(r.get("sector", ""), goals)
                if "Strong" in al_label:
                    dot, dot_style = "●", "bold green"
                elif "Partial" in al_label:
                    dot, dot_style = "◑", "bold yellow"
                else:
                    dot, dot_style = "○", "dim red"

                tier = r.get("tier", "?")
                tier_style = TIER_STYLES.get(tier, "white")

                table.add_row(
                    str(i),
                    Text(r["ticker"], style="bold white"),
                    Text(r.get("sector", "?"), style="dim #5f87af"),
                    alloc,
                    Text(tier, style=tier_style),
                    pnl_cell,
                    Text(dot, style=dot_style),
                )
            msg.update(Text(f"${total:,.2f} total  ·  {len(rows)} position(s)", style="dim #5f87af"))
        except Exception:
            self.query_one("#port-msg", Static).update(Text("Portfolio unavailable.", style="dim"))

    def _set_input(self, placeholder: str) -> None:
        inp = self.query_one("#port-input", Input)
        inp.placeholder = placeholder
        inp.value = ""
        inp.remove_class("hidden")
        inp.focus()

    def action_add_mode(self) -> None:
        self._mode = "ticker"
        self._pending = {}
        self._set_input("Ticker (e.g. AAPL)…")

    def action_edit_mode(self) -> None:
        self._mode = "edit_num"
        self._edit_idx = None
        self._set_input("Position # to edit…")

    def action_remove_mode(self) -> None:
        self._mode = "remove"
        self._set_input("Position # to remove…")

    def action_goals_mode(self) -> None:
        self._mode = "goals"
        self._set_input("Goals (comma separated)…")

    def action_cancel_input(self) -> None:
        self._mode = None
        self._pending = {}
        self._edit_idx = None
        inp = self.query_one("#port-input", Input)
        inp.add_class("hidden")
        inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        msg = self.query_one("#port-msg", Static)

        if self._mode == "goals":
            if value:
                try:
                    portfolio = load_portfolio()
                    portfolio["goals"] = [g.strip() for g in value.split(",") if g.strip()]
                    save_portfolio(portfolio)
                    msg.update(Text("Goals updated.", style="bold #00c040"))
                except Exception:
                    msg.update(Text("Error saving goals.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "remove":
            try:
                portfolio = load_portfolio()
                holdings = portfolio["holdings"]
                if value.isdigit() and 0 < int(value) <= len(holdings):
                    removed = holdings.pop(int(value) - 1)
                    save_portfolio(portfolio)
                    msg.update(Text(f"{removed['ticker']} removed.", style="bold #00c040"))
                else:
                    msg.update(Text(f"Enter 1–{len(holdings)}.", style="bold #c03040"))
            except Exception:
                msg.update(Text("Error removing position.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "edit_num":
            try:
                portfolio = load_portfolio()
                holdings = portfolio["holdings"]
                if value.isdigit() and 0 < int(value) <= len(holdings):
                    self._edit_idx = int(value) - 1
                    h = holdings[self._edit_idx]
                    msg.update(Text(
                        f"{h['ticker']}: shares={h['shares']}  cost={h['avg_cost']}  tier={h.get('tier','?')}",
                        style="dim #5f87af",
                    ))
                    self._mode = "edit_field"
                    self._set_input("Field: shares / cost / tier")
                else:
                    msg.update(Text(f"Enter 1–{len(holdings)}.", style="bold #c03040"))
            except Exception:
                msg.update(Text("Error.", style="bold #c03040"))
            return

        if self._mode == "edit_field":
            field = value.lower()
            if field not in ("shares", "cost", "tier"):
                msg.update(Text("Enter: shares, cost, or tier", style="bold #c03040"))
                return
            self._mode = f"edit_{field}"
            prompts = {
                "shares": "New shares…",
                "cost": "New avg cost ($)…",
                "tier": f"New tier ({'/'.join(self._TIERS)})…",
            }
            self._set_input(prompts[field])
            return

        if self._mode in ("edit_shares", "edit_cost"):
            try:
                float(value)
            except ValueError:
                msg.update(Text("Enter a number.", style="bold #c03040"))
                return
            try:
                portfolio = load_portfolio()
                key = "shares" if self._mode == "edit_shares" else "avg_cost"
                portfolio["holdings"][self._edit_idx][key] = float(value)
                save_portfolio(portfolio)
                msg.update(Text("Position updated.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error updating.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "edit_tier":
            tier = value.upper()
            if tier not in self._TIERS:
                msg.update(Text(f"Tier must be one of: {', '.join(self._TIERS)}", style="bold #c03040"))
                return
            try:
                portfolio = load_portfolio()
                portfolio["holdings"][self._edit_idx]["tier"] = tier
                save_portfolio(portfolio)
                msg.update(Text("Tier updated.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error updating.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()
            return

        if self._mode == "ticker":
            if not value:
                msg.update(Text("Ticker cannot be empty.", style="bold #c03040"))
                return
            ticker = value.upper()
            self._pending["ticker"] = ticker
            known = next((s for s in STOCKS if s["ticker"] == ticker), None)
            if known:
                self._pending["sector"] = known["sector"]
                self._pending["name"] = known["name"]
            else:
                self._pending["sector"] = "Unknown"
                self._pending["name"] = ticker
            self._mode = "shares"
            self._set_input("Shares owned…")

        elif self._mode == "shares":
            try:
                float(value)
            except ValueError:
                msg.update(Text("Enter a number for shares.", style="bold #c03040"))
                return
            self._pending["shares"] = float(value)
            self._mode = "cost"
            self._set_input("Avg cost per share ($)…")

        elif self._mode == "cost":
            try:
                float(value)
            except ValueError:
                msg.update(Text("Enter a number for cost.", style="bold #c03040"))
                return
            self._pending["avg_cost"] = float(value)
            self._mode = "tier"
            tiers = "/".join(self._TIERS)
            self._set_input(f"Tier ({tiers})…")

        elif self._mode == "tier":
            tier = value.upper()
            if tier not in self._TIERS:
                msg.update(Text(f"Tier must be one of: {', '.join(self._TIERS)}", style="bold #c03040"))
                return
            self._pending["tier"] = tier
            try:
                portfolio = load_portfolio()
                ticker = self._pending["ticker"]
                portfolio["holdings"].append({
                    "ticker": ticker,
                    "name": self._pending.get("name", ticker),
                    "sector": self._pending.get("sector", "Unknown"),
                    "shares": self._pending["shares"],
                    "avg_cost": self._pending["avg_cost"],
                    "tier": tier,
                })
                save_portfolio(portfolio)
                msg.update(Text(f"{ticker} added.", style="bold #00c040"))
            except Exception:
                msg.update(Text("Error saving position.", style="bold #c03040"))
            self.action_cancel_input()
            self._populate_table()


# ══════════════════════════════════════════════════════════════════════════════
# Game screen
# ══════════════════════════════════════════════════════════════════════════════

class GameScreen(Screen):
    BINDINGS = [
        ("enter", "launch", "Start"),
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold white]STOCK GUESSER[/bold white]\n\n[dim #5f87af]"
            "Press [bold white]Enter[/bold white] to launch game  ·  "
            "[bold white]q[/bold white] to go back[/dim #5f87af]",
            id="game-prompt",
        )

    def action_launch(self) -> None:
        try:
            with self.app.suspend():
                play_game(self._name)
        except Exception as e:
            self.query_one("#game-prompt", Static).update(
                f"[bold #c03040]Game error: {e}[/bold #c03040]\n\n"
                "[dim #5f87af]Press [bold white]q[/bold white] to go back[/dim #5f87af]"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Shared context builder — used by BotsScreen and morning brief
# ══════════════════════════════════════════════════════════════════════════════

def _build_neon_context() -> dict:
    ctx: dict = {}
    try:
        data = load_habits()
        habits = data["habits"]
        logs = data["logs"]
        ctx["habits_done"]  = sum(1 for h in habits if is_done_today(logs.get(h, [])))
        ctx["habits_total"] = len(habits)
        ctx["habits_list"]  = habits[:8]
        today_dt = datetime.now().date()
        last_30  = {(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)}
        last_14  = {(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)}
        prior_14 = {(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14, 28)}
        trend_data = []
        for h in habits:
            log_set = set(logs.get(h, []))
            days_30 = len(log_set & last_30)
            recent  = len(log_set & last_14)
            prior   = len(log_set & prior_14)
            trend   = "↑" if recent > prior else ("↓" if recent < prior else "→")
            trend_data.append({"habit": h, "pct_30": round(days_30 / 30 * 100), "days_30": days_30, "trend": trend})
        ctx["habit_trends"] = trend_data
        if trend_data:
            ctx["habit_avg_30"] = round(
                sum(t["days_30"] for t in trend_data) / (len(trend_data) * 30) * 100
            )
    except Exception:
        pass
    try:
        tasks = load_tasks()
        remaining = [t["name"] for t in tasks if not t["done"]]
        ctx["tasks_remaining"] = len(remaining)
        ctx["tasks_open"] = remaining[:5]
        ctx["tasks_done_count"] = sum(1 for t in tasks if t["done"])
    except Exception:
        pass
    try:
        notes = load_notes()
        ctx["notes_count"] = len(notes)
        if notes:
            ctx["notes_recent"] = [n["text"][:60] for n in notes[-3:]]
    except Exception:
        pass
    try:
        portfolio = load_portfolio()
        holdings = portfolio.get("holdings", [])
        if holdings:
            rows = calculate_weights(holdings)
            total = sum(r["value"] for r in rows)
            ctx["portfolio_value"] = round(total, 2)
            ctx["portfolio_positions"] = len(rows)
            ctx["portfolio_top"] = [
                {
                    "ticker": r["ticker"],
                    "shares": r.get("shares", 0),
                    "weight": round(r["weight"] * 100, 1),
                    "pnl": round((r["current_price"] - r["avg_cost"]) / r["avg_cost"] * 100, 1),
                }
                for r in rows[:4]
            ]
            changes = cached_changes()
            movers = [
                {"ticker": h["ticker"], "change": changes[h["ticker"]]}
                for h in holdings
                if h["ticker"] in changes
            ]
            if movers:
                ctx["price_movers"] = sorted(movers, key=lambda x: abs(x["change"]), reverse=True)
    except Exception:
        pass
    try:
        ideas = load_ideas()
        if ideas:
            ctx["music_count"] = len(ideas)
            ctx["music_ideas"] = [
                {"title": i["title"], "vibe": i.get("vibe", "")}
                for i in ideas
            ]
    except Exception:
        pass
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# Bots screen
# ══════════════════════════════════════════════════════════════════════════════

class BotsScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("c", "ask_mode", "Chat"),
        ("o", "generate_observation", "Observe"),
        ("u", "generate_ux", "UX Review"),
        ("m", "generate_music", "Music"),
        ("a", "generate_art", "Art"),
        ("y", "approve", "Approve"),
        ("n", "reject", "Reject"),
        ("s", "save_chat", "Save"),
        ("p", "open_persona", "Persona"),
        ("e", "export_notes", "Export Notes"),
        ("plus", "trust_up", "Trust +"),
        ("minus", "trust_down", "Trust -"),
        ("escape", "cancel_ask", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("", id="bots-title", classes="sub-title")
        with Horizontal(id="bots-body"):
            with ScrollableContainer(id="bots-history"):
                yield Static("", id="history-content")
            with Vertical(id="bots-right"):
                yield Static("", id="pending-header")
                yield Static("", id="pending-content")
                yield Static("", id="pending-hint")
        yield Input(placeholder="[c] to chat with NEON…", id="bots-input")
        yield Static("", id="watcher-bar")
        yield Static(
            "[dim #2a3a5a]"
            "[c] chat  [o] observe  [u] ux  [m] music  [a] art  "
            "[y] approve output  [n] reject  [s] save chat  "
            "[e] export notes  [p] persona  [+/-] trust  [q] back"
            "[/dim #2a3a5a]",
            id="bots-keyhint",
        )

    def on_mount(self) -> None:
        mem = getattr(self.app, "_memory", None)
        self._history: list[dict] = [
            {"time": j["time"], "type": j["type"], "verdict": j["verdict"], "content": ""}
            for j in (mem.session_judgments if mem else [])
        ]
        self._generating = False
        self._input_mode: str | None = None
        self._chat_thread: list[dict] = []
        self._brief_loaded: bool = getattr(self.app, "_brief_displayed_in_bots", False)
        self._trust_pending: str | None = None
        self._insp_count: int = inspiration_count()
        self._watcher_timer = None
        self._refresh_title()
        self._refresh_pending_display()
        self._refresh_watcher()
        self._refresh_history()

    def on_key(self, event: events.Key) -> None:
        if self._trust_pending and event.key not in ("plus", "minus"):
            self._trust_pending = None
            self._refresh_pending_display()

    def on_hide(self) -> None:
        if self._watcher_timer is not None:
            self._watcher_timer.stop()
            self._watcher_timer = None

    def on_show(self) -> None:
        self._watcher_timer = self.set_interval(5, self._refresh_watcher)
        self._refresh_title()
        self._insp_count = inspiration_count()
        self._refresh_watcher()
        # Load morning brief into history + chat thread on first visit
        if not self._brief_loaded:
            self._brief_loaded = True
            self.app._brief_displayed_in_bots = True
            brief = getattr(self.app, "_morning_brief", None)
            if brief:
                if not any(h["type"] == "brief" for h in self._history):
                    self._history.append({
                        "time": brief.timestamp,
                        "type": "brief",
                        "verdict": "approved",
                        "content": brief.content,
                    })
                if not self._chat_thread:
                    self._chat_thread.append({
                        "role": "assistant",
                        "content": brief.content,
                        "time": brief.timestamp,
                    })
        self._refresh_history()
        bot: Bot | None = getattr(self.app, "_bot", None)
        has_brief = bool(getattr(self.app, "_morning_brief", None))
        if bot and bot.pending is None and not self._generating and self._input_mode is None and not has_brief:
            self._generate("observation")

    def _refresh_title(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None:
            title = "BOTS — offline"
        else:
            t = bot.trust_level
            title = f"BOTS  ·  {bot.name}  [L{t}: {permissions.level_name(t)}]"
        try:
            self.query_one("#bots-title", Static).update(f"[bold white]{title}[/bold white]")
        except Exception:
            pass

    def _refresh_watcher(self) -> None:
        watcher: Watcher | None = getattr(self.app, "_watcher", None)
        bot: Bot | None = getattr(self.app, "_bot", None)
        mem: MemoryManager | None = getattr(self.app, "_memory", None)
        if watcher is None:
            return
        watcher.check_health(bot)
        h = watcher.health
        calls = mem.calls_today if mem else 0
        limit = bot.persona.get("daily_call_limit", 50) if bot else 50
        bar = Text(justify="center")
        bar.append("WATCHER  ", style="dim #2a3a5a")
        for label, ok in [("API", h.anthropic_api), ("MEM", h.memory_layer), ("♪", h.music_system), ("BOT", h.bot_online)]:
            color = "#00c040" if ok else "#c03040"
            bar.append("● " if ok else "○ ", style=f"bold {color}")
            bar.append(f"{label}  ", style=f"dim {color}")
        api_color = "#c03040" if calls >= limit else ("#e8a020" if calls >= limit * 0.8 else "#2a3a5a")
        bar.append(f"CALLS:{calls}/{limit}  ", style=f"dim {api_color}")
        insp = getattr(self, "_insp_count", 0)
        insp_color = "#00c040" if insp > 0 else "#2a3a5a"
        bar.append(f"INSP:{insp}  ", style=f"dim {insp_color}")
        bar.append(
            f"QUEUE:{watcher.queue_depth}  FLAGS:{watcher.flag_count}  {watcher.last_check}",
            style="dim #2a3a5a",
        )
        try:
            self.query_one("#watcher-bar", Static).update(bar)
        except Exception:
            pass

    def _refresh_pending_display(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        try:
            header_w = self.query_one("#pending-header", Static)
            content_w = self.query_one("#pending-content", Static)
            hint_w    = self.query_one("#pending-hint", Static)
        except Exception:
            return

        if self._generating:
            header_w.update(Text("generating…", style="bold #e8a020"))
            content_w.update(Text(""))
            hint_w.update(Text(""))
            return

        pending = bot.pending if bot else None

        if pending:
            type_colors = {
                "observation": "#5f87af",
                "music_spec":  "#e8a020",
                "ascii_art":   "#4a9eff",
                "commentary":  "#5f87af",
                "ux_review":   "#9b59b6",
            }
            color = type_colors.get(pending.output_type, "#5f87af")
            header_w.update(Text(f"[{pending.output_type.upper()}]  {pending.timestamp}", style=f"bold {color}"))
            content_w.update(Text(pending.content, style="white"))
            hint_w.update(Text("[y] approve    [n] reject", style="dim #e8a020"))
            return

        if self._chat_thread:
            t = Text()
            for msg in self._chat_thread[-10:]:
                is_test = msg.get("test", False)
                if msg["role"] == "user":
                    label = "dim #9b59b6" if is_test else "dim #e8a020"
                    tag   = "?TEST" if is_test else "YOU"
                    t.append(f"{msg['time']}  {tag}\n", style=label)
                    t.append(f"{msg['content']}\n\n", style="dim white" if is_test else "white")
                else:
                    label = "dim #9b59b6" if is_test else "dim #4a9eff"
                    tag   = "NEON [sandbox]" if is_test else "NEON"
                    t.append(f"{msg['time']}  {tag}\n", style=label)
                    t.append(f"{msg['content']}\n\n", style="dim #888" if is_test else "dim #c0c0d0")
            header_w.update(Text("CHAT", style="bold #4a9eff"))
            content_w.update(t)
            hint_w.update(Text("[c] reply  [?msg] test  [Esc] exit  [o] observe", style="dim #2a3a5a"))
            return

        header_w.update(Text("— awaiting output —", style="dim #2a3a5a"))
        content_w.update(Text(""))
        hint_w.update(Text(""))

    def _refresh_history(self) -> None:
        try:
            content_w = self.query_one("#history-content", Static)
        except Exception:
            return
        if not self._history:
            content_w.update(Text("No output yet this session.\n\nPress [c] to ask NEON anything.\nPress [o] to observe the dashboard.", style="dim #2a3a5a"))
            return
        _symbols = {"approved": "✓", "rejected": "✗", "blocked": "✕", "error": "!"}
        _colors  = {"approved": "#00c040", "rejected": "#c03040", "blocked": "#e8a020", "error": "#c03040"}
        t = Text()
        for item in reversed(self._history[-20:]):
            verdict = item.get("verdict", "?")
            sym_color = _colors.get(verdict, "#5f87af")
            t.append(f"{item.get('time', '--:--')} ", style="dim #2a3a5a")
            t.append(f"[{item.get('type', '?')[:3].upper()}] ", style="dim #5f87af")
            t.append(f"{_symbols.get(verdict, '?')}\n", style=f"bold {sym_color}")
            content = item.get("content", "")
            if content:
                preview = content[:120] + ("…" if len(content) > 120 else "")
                t.append(f"{preview}\n\n", style="dim #4a5568")
        content_w.update(t)

    def _build_context(self) -> dict:
        return _build_neon_context()

    @work(exclusive=True)
    async def _generate(self, gen_type: str, prompt: str = "", extra: str = "") -> None:
        import asyncio
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None:
            return
        self._generating = True
        self._refresh_pending_display()

        if gen_type == "observation":
            output = await asyncio.to_thread(bot.generate_observation, self._build_context(), extra)
        elif gen_type == "ux_review":
            output = await asyncio.to_thread(bot.generate_ux_review)
        elif gen_type == "music_spec":
            output = await asyncio.to_thread(bot.generate_music_spec)
        elif gen_type == "ascii_art":
            output = await asyncio.to_thread(bot.generate_ascii_art)
        elif gen_type == "chat":
            output = await asyncio.to_thread(bot.chat, prompt, self._build_context())
        elif gen_type == "test":
            output = await asyncio.to_thread(bot.test_response, prompt)
        else:
            self._generating = False
            return

        self._generating = False

        if output.output_type == "blocked":
            self._history.append({"time": output.timestamp, "type": "blocked", "verdict": "blocked", "content": ""})
            self._refresh_history()
        elif gen_type == "chat":
            self._chat_thread.append({"role": "user",      "content": prompt,          "time": output.timestamp})
            self._chat_thread.append({"role": "assistant", "content": output.content,  "time": output.timestamp})
            self._history.append({"time": output.timestamp, "type": "chat", "verdict": "approved", "content": output.content})
            self._refresh_history()
            try:
                self.query_one("#bots-input", Input).focus()
            except Exception:
                pass
        elif gen_type == "test":
            self._chat_thread.append({"role": "user",      "content": f"? {prompt}",   "time": output.timestamp, "test": True})
            self._chat_thread.append({"role": "assistant", "content": output.content,  "time": output.timestamp, "test": True})
            self._refresh_history()
            try:
                self.query_one("#bots-input", Input).focus()
            except Exception:
                pass
        elif bot.pending is None:
            self._history.append({"time": output.timestamp, "type": "error", "verdict": "error", "content": ""})
            self._refresh_history()
        else:
            first_line = output.content.split("\n")[0][:120]
            notify(f"NEON: {first_line}")

        self._refresh_pending_display()
        self._refresh_watcher()

    def _guard_pending(self) -> bool:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot and bot.pending:
            try:
                self.query_one("#pending-hint", Static).update(
                    Text("Judge current output first  [y] / [n]", style="bold #c03040")
                )
            except Exception:
                pass
            return True
        return False

    def action_generate_observation(self) -> None:
        self._trust_pending = None
        if self._guard_pending() or self._generating:
            return
        self._input_mode = "obs_context"
        inp = self.query_one("#bots-input", Input)
        inp.placeholder = "What should NEON focus on? (Enter to skip)…"
        inp.value = ""
        inp.focus()

    def action_generate_ux(self) -> None:
        if not self._guard_pending():
            self._generate("ux_review")

    def action_generate_music(self) -> None:
        if not self._guard_pending():
            self._generate("music_spec")

    def action_generate_art(self) -> None:
        if not self._guard_pending():
            self._generate("ascii_art")

    def action_ask_mode(self) -> None:
        self._trust_pending = None
        if self._guard_pending():
            return
        self._input_mode = "ask"
        inp = self.query_one("#bots-input", Input)
        inp.placeholder = "Ask NEON anything…"
        inp.value = ""
        inp.focus()

    def action_cancel_ask(self) -> None:
        self._input_mode = None
        inp = self.query_one("#bots-input", Input)
        inp.placeholder = "[c] to chat with NEON…"
        inp.value = ""
        inp.blur()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        mode = self._input_mode
        inp = self.query_one("#bots-input", Input)
        inp.value = ""
        if mode == "obs_context":
            self._input_mode = None
            inp.placeholder = "[c] to chat with NEON…"
            inp.blur()
            self._generate("observation", extra=value)
        elif value.startswith("?") and len(value) > 1:
            self._input_mode = "ask"
            self._generate("test", prompt=value[1:].strip())
        elif value:
            self._input_mode = "ask"
            self._generate("chat", prompt=value)

    def action_approve(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None or bot.pending is None:
            return
        output = bot.record_verdict("approved")
        if output:
            self._history.append({"time": output.timestamp, "type": output.output_type, "verdict": "approved", "content": output.content})
            notes = load_notes()
            notes.append({
                "timestamp": output.timestamp,
                "text": output.content,
                "tags": ["#neon", f"#{output.output_type}"],
            })
            save_notes(notes)
        self._refresh_pending_display()
        self._refresh_history()
        self._update_bot_widget()
        if output:
            try:
                self.query_one("#pending-hint", Static).update(
                    Text("✓ Saved to notes", style="bold #00c040")
                )
            except Exception:
                pass
            self.set_timer(2, self._refresh_pending_display)

    def action_reject(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None or bot.pending is None:
            return
        output = bot.record_verdict("rejected")
        if output:
            self._history.append({"time": output.timestamp, "type": output.output_type, "verdict": "rejected", "content": output.content})
        self._refresh_pending_display()
        self._refresh_history()

    def action_save_chat(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot and bot.pending:
            return  # pending output uses [y] approve instead
        last_neon = next(
            (m for m in reversed(self._chat_thread) if m["role"] == "assistant" and not m.get("test")),
            None,
        )
        if last_neon is None:
            return
        notes = load_notes()
        notes.append({
            "timestamp": last_neon["time"],
            "text": last_neon["content"],
            "tags": ["#neon", "#chat"],
        })
        save_notes(notes)
        try:
            self.query_one("#pending-hint", Static).update(
                Text("✓ Saved to notes", style="bold #00c040")
            )
        except Exception:
            pass
        self.set_timer(2, self._refresh_pending_display)

    def action_trust_up(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None or self._generating:
            return
        current = bot.trust_level
        if self._trust_pending == "+1":
            self._trust_pending = None
            new_level = bot.adjust_trust(+1)
            self._refresh_title()
            watcher: Watcher | None = getattr(self.app, "_watcher", None)
            if watcher:
                watcher.flag(f"Trust raised to {new_level} ({permissions.level_name(new_level)})", "info")
            self._refresh_watcher()
            self._update_bot_widget()
        else:
            self._trust_pending = "+1"
            try:
                self.query_one("#pending-hint", Static).update(
                    Text(f"Raise trust L{current} → L{current+1}? Press [+] again to confirm, any other key to cancel.", style="bold #e8a020")
                )
            except Exception:
                pass

    def action_trust_down(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None or self._generating:
            return
        current = bot.trust_level
        if self._trust_pending == "-1":
            self._trust_pending = None
            new_level = bot.adjust_trust(-1)
            self._refresh_title()
            watcher: Watcher | None = getattr(self.app, "_watcher", None)
            if watcher:
                watcher.flag(f"Trust reduced to {new_level} ({permissions.level_name(new_level)})", "warning")
            self._refresh_watcher()
            self._update_bot_widget()
        else:
            self._trust_pending = "-1"
            try:
                self.query_one("#pending-hint", Static).update(
                    Text(f"Lower trust L{current} → L{current-1}? Press [-] again to confirm, any other key to cancel.", style="bold #c03040")
                )
            except Exception:
                pass

    def action_open_persona(self) -> None:
        self.app.push_screen(PersonaScreen())

    def action_export_notes(self) -> None:
        result = export_notes()
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot:
            bot.invalidate_corpus_cache()
        self._insp_count = inspiration_count()
        try:
            self.query_one("#pending-hint", Static).update(
                Text(f"Exported → {result}", style="dim #00c040")
            )
        except Exception:
            pass

    def _update_bot_widget(self) -> None:
        try:
            self.app.query_one("#bot-widget", BotWidget).refresh_data()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Persona editor screen
# ══════════════════════════════════════════════════════════════════════════════

class PersonaScreen(Screen):
    BINDINGS = [
        ("s", "save_persona", "Save"),
        ("q", "discard", "Back"),
        ("a", "add_trait", "Add Trait"),
        ("d", "delete_trait", "Del Trait"),
        ("escape", "cancel_input", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("", id="persona-title", classes="sub-title")
        with ScrollableContainer(id="persona-body"):
            yield Static("NAME", classes="persona-label")
            yield Input(id="field-name", placeholder="Bot name…")
            yield Static("PHILOSOPHY", classes="persona-label")
            yield Input(id="field-philosophy", placeholder="Aesthetic philosophy…")
            yield Static("CONSTRAINT", classes="persona-label")
            yield Input(id="field-constraint", placeholder="What it never does…")
            yield Static("", id="traits-header", classes="persona-label")
            yield Static("", id="traits-list")
        yield Input(placeholder="", id="persona-input", classes="hidden")
        yield Static("", id="persona-hint")
        yield Static(
            "[bold #e8a020][a][/bold #e8a020][white] add trait  [/white]"
            "[bold #e8a020][d][/bold #e8a020][white] del trait  [/white]"
            "[bold #e8a020][s][/bold #e8a020][white] save  [/white]"
            "[bold #e8a020][q][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        self._persona: dict = dict(bot.persona) if bot else {}
        self._input_mode: str | None = None
        self.query_one("#persona-title", Static).update("[bold white]NEON  ·  PERSONA EDITOR[/bold white]")
        if bot:
            self.query_one("#field-name", Input).value = self._persona.get("name", "")
            self.query_one("#field-philosophy", Input).value = self._persona.get("aesthetic_philosophy", "")
            self.query_one("#field-constraint", Input).value = self._persona.get("never_does", "")
        self._refresh_traits()

    def _refresh_traits(self) -> None:
        traits = self._persona.get("traits", [])
        try:
            self.query_one("#traits-header", Static).update(
                f"[bold #e8a020]TRAITS  ({len(traits)})[/bold #e8a020]"
            )
            list_w = self.query_one("#traits-list", Static)
        except Exception:
            return
        if not traits:
            list_w.update(Text("  No traits defined.  Press [a] to add one.", style="dim #2a3a5a"))
            return
        t = Text()
        for i, trait in enumerate(traits, 1):
            t.append(f"  {i}.  ", style="dim #e8a020")
            t.append(f"{trait}\n", style="white")
        list_w.update(t)

    def action_add_trait(self) -> None:
        if self._input_mode:
            return
        self._input_mode = "add"
        inp = self.query_one("#persona-input", Input)
        inp.placeholder = "New trait text…"
        inp.value = ""
        inp.remove_class("hidden")
        inp.focus()
        try:
            self.query_one("#persona-hint", Static).update(
                Text("Enter to confirm  ·  Escape to cancel", style="dim #5f87af")
            )
        except Exception:
            pass

    def action_delete_trait(self) -> None:
        if self._input_mode:
            return
        traits = self._persona.get("traits", [])
        if not traits:
            return
        self._input_mode = "delete"
        inp = self.query_one("#persona-input", Input)
        inp.placeholder = f"Trait # to delete  (1–{len(traits)})…"
        inp.value = ""
        inp.remove_class("hidden")
        inp.focus()
        try:
            self.query_one("#persona-hint", Static).update(
                Text(f"Enter number 1–{len(traits)}  ·  Escape to cancel", style="dim #c03040")
            )
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        inp_id = event.input.id
        val = event.value.strip()

        if inp_id == "field-name":
            self.query_one("#field-philosophy", Input).focus()
            return
        if inp_id == "field-philosophy":
            self.query_one("#field-constraint", Input).focus()
            return
        if inp_id == "field-constraint":
            self.set_focus(None)
            return
        if inp_id != "persona-input":
            return

        mode = self._input_mode
        self._cancel_input()

        if not val:
            return
        if mode == "add":
            self._persona.setdefault("traits", []).append(val)
        elif mode == "delete":
            try:
                idx = int(val) - 1
                traits = self._persona.get("traits", [])
                if 0 <= idx < len(traits):
                    traits.pop(idx)
                    self._persona["traits"] = traits
            except ValueError:
                pass
        self._refresh_traits()

    def action_cancel_input(self) -> None:
        if self._input_mode:
            self._cancel_input()
        else:
            self.app.pop_screen()

    def _cancel_input(self) -> None:
        self._input_mode = None
        inp = self.query_one("#persona-input", Input)
        inp.add_class("hidden")
        inp.value = ""
        try:
            self.query_one("#persona-hint", Static).update(Text(""))
        except Exception:
            pass

    def action_save_persona(self) -> None:
        name = self.query_one("#field-name", Input).value.strip()
        phil = self.query_one("#field-philosophy", Input).value.strip()
        const = self.query_one("#field-constraint", Input).value.strip()
        if name:
            self._persona["name"] = name
        if phil:
            self._persona["aesthetic_philosophy"] = phil
        if const:
            self._persona["never_does"] = const

        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot:
            bot.persona.update(self._persona)

        save_persona(self._persona)
        self.app.pop_screen()

    def action_discard(self) -> None:
        if self._input_mode:
            self._cancel_input()
        else:
            self.app.pop_screen()


# ══════════════════════════════════════════════════════════════════════════════
# Security screen
# ══════════════════════════════════════════════════════════════════════════════

class SecurityScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("s", "scan", "Scan"),
        ("t", "request_trash", "Empty Trash"),
        ("d", "request_desktop", "Archive Desktop"),
        ("k", "check_key", "Rotate Key"),
        ("y", "confirm_action", "Confirm"),
        ("n", "cancel_action", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  SECURITY  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="sec-table", cursor_type="row", show_cursor=False)
        yield Static("", id="sec-ports")
        yield Static("", id="sec-maint")
        yield Static("", id="sec-msg", classes="sub-msg")
        yield Static("", id="sec-hint", classes="sub-hint")

    def on_mount(self) -> None:
        self.query_one("#sec-table", DataTable).can_focus = False
        self._pending_action: str | None = None
        self._scan_timer = None
        self._refresh_hint()
        self._run_scan()

    def on_hide(self) -> None:
        if self._scan_timer is not None:
            self._scan_timer.stop()
            self._scan_timer = None

    def on_show(self) -> None:
        self._scan_timer = self.set_interval(30, self._run_scan)
        self._run_scan()

    def _refresh_hint(self) -> None:
        try:
            w = self.query_one("#sec-hint", Static)
            if self._pending_action:
                w.update(Text("[y] confirm    [n] cancel", style="bold #c03040"))
            else:
                w.update(
                    "[dim #e8a020][s][/dim #e8a020][dim #5f87af] scan  [/dim #5f87af]"
                    "[dim #e8a020][t][/dim #e8a020][dim #5f87af] trash  [/dim #5f87af]"
                    "[dim #e8a020][d][/dim #e8a020][dim #5f87af] desktop  [/dim #5f87af]"
                    "[dim #e8a020][k][/dim #e8a020][dim #5f87af] key  [/dim #5f87af]"
                    "[dim #e8a020][q][/dim #e8a020][dim #5f87af] back[/dim #5f87af]"
                )
        except Exception:
            pass

    def action_scan(self) -> None:
        self._run_scan()

    def action_request_trash(self) -> None:
        if self._pending_action:
            return
        self._pending_action = "trash"
        self.query_one("#sec-msg", Static).update(
            Text("Empty Trash — this cannot be undone.  [y] confirm  [n] cancel", style="bold #e8a020")
        )
        self._refresh_hint()

    def action_request_desktop(self) -> None:
        if self._pending_action:
            return
        self._pending_action = "desktop"
        self.query_one("#sec-msg", Static).update(
            Text("Archive Desktop → Desktop/Archive/today  [y] confirm  [n] cancel", style="bold #e8a020")
        )
        self._refresh_hint()

    def action_check_key(self) -> None:
        days, msg = security.check_api_key_age()
        color = "#c03040" if days > 90 else ("#e8a020" if days > 30 else "#00c040")
        t = Text(f"API Key: {msg}", style=f"bold {color}")
        if days < 0 or days > 30:
            t.append("  → opening console…", style="dim #5f87af")
            security.open_key_rotation()
        self.query_one("#sec-msg", Static).update(t)

    def action_confirm_action(self) -> None:
        if not self._pending_action:
            return
        action = self._pending_action
        self._pending_action = None
        self._refresh_hint()
        self._run_maintenance(action)

    def action_cancel_action(self) -> None:
        self._pending_action = None
        self.query_one("#sec-msg", Static).update(Text(""))
        self._refresh_hint()

    @work(exclusive=True)
    async def _run_maintenance(self, action: str) -> None:
        import asyncio
        msg_w = self.query_one("#sec-msg", Static)
        maint_w = self.query_one("#sec-maint", Static)
        msg_w.update(Text("Running…", style="dim #e8a020"))

        if action == "trash":
            ok, result = await asyncio.to_thread(security.empty_trash)
        elif action == "desktop":
            ok, result = await asyncio.to_thread(security.archive_desktop)
        else:
            return

        color = "#00c040" if ok else "#c03040"
        msg_w.update(Text(result, style=f"bold {color}"))

        # Ask NEON to observe the result (trust level gated)
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot and bot.trust_level >= 1:
            commentary = await asyncio.to_thread(
                bot.generate_commentary,
                f"Maintenance task completed: {result}"
            )
            if commentary and commentary.output_type not in ("blocked",):
                maint_w.update(Text(f'NEON: "{commentary.content}"', style="italic dim #5f87af"))

    @work(exclusive=True)
    async def _run_scan(self) -> None:
        import asyncio
        msg = self.query_one("#sec-msg", Static)
        if not self._pending_action:
            msg.update(Text("Scanning…", style="dim #e8a020"))

        checks, ports = await asyncio.gather(
            asyncio.to_thread(security.run_checks),
            asyncio.to_thread(security.get_open_ports),
        )

        table = self.query_one("#sec-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Check", "Status", "")

        pass_count = 0
        for label, status, is_good in checks:
            if is_good:
                pass_count += 1
            status_text = Text(status, style="bold #00c040" if is_good else "bold #c03040")
            indicator = Text("✓" if is_good else "✗", style="bold #00c040" if is_good else "bold #c03040")
            table.add_row(label, status_text, indicator)

        ports_widget = self.query_one("#sec-ports", Static)
        if ports:
            port_list = "  ".join(str(p) for p in ports[:20])
            overflow = f"  +{len(ports) - 20} more" if len(ports) > 20 else ""
            ports_widget.update(Text(f"Open ports: {port_list}{overflow}", style="dim #5f87af"))
        else:
            ports_widget.update(Text("Open ports: none detected", style="dim #00c040"))

        total = len(checks)
        color = "#00c040" if pass_count == total else ("#e8a020" if pass_count >= total // 2 else "#c03040")
        if not self._pending_action:
            msg.update(Text(f"{pass_count}/{total} checks passed", style=f"bold {color}"))


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════

class DarkHourApp(App):
    CSS_PATH = "tui.tcss"

    def on_mount(self) -> None:
        self._music_proc = None
        self._music_muted = False
        self._current_song = ""
        self._morning_brief = None
        _boot_sound()
        self.set_timer(0.8, self._start_music)
        self.set_timer(2.5, self._run_morning_brief)
        config = load_config()
        self.is_admin = config["is_admin"]
        self._memory = MemoryManager()
        self._watcher = Watcher()
        self._bot = Bot(load_persona(), self._memory, self._watcher)
        self.push_screen(DashboardScreen(config["name"], self.is_admin))

    @work(exclusive=False)
    async def _run_morning_brief(self) -> None:
        import asyncio
        bot = getattr(self, "_bot", None)
        if bot is None:
            return
        context = await asyncio.to_thread(_build_neon_context)
        output = await asyncio.to_thread(bot.generate_morning_brief, context)
        self._morning_brief = output
        first_line = output.content.split("\n")[0][:120]
        notify(f"NEON: {first_line}")
        try:
            self.query_one("#bot-widget", BotWidget).refresh_data()
        except Exception:
            pass

    def _start_music(self) -> None:
        self._music_proc = _start_bg_music()
        if self._music_proc:
            self._current_song = "VICE CITY"
        # Apply mute if the user pressed M during the 2s boot delay
        if self._music_muted and self._music_proc:
            try:
                pgid = os.getpgid(self._music_proc.pid)
                os.killpg(pgid, signal.SIGSTOP)
            except Exception:
                pass

    def action_toggle_mute(self) -> None:
        self._music_muted = not self._music_muted
        proc = self._music_proc
        if proc and proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                sig = signal.SIGSTOP if self._music_muted else signal.SIGCONT
                os.killpg(pgid, sig)
            except Exception:
                pass
        try:
            self.query_one(FooterControls).set_muted(self._music_muted, self._current_song)
        except Exception:
            pass  # not on dashboard screen


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app = DarkHourApp()
    try:
        app.run()
    finally:
        proc = getattr(app, "_music_proc", None)
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            os.remove(_MUSIC_PID_FILE)
        except Exception:
            pass
        memory = getattr(app, "_memory", None)
        if memory:
            try:
                memory.close_session()
            except Exception:
                pass
    print("\n\033[2m\033[38;5;67mUntil the next Dark Hour.\033[0m\n")


if __name__ == "__main__":
    main()
