"""
tui.py  —  Dark Hour Dashboard (Textual TUI)
Persona 3 × GTA aesthetic.  Replaces app.py as the main entry point.
"""

import os
import signal
import shlex
import subprocess
from datetime import datetime

from rich.text import Text
from rich.console import RenderableType

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, DataTable, Input, Label
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
from portfolio import load_portfolio, calculate_weights
from game import main as play_game
import permissions
from memory import MemoryManager
from watcher import Watcher
from bot import Bot, BotOutput, load_persona

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


def _start_bg_music() -> "subprocess.Popen | None":
    """Loop vicecity.m4a in the background. Returns the process so it can be paused/terminated."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vicecity.m4a")
    if not os.path.exists(path):
        return None
    cmd = f"while true; do afplay {shlex.quote(path)}; done"
    return subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # isolated process group so SIGSTOP/SIGCONT don't hit Python
    )


def _build_footer_markup(quote: str) -> str:
    return f'[italic #5f87af]"{quote}"[/italic #5f87af]'


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
    """Animated header with ASCII logo, city skyline, and live clock."""

    def __init__(self, name: str, is_admin: bool = False) -> None:
        super().__init__()
        self._user_name = name
        self._is_admin = is_admin

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
        t.append("▀█▀ █░█ █▀▀   █▀▄ █▀█ █▀█ █▄▀   █░█ █▀█ █░█ █▀█\n", style="bold white")
        t.append("░█░ █▀█ ██▄   █▄▀ █▀█ █▀▄ █░█   █▀█ █▄█ █▄█ █▀▄\n", style="bold white")
        t.append("──────────────── ◐ ────────────────\n", style="dim #4a9eff")
        t.append(f"{get_greeting()}, {self._user_name}", style="bold #e8a020")
        if self._is_admin:
            t.append("  [ADMIN]", style="bold #ff2244")
        t.append(f"  ·  {self._date}  {self._clock}", style="dim #5f87af")
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
            bar = "█" * filled + "░" * (12 - filled)
            best = max(
                (calculate_streak(logs.get(h, [])) for h in habits), default=0
            )
            stat_style = "bold #e8a020" if done > 0 else "bold dim white"
            t = Text(justify="center")
            t.append(f"{done}/{total}\n", style=stat_style)
            t.append("HABITS TODAY\n", style="dim #4a5568")
            t.append(bar + "\n", style="dim #2a3a5a")
            t.append(f"{best}d STREAK", style="dim #5f87af")
            self.update(t)
        except Exception:
            self.update(Text("Habits unavailable", style="dim"))


class TasksWidget(Static):
    """HUD card: tasks remaining."""

    def on_mount(self) -> None:
        self.refresh_data()

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            tasks = load_tasks()
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
            self.update(t)
        except Exception:
            self.update(Text("Tasks unavailable", style="dim"))


class NotesWidget(Static):
    """HUD card: note count + last note preview."""

    def on_mount(self) -> None:
        self.refresh_data()

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

    def on_show(self) -> None:
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        import asyncio
        try:
            portfolio = await asyncio.to_thread(load_portfolio)
            holdings = portfolio.get("holdings", [])
            rows = await asyncio.to_thread(calculate_weights, holdings) if holdings else []
            t = Text(justify="center")
            if rows:
                total = sum(r["value"] for r in rows)
                t.append(f"${total:,.0f}\n", style="bold #00c040")
                t.append("PORTFOLIO\n", style="dim #4a5568")
                for r in rows[:2]:
                    w = r["weight"]
                    filled = round(w * 8)
                    bar = "█" * filled + "░" * (8 - filled)
                    t.append(f"{r['ticker']}  {bar}\n", style="dim #5f87af")
            else:
                t.append("—\n", style="dim")
                t.append("NO POSITIONS", style="dim #4a5568")
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
    """HUD footer bar showing music state and key hints."""

    def on_mount(self) -> None:
        self.set_muted(False)

    def set_muted(self, muted: bool) -> None:
        t = Text(justify="center")
        if muted:
            t.append("✕ MUTED", style="dim white")
        else:
            t.append("♪", style="bold #e8a020")
        t.append("  M:MUTE  ·  1-7:NAV  ·  Q:QUIT", style="white")
        self.update(t)


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
            with Vertical(id="main"):
                with Horizontal(id="upper"):
                    yield HabitsWidget(id="habits-widget")
                    yield TasksWidget(id="tasks-widget")
                with Horizontal(id="lower"):
                    yield NotesWidget(id="notes-widget")
                    yield PortfolioWidget(id="portfolio-widget")
                yield BotWidget(id="bot-widget")
        yield Static(_build_footer_markup(get_quote()), id="footer")
        yield FooterControls(id="footer-controls")

    def on_show(self) -> None:
        try:
            self.query_one("#footer", Static).update(
                _build_footer_markup(get_quote())
            )
        except Exception:
            pass
        try:
            muted = getattr(self.app, "_music_muted", False)
            self.query_one(FooterControls).set_muted(muted)
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
        yield DataTable(id="habits-table", cursor_type="row", show_cursor=False)
        yield Input(placeholder="New habit name…", id="habit-input", classes="hidden")
        yield Static("", id="habits-msg", classes="sub-msg")
        yield Static(
            "[dim #2a3a5a]number = mark done   a = add   r = remove   q = back[/dim #2a3a5a]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._mode = None
        self._populate_table()
        self.query_one("#habits-table", DataTable).can_focus = False

    def _populate_table(self) -> None:
        table = self.query_one("#habits-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Habit", "Today", "Streak")
        try:
            data = load_habits()
            for i, habit in enumerate(data["habits"], 1):
                dates = data["logs"].get(habit, [])
                done = is_done_today(dates)
                streak = calculate_streak(dates)
                today_cell = Text("✓", style="bold #00c040") if done else Text("—", style="dim")
                streak_cell = Text(f"{streak}d", style="#e8a020" if streak > 0 else "dim")
                table.add_row(str(i), habit, today_cell, streak_cell)
        except Exception as e:
            self.query_one("#habits-msg", Static).update(
                Text(f"Error loading habits: {e}", style="bold #c03040")
            )

    def on_key(self, event: events.Key) -> None:
        if self._mode is not None:
            return
        if event.character and event.character.isdigit():
            event.stop()
            idx = int(event.character) - 1
            try:
                data = load_habits()
                habits = data["habits"]
                if 0 <= idx < len(habits):
                    habit = habits[idx]
                    success = mark_done(data, habit)
                    msg = self.query_one("#habits-msg", Static)
                    if success:
                        msg.update(Text(f"{habit} marked done!", style="bold #00c040"))
                        notify(f"✓ Habit: {habit}")
                    else:
                        msg.update(Text(f"{habit} already done today.", style="bold #c03040"))
                    self._populate_table()
            except Exception:
                pass

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
            "[dim #2a3a5a]number = complete   a = add   q = back[/dim #2a3a5a]",
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
                        notify(f"✓ Task: {task_name}")
                    self._populate_table()
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
            "[dim #2a3a5a]a = add note   q = back[/dim #2a3a5a]",
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
            "[dim #2a3a5a]number = view detail   a = add   q = back[/dim #2a3a5a]",
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
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold white]═══  PORTFOLIO  ═══[/bold white]", classes="sub-title")
        yield DataTable(id="port-table", cursor_type="row", show_cursor=False)
        yield Static("", id="port-summary", classes="sub-msg")
        yield Static(
            "[dim #2a3a5a]q = back[/dim #2a3a5a]",
            classes="sub-hint",
        )

    def on_mount(self) -> None:
        self._populate_table()

    def on_show(self) -> None:
        self._populate_table()

    def _populate_table(self) -> None:
        table = self.query_one("#port-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Ticker", "Allocation", "Weight", "Tier")
        summary = self.query_one("#port-summary", Static)
        try:
            portfolio = load_portfolio()
            rows = calculate_weights(portfolio["holdings"]) if portfolio["holdings"] else []
            if not rows:
                summary.update(Text("No positions yet.", style="dim"))
                return
            total = sum(r["value"] for r in rows)
            for i, r in enumerate(rows, 1):
                w = r["weight"]
                filled = round(w * 16)
                bar = "█" * filled + "░" * (16 - filled)
                weight_str = f"{w * 100:.1f}%"
                tier = r.get("tier", "?")
                table.add_row(
                    str(i),
                    Text(r["ticker"], style="bold white"),
                    Text(bar, style="#4682b4"),
                    Text(weight_str, style="#5f87af"),
                    Text(tier, style="bold white"),
                )
            summary.update(
                Text(
                    f"${total:,.2f} total  ·  {len(rows)} position(s)",
                    style="dim #5f87af",
                )
            )
        except Exception:
            summary.update(Text("Portfolio unavailable.", style="dim"))


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
# Bots screen
# ══════════════════════════════════════════════════════════════════════════════

class BotsScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("o", "generate_observation", "Observe"),
        ("m", "generate_music", "Music"),
        ("a", "generate_art", "Art"),
        ("y", "approve", "Approve"),
        ("n", "reject", "Reject"),
        ("plus", "trust_up", "Trust +"),
        ("minus", "trust_down", "Trust -"),
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
        yield Static("", id="watcher-bar")
        yield Static(
            "[dim #2a3a5a]"
            "[o] observe  [m] music  [a] art  "
            "[y] approve  [n] reject  "
            "[+/-] trust  [q] back"
            "[/dim #2a3a5a]",
            id="bots-keyhint",
        )

    def on_mount(self) -> None:
        mem = getattr(self.app, "_memory", None)
        self._history: list[dict] = [
            {"time": j["time"], "type": j["type"], "verdict": j["verdict"]}
            for j in (mem.session_judgments if mem else [])
        ]
        self._generating = False
        self._refresh_title()
        self._refresh_pending_display()
        self._refresh_watcher()
        self._refresh_history()
        self.set_interval(5, self._refresh_watcher)

    def on_show(self) -> None:
        self._refresh_title()
        self._refresh_watcher()
        self._refresh_history()

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

        if bot is None or bot.pending is None:
            header_w.update(Text("— awaiting output —", style="dim #2a3a5a"))
            content_w.update(Text(""))
            hint_w.update(Text(""))
            return

        pending = bot.pending
        type_colors = {
            "observation": "#5f87af",
            "music_spec":  "#e8a020",
            "ascii_art":   "#4a9eff",
            "commentary":  "#5f87af",
        }
        color = type_colors.get(pending.output_type, "#5f87af")
        header_w.update(Text(f"[{pending.output_type.upper()}]  {pending.timestamp}", style=f"bold {color}"))
        content_w.update(Text(pending.content, style="white"))
        hint_w.update(Text("[y] approve    [n] reject", style="dim #e8a020"))

    def _refresh_history(self) -> None:
        try:
            content_w = self.query_one("#history-content", Static)
        except Exception:
            return
        if not self._history:
            content_w.update(Text("No output yet this session.", style="dim #2a3a5a"))
            return
        _symbols = {"approved": "✓", "rejected": "✗", "blocked": "✕", "error": "!"}
        _colors  = {"approved": "#00c040", "rejected": "#c03040", "blocked": "#e8a020", "error": "#c03040"}
        t = Text()
        for item in reversed(self._history[-30:]):
            verdict = item.get("verdict", "?")
            t.append(f"{item.get('time', '--:--')}  ", style="dim #2a3a5a")
            t.append(f"[{item.get('type', '?')[:3]}]  ", style="dim #5f87af")
            t.append(
                f"{_symbols.get(verdict, '?')}\n",
                style=f"bold {_colors.get(verdict, '#5f87af')}",
            )
        content_w.update(t)

    def _build_context(self) -> dict:
        ctx: dict = {}
        try:
            data = load_habits()
            habits = data["habits"]
            logs = data["logs"]
            ctx["habits_done"]  = sum(1 for h in habits if is_done_today(logs.get(h, [])))
            ctx["habits_total"] = len(habits)
        except Exception:
            pass
        try:
            ctx["tasks_remaining"] = sum(1 for t in load_tasks() if not t["done"])
        except Exception:
            pass
        try:
            ctx["notes_count"] = len(load_notes())
        except Exception:
            pass
        return ctx

    @work(exclusive=True)
    async def _generate(self, gen_type: str) -> None:
        import asyncio
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None:
            return
        self._generating = True
        self._refresh_pending_display()

        if gen_type == "observation":
            output = await asyncio.to_thread(bot.generate_observation, self._build_context())
        elif gen_type == "music_spec":
            output = await asyncio.to_thread(bot.generate_music_spec)
        elif gen_type == "ascii_art":
            output = await asyncio.to_thread(bot.generate_ascii_art)
        else:
            self._generating = False
            return

        self._generating = False

        if output.output_type == "blocked":
            self._history.append({"time": output.timestamp, "type": "blocked", "verdict": "blocked"})
            self._refresh_history()
        elif bot.pending is None:
            self._history.append({"time": output.timestamp, "type": "error", "verdict": "error"})
            self._refresh_history()

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
        if not self._guard_pending():
            self._generate("observation")

    def action_generate_music(self) -> None:
        if not self._guard_pending():
            self._generate("music_spec")

    def action_generate_art(self) -> None:
        if not self._guard_pending():
            self._generate("ascii_art")

    def action_approve(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None or bot.pending is None:
            return
        output = bot.record_verdict("approved")
        if output:
            self._history.append({"time": output.timestamp, "type": output.output_type, "verdict": "approved"})
        self._refresh_pending_display()
        self._refresh_history()
        self._update_bot_widget()

    def action_reject(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None or bot.pending is None:
            return
        output = bot.record_verdict("rejected")
        if output:
            self._history.append({"time": output.timestamp, "type": output.output_type, "verdict": "rejected"})
        self._refresh_pending_display()
        self._refresh_history()

    def action_trust_up(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None:
            return
        new_level = bot.adjust_trust(+1)
        self._refresh_title()
        watcher: Watcher | None = getattr(self.app, "_watcher", None)
        if watcher:
            watcher.flag(f"Trust raised to {new_level} ({permissions.level_name(new_level)})", "info")
        self._refresh_watcher()
        self._update_bot_widget()

    def action_trust_down(self) -> None:
        bot: Bot | None = getattr(self.app, "_bot", None)
        if bot is None:
            return
        new_level = bot.adjust_trust(-1)
        self._refresh_title()
        watcher: Watcher | None = getattr(self.app, "_watcher", None)
        if watcher:
            watcher.flag(f"Trust reduced to {new_level} ({permissions.level_name(new_level)})", "warning")
        self._refresh_watcher()
        self._update_bot_widget()

    def _update_bot_widget(self) -> None:
        try:
            self.app.query_one("#bot-widget", BotWidget).refresh_data()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════

class DarkHourApp(App):
    CSS_PATH = "tui.tcss"

    def on_mount(self) -> None:
        self._music_proc = None
        self._music_muted = False
        _boot_sound()
        self.set_timer(0.8, self._start_music)
        config = load_config()
        self.is_admin = config["is_admin"]
        self._memory = MemoryManager()
        self._watcher = Watcher()
        self._bot = Bot(load_persona(), self._memory, self._watcher)
        self.push_screen(DashboardScreen(config["name"], self.is_admin))

    def _start_music(self) -> None:
        self._music_proc = _start_bg_music()
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
            self.query_one(FooterControls).set_muted(self._music_muted)
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
        memory = getattr(app, "_memory", None)
        if memory:
            try:
                memory.close_session()
            except Exception:
                pass
    print("\n\033[2m\033[38;5;67mUntil the next Dark Hour.\033[0m\n")


if __name__ == "__main__":
    main()
