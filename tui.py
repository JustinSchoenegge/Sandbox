"""
tui.py  —  Dark Hour Dashboard (Textual TUI)
Persona 3 × GTA aesthetic.  Replaces app.py as the main entry point.
"""

import os
import platform
import shlex
import shutil
import signal
import subprocess
from datetime import datetime, timedelta

_SYSTEM = platform.system()   # "Darwin" | "Linux" | "Windows"

from rich.text import Text
from rich.console import RenderableType

from textual.app import App, ComposeResult
from textual.binding import Binding
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
from habits import load_habits, is_done_today, calculate_streak
from tasks import load_tasks, save_tasks
from notes import load_notes, save_notes, get_notes_meta
from music import load_ideas, save_ideas
from portfolio import load_portfolio, calculate_weights, save_portfolio, check_alignment, safe_pnl
from stocks import STOCKS
from game import main as play_game
import vitals
import security
import permissions
import context as _ctx_mod
from memory import MemoryManager
from watcher import Watcher
from bot import Bot, BotOutput, load_persona, save_persona
from inspiration import file_count as inspiration_count, export_notes
from prices import cached_changes
from screens.habits import HabitsScreen
from screens.portfolio import PortfolioScreen

load_env()

# ── boot sound ─────────────────────────────────────────────────────────────────

def _boot_sound() -> None:
    if _SYSTEM == "Darwin":
        path = "/System/Library/Sounds/Glass.aiff"
        if os.path.exists(path):
            subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif _SYSTEM == "Linux":
        # Use paplay (PulseAudio) or aplay with a fallback system bell
        for cmd in (["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
                    ["aplay", "/usr/share/sounds/alsa/Front_Center.wav"]):
            if shutil.which(cmd[0]) and os.path.exists(cmd[1]):
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break


_MUSIC_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".music.pid")


def _kill_music_from_pidfile() -> None:
    """Kill music process via PID file — works at startup and in signal handlers."""
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


def _audio_loop_cmd(path: str) -> "list[str] | None":
    """Return the command list to loop an audio file, or None if no player found."""
    if _SYSTEM == "Darwin":
        quoted = shlex.quote(path)
        return ["bash", "-c", f"while true; do afplay {quoted}; done"]
    if _SYSTEM == "Linux":
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--loop=inf", "--really-quiet", path]
        if shutil.which("cvlc"):
            return ["cvlc", "--repeat", "--no-video", "--quiet", path]
        if shutil.which("vlc"):
            return ["vlc", "--repeat", "--no-video", "--quiet", path]
    return None


