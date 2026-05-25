"""
tui.py  —  Dark Hour Dashboard (Textual TUI)
Persona 3 aesthetic.  Replaces app.py as the main entry point.
"""

import os
import shlex
import subprocess
from datetime import datetime

from rich.text import Text
from rich.console import RenderableType

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, DataTable, Input
from textual.containers import Horizontal, Vertical, ScrollableContainer
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

load_env()

# ── boot sound ─────────────────────────────────────────────────────────────────

def _boot_sound() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "boot.m4a")
    if os.path.exists(path):
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _start_bg_music() -> "subprocess.Popen | None":
    """Loop vicecity.m4a in the background. Returns the shell process so it can be terminated."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vicecity.m4a")
    if not os.path.exists(path):
        return None
    cmd = f"while true; do afplay {shlex.quote(path)}; done"
    return subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard widgets
# ══════════════════════════════════════════════════════════════════════════════

class DashboardHeader(Static):
    """Animated header with ASCII logo, greeting and live clock."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._user_name = name

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
        t.append("░█░ █▀█ ██▄   █▄▀ █▀█ █▀▄ █░█   █▀█ █▀▄ █▄█ █▀▄\n", style="bold white")
        t.append("      · · · ☽ · · ·\n", style="dim #5f87af")
        t.append(f"{get_greeting()}, {self._user_name}", style="bold white")
        t.append(f"  ·  {self._date}  {self._clock}", style="dim #5f87af")
        return t


class NavSidebar(Static):
    """Left-hand navigation sidebar."""

    def render(self) -> RenderableType:
        t = Text()
        for key, label in [
            ("[1]", "Habits"),
            ("[2]", "Tasks"),
            ("[3]", "Notes"),
            ("[4]", "Game"),
            ("[5]", "Portfolio"),
            ("[6]", "Music"),
        ]:
            t.append(key + " ", style="dim #5f87af")
            t.append(label + "\n", style="bold white")
        t.append("──────────────────\n", style="dim #2a3a5a")
        t.append("[q] ", style="dim #5f87af")
        t.append("Quit", style="bold white")
        return t


class HabitsWidget(Static):
    """Summary panel: habits done today + best streak."""

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
            t = Text()
            t.append(f"{done} / {total} today\n", style="bold white")
            t.append(bar + "\n", style="#5f87af")
            t.append(f"Best streak  {best}d", style="dim #5f87af")
            self.update(t)
        except Exception:
            self.update(Text("Habits unavailable", style="dim"))


class TasksWidget(Static):
    """Summary panel: tasks remaining."""

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
            t = Text()
            if remaining == 0:
                t.append("All tasks complete ✓", style="bold #00c040")
            else:
                t.append(f"{remaining} remaining\n", style="bold white")
                t.append(f"{done_count} of {total} complete", style="dim #5f87af")
            self.update(t)
        except Exception:
            self.update(Text("Tasks unavailable", style="dim"))


class NotesWidget(Static):
    """Summary panel: note count + last note preview."""

    def on_mount(self) -> None:
        self.refresh_data()

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            notes = load_notes()
            count = len(notes)
            t = Text()
            t.append(f"{count} note{'s' if count != 1 else ''}\n", style="bold white")
            if notes:
                last_text = notes[-1]["text"]
                preview = (last_text[:40] + "…") if len(last_text) > 40 else last_text
                t.append(preview, style="italic dim #008b8b")
            else:
                t.append("No notes yet", style="dim")
            self.update(t)
        except Exception:
            self.update(Text("Notes unavailable", style="dim"))


class PortfolioWidget(Static):
    """Summary panel: total value + top 2 holdings."""

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
            t = Text()
            if rows:
                total = sum(r["value"] for r in rows)
                t.append(f"${total:,.0f} total\n", style="bold white")
                for r in rows[:2]:
                    w = r["weight"]
                    filled = round(w * 8)
                    bar = "█" * filled + "░" * (8 - filled)
                    t.append(f"{r['ticker']}  {bar}  {w * 100:.0f}%\n", style="#5f87af")
            else:
                t.append("No positions", style="dim")
            self.update(t)
        except Exception:
            self.update(Text("Portfolio unavailable", style="dim"))


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard screen
# ══════════════════════════════════════════════════════════════════════════════

class DashboardScreen(Screen):
    BINDINGS = [
        ("1", "push_habits", "Habits"),
        ("2", "push_tasks", "Tasks"),
        ("3", "push_notes", "Notes"),
        ("4", "push_game", "Game"),
        ("5", "push_portfolio", "Portfolio"),
        ("6", "push_music", "Music"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        yield DashboardHeader(self._name)
        with Horizontal(id="body"):
            yield NavSidebar(id="sidebar")
            with Vertical(id="main"):
                with Horizontal(id="upper"):
                    yield HabitsWidget(id="habits-widget")
                    yield TasksWidget(id="tasks-widget")
                with Horizontal(id="lower"):
                    yield NotesWidget(id="notes-widget")
                    yield PortfolioWidget(id="portfolio-widget")
        yield Static(
            f'[italic #5f87af]"{get_quote()}"[/italic #5f87af]',
            id="footer",
        )

    def on_show(self) -> None:
        try:
            self.query_one("#footer", Static).update(
                f'[italic #5f87af]"{get_quote()}"[/italic #5f87af]'
            )
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

    def action_push_habits(self) -> None:
        self.app.push_screen(HabitsScreen())

    def action_push_tasks(self) -> None:
        self.app.push_screen(TasksScreen())

    def action_push_notes(self) -> None:
        self.app.push_screen(NotesScreen())

    def action_push_game(self) -> None:
        self.app.push_screen(GameScreen(self._name))

    def action_push_portfolio(self) -> None:
        self.app.push_screen(PortfolioScreen())

    def action_push_music(self) -> None:
        self.app.push_screen(MusicScreen())


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
                streak_cell = Text(f"{streak}d", style="#c0a000" if streak > 0 else "dim")
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
# App
# ══════════════════════════════════════════════════════════════════════════════

class DarkHourApp(App):
    CSS_PATH = "tui.tcss"

    def on_mount(self) -> None:
        self._music_proc = None
        _boot_sound()
        self.set_timer(2.0, self._start_music)
        config = load_config()
        self.push_screen(DashboardScreen(config["name"]))

    def _start_music(self) -> None:
        self._music_proc = _start_bg_music()


def main() -> None:
    app = DarkHourApp()
    try:
        app.run()
    finally:
        if getattr(app, "_music_proc", None):
            app._music_proc.terminate()
    print("\n\033[2m\033[38;5;67mUntil the next Dark Hour.\033[0m\n")


if __name__ == "__main__":
    main()