def _start_bg_music(bg_path: str = "") -> "subprocess.Popen | None":
    """Loop an audio file in the background. Uses bg_path or falls back to vicecity.m4a."""
    _kill_music_from_pidfile()
    base = os.path.dirname(os.path.abspath(__file__))
    if bg_path and os.path.exists(bg_path):
        path = bg_path
    else:
        path = os.path.join(base, "assets", "vicecity.m4a")
    if not os.path.exists(path):
        return None
    shell_cmd = _audio_loop_cmd(path)
    if shell_cmd is None:
        return None
    proc = subprocess.Popen(
        shell_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
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
        self._is_live = False

    def on_mount(self) -> None:
        self._clock = ""
        self._date = ""
        self._tick()
        self.set_interval(1, self._tick)
        self._check_live()
        self.set_interval(5, self._check_live)

    def _tick(self) -> None:
        now = datetime.now()
        self._clock = now.strftime("%I:%M %p")
        self._date = now.strftime("%a %b %d")
        self.refresh()

    @work(exclusive=True)
    async def _check_live(self) -> None:
        import asyncio
        try:
            flags = ["-ix"] if _SYSTEM == "Darwin" else ["-x"]
            r = await asyncio.to_thread(
                lambda: subprocess.run(["pgrep"] + flags + ["obs"], capture_output=True, timeout=1)
            )
            live = r.returncode == 0
            if live != self._is_live:
                self._is_live = live
                self.refresh()
        except Exception:
            pass

    def render(self) -> RenderableType:
        t = Text(justify="center")
        t.append("DARK HOUR", style="bold white")
        t.append("  ◐  ", style="dim #4a9eff")
        t.append(f"{get_greeting()}, {self._user_name}", style="bold #e8a020")
        if self._is_admin:
            t.append("  [ADMIN]", style="bold #ff2244")
        if self._is_live:
            t.append("  ● LIVE", style="bold #c03040")
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
            meta = get_notes_meta()
            count = meta.get("count", 0)
            last_text = meta.get("last_text", "")
            t = Text(justify="center")
            t.append(f"{count}\n", style="bold #e8a020")
            t.append(f"NOTE{'S' if count != 1 else ''}\n", style="dim #4a5568")
            if last_text:
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
                    pnl = safe_pnl(r["current_price"], r["avg_cost"])
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


class FooterControls(Widget):
    """Footer bar: nav key hints left, music status indicator pinned right.

    Reads mute state directly from the app on a 1s tick rather than waiting
    for external set_muted calls — avoids silent query_one failures.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._muted: bool = False
        self._song: str = ""

    def on_mount(self) -> None:
        self._sync()
        self.set_interval(1, self._sync)

    def _sync(self) -> None:
        muted = getattr(self.app, "_music_muted", False)
        song  = getattr(self.app, "_current_song", "")
        if muted != self._muted or song != self._song:
            self._muted = muted
            self._song  = song
            self.refresh()

    def set_muted(self, muted: bool, song: str = "") -> None:
        """Explicit update — still supported for immediate response."""
        self._muted = muted
        self._song  = song
        self.refresh()

    def render(self) -> RenderableType:
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
        if self._muted:
            music.append("✕ MUTED", style="bold #c03040")
        else:
            music.append(f"♪  {self._song}" if self._song else "♪  LIVE", style="bold #00c040")

        grid = RichTable.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row(nav, music)
        return grid


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
            if temp:
                try:
                    temp_c = float(temp.replace("°C", "").replace("°F", "").strip())
                    temp_style = "#00c040" if temp_c < 50 else ("#e8a020" if temp_c < 70 else "bold #c03040")
                except ValueError:
                    temp_style = "#e8a020"
                t.append(temp, style=temp_style)
            else:
                t.append("—", style="dim #5f87af")

            t.append("  ·  ", style="dim #1e3a5f")

            fan = data.get("fan")
            t.append("FAN ", style="dim #5f87af")
            if fan:
                # Color the thermal state suffix if present (e.g. "2x · nom")
                if " · " in fan:
                    prefix, state = fan.rsplit(" · ", 1)
                    t.append(f"{prefix} · ", style="#5f87af")
                    state_style = {"nom": "#00c040", "fair": "#e8a020", "srs!": "bold #c03040", "CRIT": "bold #c03040"}.get(state, "#5f87af")
                    t.append(state, style=state_style)
                else:
                    t.append(fan, style="#5f87af")
            else:
                t.append("—", style="dim #5f87af")

            self.update(t)
        except Exception:
            self.update(Text("vitals unavailable", style="dim"))


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard screen
# ══════════════════════════════════════════════════════════════════════════════

class DashboardScreen(Screen):
    BINDINGS = [
        ("1", "push_screen_nav(0)", "Habits"),
        ("2", "push_screen_nav(1)", "Tasks"),
        ("3", "push_screen_nav(2)", "Notes"),
        ("4", "push_screen_nav(3)", "Game"),
        ("5", "push_screen_nav(4)", "Portfolio"),
        ("6", "push_screen_nav(5)", "Music"),
        ("7", "push_screen_nav(6)", "Bots"),
        ("8", "push_screen_nav(7)", "Security"),
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

    def action_push_screen_nav(self, idx: int) -> None:
        if idx == 7 and not self._is_admin:
            self.notify("Security screen requires admin access", severity="warning")
            return
        self.app.push_screen(_NAV[idx][2](self._name))


# ══════════════════════════════════════════════════════════════════════════════
# Habits screen
# ══════════════════════════════════════════════════════════════════════════════

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
            "[bold #e8a020][[a]][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
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
        if event.character and event.character.isdigit() and event.character != "0":
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
                        invalidate_context_cache()
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
                    invalidate_context_cache()
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
            "[bold #e8a020][[a]][/bold #e8a020][white] add note  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
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
                    invalidate_context_cache()
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
        ("w", "mark_written", "Written"),
        ("b", "change_bg", "Bg Song"),
        ("escape", "cancel_input", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  MUSIC IDEAS  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="music-table", cursor_type="row", show_cursor=False)
        with Horizontal(id="music-inputs", classes="hidden"):
            yield Input(id="music-title-in", placeholder="Song title…")
            yield Input(id="music-vibe-in", placeholder="Vibe / mood…")
        yield Input(id="music-bg-in", placeholder="Audio file path (e.g. vicecity.m4a)…", classes="hidden")
        yield Static("", id="music-msg", classes="sub-msg")
        yield Static(
            "[bold #e8a020][1-9][/bold #e8a020][white] detail  [/white]"
            "[bold #e8a020][[a]][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][[w]][/bold #e8a020][white] written  [/white]"
            "[bold #e8a020][[b]][/bold #e8a020][white] bg song  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
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
        msg = self.query_one("#music-msg", Static)
        if self._mode == "written":
            if event.key == "escape":
                self._mode = None
                msg.update(Text(""))
                return
            if event.character and event.character.isdigit() and event.character != "0":
                event.stop()
                idx = int(event.character) - 1
                try:
                    ideas = load_ideas()
                    if 0 <= idx < len(ideas):
                        ideas[idx]["song"] = None if ideas[idx].get("song") else "✓"
                        save_ideas(ideas)
                        title = ideas[idx]["title"]
                        state = "written ✓" if ideas[idx]["song"] else "unwritten"
                        msg.update(Text(f"'{title}' marked as {state}.", style="bold #00c040"))
                        self._populate_table()
                    else:
                        msg.update(Text(f"Enter 1–{len(ideas)}.", style="bold #c03040"))
                except Exception:
                    pass
                self._mode = None
            return
        if self._mode is not None:
            return
        if event.character and event.character.isdigit() and event.character != "0":
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
                    msg.update(detail)
                else:
                    msg.update(Text(f"Enter 1–{len(ideas)}.", style="bold #c03040"))
            except Exception:
                pass

    def action_mark_written(self) -> None:
        if self._mode is not None:
            return
        ideas = load_ideas()
        if not ideas:
            self.query_one("#music-msg", Static).update(Text("No ideas to mark.", style="dim"))
            return
        self._mode = "written"
        self.query_one("#music-msg", Static).update(
            Text(f"Press [1-{len(ideas)}] to toggle written  ·  [Esc] cancel", style="dim #e8a020")
        )

    def action_change_bg(self) -> None:
        if self._mode is not None:
            return
        self._mode = "bg"
        inp = self.query_one("#music-bg-in", Input)
        inp.value = ""
        inp.remove_class("hidden")
        inp.focus()

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
        try:
            bg_in = self.query_one("#music-bg-in", Input)
            bg_in.add_class("hidden")
            bg_in.value = ""
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = self.query_one("#music-msg", Static)
        if event.input.id == "music-bg-in":
            path = event.value.strip()
            inp = self.query_one("#music-bg-in", Input)
            inp.add_class("hidden")
            inp.value = ""
            self._mode = None
            if path:
                self.app._change_bg_music(path, msg)
            return
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
        yield Static("[bold white]═══  STOCK GUESSER  ═══[/bold white]", classes="sub-title")
        yield Static("", id="game-body")
        yield Static(
            "[bold #e8a020][[enter]][/bold #e8a020][white] launch game  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_show(self) -> None:
        self._render_splash()

    def _render_splash(self) -> None:
        from stocks import STOCKS, PRICES_AS_OF
        t = Text()
        t.append("\n  STOCK GUESSER\n\n", style="bold #e8a020")
        t.append("  Guess the price of a random stock to within 5% to win.\n", style="dim #5f87af")
        t.append(f"  {len(STOCKS)} stocks in the pool  ·  prices approximate as of {PRICES_AS_OF}\n\n",
                 style="dim #2a3a5a")
        t.append("  Scoring\n", style="bold #4a9eff")
        t.append("  1 attempt  →  perfect\n", style="dim #5f87af")
        t.append("  2–3 attempts  →  solid read\n", style="dim #5f87af")
        t.append("  4+ attempts  →  keep studying\n\n", style="dim #5f87af")
        t.append("  Press ", style="dim #5f87af")
        t.append("[enter]", style="bold white")
        t.append(" to start", style="dim #5f87af")
        try:
            self.query_one("#game-body", Static).update(t)
        except Exception:
            pass

    def action_launch(self) -> None:
        try:
            with self.app.suspend():
                play_game(self._name)
            self._render_splash()
        except Exception as e:
            t = Text()
            t.append(f"\n  Game error: {e}\n\n", style="bold #c03040")
            t.append("  Press ", style="dim #5f87af")
            t.append("[q]", style="bold white")
            t.append(" to go back.", style="dim #5f87af")
            try:
                self.query_one("#game-body", Static).update(t)
            except Exception:
                pass


def invalidate_context_cache() -> None:
    _ctx_mod.invalidate_context_cache()


def _build_neon_context() -> dict:
    return _ctx_mod.build_context_dict()


# ══════════════════════════════════════════════════════════════════════════════
# Bots screen
# ══════════════════════════════════════════════════════════════════════════════

class BotsScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("c", "ask_mode", "Chat"),
        ("o", "generate_observation", "Observe"),
        ("u", "generate_ux", "UX Review"),
        ("g", "generate_music", "Music"),
        ("a", "generate_art", "Art"),
        ("y", "approve", "Approve"),
        ("n", "reject", "Reject"),
        ("s", "save_chat", "Save"),
        ("p", "open_persona", "Persona"),
        ("e", "export_notes", "Export Notes"),
        ("plus", "trust_up", "Trust +"),
        ("minus", "trust_down", "Trust -"),
        ("escape", "cancel_ask", "Cancel"),
        ("t", "cycle_trait", "Trait"),
        ("x", "generate_synthesis", "Synthesis"),
        ("v", "generate_portfolio", "Portfolio"),
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
            "[[c]] chat  [[o]] observe  [[u]] ux  [[g]] music  [[a]] art  [[t]] trait  [[x]] synth  [[v]] port\n"
            "[[y]] approve  [[n]] reject  [[s]] save  [[e]] export  [[p]] persona  [+/-] trust  [[q]] back"
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
        self._active_trait: str | None = None
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
        trait_part = ""
        if getattr(self, "_active_trait", None):
            from bot import TRAITS
            tr = TRAITS.get(self._active_trait, {})
            trait_part = f"  [{tr.get('symbol', '')} {tr.get('name', '')}]"
        try:
            self.query_one("#bots-title", Static).update(f"[bold white]{title}{trait_part}[/bold white]")
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
        muted = getattr(self.app, "_music_muted", False)
        bar = Text(justify="center")
        bar.append("WATCHER  ", style="dim #2a3a5a")
        for label, ok in [("API", h.anthropic_api), ("MEM", h.memory_layer), ("♪", h.music_system), ("BOT", h.bot_online)]:
            if label == "♪" and muted:
                bar.append("✕ ", style="bold #c03040")
                bar.append(f"{label}  ", style="dim #c03040")
            else:
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
            hint_w.update(Text("[c] reply  [o] observe  [Esc] exit", style="dim #2a3a5a"))
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
        try:
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
            elif gen_type == "synthesis":
                output = await asyncio.to_thread(bot.generate_synthesis, self._build_context())
            elif gen_type == "portfolio_narrative":
                output = await asyncio.to_thread(bot.generate_portfolio_narrative, self._build_context())
            else:
                return

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

        except Exception as e:
            self._history.append({
                "time": datetime.now().strftime("%H:%M"),
                "type": "error",
                "verdict": "error",
                "content": str(e)[:120],
            })
            self._refresh_history()
        finally:
            self._generating = False
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

    def action_cycle_trait(self) -> None:
        order = [None, "power", "wisdom", "courage"]
        idx = order.index(self._active_trait) if self._active_trait in order else 0
        self._active_trait = order[(idx + 1) % len(order)]
        bot = getattr(self.app, "_bot", None)
        if bot:
            bot.set_trait(self._active_trait)
        self._refresh_title()

    def action_generate_synthesis(self) -> None:
        if not self._guard_pending():
            self._generate("synthesis")

    def action_generate_portfolio(self) -> None:
        if not self._guard_pending():
            self._generate("portfolio_narrative")

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
            inp.focus()
            self._generate("test", prompt=value[1:].strip())
        elif value:
            self._input_mode = "ask"
            inp.focus()
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
            invalidate_context_cache()
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
        invalidate_context_cache()
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
            if current + 1 >= 4 and not getattr(self.app, "is_admin", False):
                try:
                    self.query_one("#pending-hint", Static).update(
                        Text("Trust L4+ requires admin access.", style="bold #c03040")
                    )
                except Exception:
                    pass
                self.set_timer(2, self._refresh_pending_display)
                return
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
            "[bold #e8a020][[a]][/bold #e8a020][white] add trait  [/white]"
            "[bold #e8a020][[d]][/bold #e8a020][white] del trait  [/white]"
            "[bold #e8a020][[s]][/bold #e8a020][white] save  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot:
            # Deep-copy traits list so discard doesn't mutate the live bot
            self._persona: dict = {**bot.persona, "traits": list(bot.persona.get("traits", []))}
        else:
            self._persona = {}
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

        if not name:
            try:
                self.query_one("#persona-hint", Static).update(
                    Text("Name cannot be empty.", style="bold #c03040")
                )
            except Exception:
                pass
            return

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
        ("k", "check_key", "Key Age"),
        ("r", "rotate_key", "Rotate Key"),
        ("y", "confirm_action", "Confirm"),
        ("n", "cancel_action", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  SECURITY  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="sec-table", cursor_type="row", show_cursor=False)
        yield Static("", id="sec-ports")
        yield Static("", id="sec-maint")
        yield Static("", id="sec-msg", classes="sub-msg")
        yield Input(id="sec-key-input", placeholder="Paste new ANTHROPIC_API_KEY…", classes="hidden")
        yield Static("", id="sec-hint", classes="sub-hint")

    def on_mount(self) -> None:
        self.query_one("#sec-table", DataTable).can_focus = False
        self._pending_action: str | None = None
        self._scan_timer = None
        self._refresh_hint()
        checks, ports, ts = security.load_scan_cache()
        if checks is not None:
            self._display_cached(checks, ports, ts)
        if security.cache_age_hours() > 24:
            self._run_scan()

    def on_hide(self) -> None:
        if self._scan_timer is not None:
            self._scan_timer.stop()
            self._scan_timer = None

    def on_show(self) -> None:
        self._scan_timer = self.set_interval(86400, self._run_scan)
        checks, ports, ts = security.load_scan_cache()
        if checks is not None:
            self._display_cached(checks, ports, ts)
        if security.cache_age_hours() > 24:
            self._run_scan()

    def _display_cached(self, checks, ports, ts, scanning: bool = False) -> None:
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
        port_line = ""
        if ports:
            port_list = "  ".join(str(p) for p in ports[:20])
            overflow = f"  +{len(ports) - 20} more" if len(ports) > 20 else ""
            port_line = f"Open ports: {port_list}{overflow}"
        else:
            port_line = "Open ports: none detected"
        scan_age = ""
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                secs = int((datetime.now() - dt).total_seconds())
                if secs < 3600:
                    scan_age = f"{secs // 60}m ago"
                elif secs < 86400:
                    scan_age = f"{secs // 3600}h ago"
                else:
                    scan_age = f"{secs // 86400}d ago"
                port_line += f"\nLast scan: {scan_age}"
            except Exception:
                pass
        ports_widget.update(Text(port_line, style="dim #5f87af"))

        total = len(checks)
        key_count = security.count_api_keys()
        color = "#00c040" if pass_count == total else ("#e8a020" if pass_count >= total // 2 else "#c03040")
        if not self._pending_action:
            key_str = f"  ·  {key_count} API key{'s' if key_count != 1 else ''}"
            scan_note = "  ·  scanning…" if scanning else ""
            self.query_one("#sec-msg", Static).update(
                Text(f"{pass_count}/{total} checks passed{key_str}{scan_note}", style=f"bold {color}")
            )

    def _refresh_hint(self) -> None:
        try:
            w = self.query_one("#sec-hint", Static)
            if self._pending_action == "rotate_key":
                w.update(Text("[Enter] save    [n] cancel", style="bold #e8a020"))
            elif self._pending_action:
                w.update(Text("[y] confirm    [n] cancel", style="bold #c03040"))
            else:
                w.update(
                    "[dim #e8a020][[s]][/dim #e8a020][dim #5f87af] scan  [/dim #5f87af]"
                    "[dim #e8a020][[t]][/dim #e8a020][dim #5f87af] trash  [/dim #5f87af]"
                    "[dim #e8a020][[d]][/dim #e8a020][dim #5f87af] desktop  [/dim #5f87af]"
                    "[dim #e8a020][[k]][/dim #e8a020][dim #5f87af] key age  [/dim #5f87af]"
                    "[dim #e8a020][[r]][/dim #e8a020][dim #5f87af] rotate  [/dim #5f87af]"
                    "[dim #e8a020][[q]][/dim #e8a020][dim #5f87af] back[/dim #5f87af]"
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

    def action_rotate_key(self) -> None:
        if self._pending_action:
            return
        self._pending_action = "rotate_key"
        self.query_one("#sec-msg", Static).update(
            Text("Paste new ANTHROPIC_API_KEY and press Enter:", style="bold #e8a020")
        )
        inp = self.query_one("#sec-key-input", Input)
        inp.value = ""
        inp.remove_class("hidden")
        inp.focus()
        self._refresh_hint()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "sec-key-input":
            return
        new_key = event.value.strip()
        inp = self.query_one("#sec-key-input", Input)
        inp.add_class("hidden")
        inp.value = ""
        self._pending_action = None
        self._refresh_hint()
        if not new_key:
            return
        ok, result = security.update_api_key(new_key)
        color = "#00c040" if ok else "#c03040"
        self.query_one("#sec-msg", Static).update(Text(result, style=f"bold {color}"))
        watcher = getattr(self.app, "_watcher", None)
        if watcher:
            watcher.check_health(getattr(self.app, "_bot", None))

    def action_confirm_action(self) -> None:
        if not self._pending_action:
            return
        action = self._pending_action
        self._pending_action = None
        self._refresh_hint()
        self._run_maintenance(action)

    def action_cancel_action(self) -> None:
        self._pending_action = None
        try:
            inp = self.query_one("#sec-key-input", Input)
            inp.add_class("hidden")
            inp.value = ""
        except Exception:
            pass
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
        checks_cached, ports_cached, ts_cached = security.load_scan_cache()
        if checks_cached is not None:
            self._display_cached(checks_cached, ports_cached, ts_cached, scanning=True)
        elif not self._pending_action:
            self.query_one("#sec-msg", Static).update(Text("Scanning…", style="dim #e8a020"))

        checks, ports = await asyncio.gather(
            asyncio.to_thread(security.run_checks),
            asyncio.to_thread(security.get_open_ports),
        )

        if not checks and _SYSTEM != "Darwin":
            table = self.query_one("#sec-table", DataTable)
            table.clear(columns=True)
            table.add_columns("Notice", "")
            table.add_row(
                Text("macOS security checks not available on this platform.", style="dim #5f87af"),
                Text(""),
            )
            ports_widget = self.query_one("#sec-ports", Static)
            if ports:
                port_list = "  ".join(str(p) for p in ports[:20])
                ports_widget.update(Text(f"Open ports: {port_list}", style="dim #5f87af"))
            else:
                ports_widget.update(Text("Open ports: none detected", style="dim #00c040"))
            key_count = security.count_api_keys()
            self.query_one("#sec-msg", Static).update(
                Text(f"Port scan complete  ·  {key_count} API key{'s' if key_count != 1 else ''}", style="dim #5f87af")
            )
            return

        security.save_scan_cache(checks, ports)
        self._display_cached(checks, ports, datetime.now().isoformat(), scanning=False)


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════

class DarkHourApp(App):
    CSS_PATH = "tui.tcss"
    BINDINGS = [Binding("m", "toggle_mute", "Mute", priority=True)]

    def on_mount(self) -> None:
        self._music_proc = None
        self._music_muted = False
        self._current_song = ""
        self._morning_brief = None
        config = load_config()
        self.is_admin = config["is_admin"]
        self._bg_music_path = config.get("bg_music", "")
        _boot_sound()
        self.set_timer(0.8, self._start_music)
        self.set_timer(2.5, self._run_morning_brief)
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
        bg_path = getattr(self, "_bg_music_path", "")
        self._music_proc = _start_bg_music(bg_path)
        if self._music_proc:
            name = os.path.splitext(os.path.basename(bg_path))[0].upper() if bg_path else ""
            self._current_song = name or "VICE CITY"
        # Apply mute if the user pressed M during the 2s boot delay.
        # Use SIGKILL (not SIGSTOP) — CoreAudio drains its buffer after SIGSTOP on macOS.
        if self._music_muted and self._music_proc:
            try:
                pgid = os.getpgid(self._music_proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
            self._music_proc = None

    def _change_bg_music(self, path: str, msg_widget=None) -> None:
        """Validate path, save to config, restart music. Callable from any screen."""
        base = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(path):
            candidate = os.path.join(base, "assets", path)
            resolved = candidate if os.path.exists(candidate) else os.path.join(base, path)
        else:
            resolved = path
        if not os.path.exists(resolved):
            if msg_widget:
                msg_widget.update(Text(f"Not found: {path}", style="bold #c03040"))
            return
        from config import load_config as _lc, save_config as _sc
        cfg = _lc()
        cfg["bg_music"] = resolved
        _sc(cfg)
        self._bg_music_path = resolved
        if not self._music_muted:
            proc = self._music_proc
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
            self._music_proc = _start_bg_music(resolved)
        name = os.path.splitext(os.path.basename(resolved))[0].upper()
        self._current_song = name
        try:
            self.query_one(FooterControls).set_muted(self._music_muted, self._current_song)
        except Exception:
            pass
        if msg_widget:
            msg_widget.update(Text(f"Bg → {os.path.basename(resolved)}", style="bold #00c040"))

    def action_toggle_mute(self) -> None:
        self._music_muted = not self._music_muted
        if self._music_muted:
            # Kill the process — SIGSTOP doesn't work on macOS because CoreAudio
            # continues draining its buffer after the process is paused.
            proc = self._music_proc
            if proc and proc.poll() is None:
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
            self._music_proc = None
            try:
                os.remove(_MUSIC_PID_FILE)
            except Exception:
                pass
        else:
            self._music_proc = _start_bg_music()
        try:
            self.query_one(FooterControls).set_muted(self._music_muted, self._current_song)
        except Exception:
            pass  # not on dashboard screen

def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # SIGHUP fires when the terminal window is closed (e.g. Ghostty Cmd+W).
    # Python exits immediately on SIGHUP without running finally blocks, so
    # the music process — being in its own session — keeps playing. Kill it.
    def _on_hup(signum, frame):
        _kill_music_from_pidfile()
        raise SystemExit(0)

    signal.signal(signal.SIGHUP, _on_hup)

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
