from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Static, DataTable, Input
from textual import events
from rich.text import Text

from habits import load_habits, is_done_today, calculate_streak, mark_done, save_habits
from context import invalidate_context_cache


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
            "[bold #e8a020][[enter]][/bold #e8a020][white] mark done  [/white]"
            "[bold #e8a020][1-9][/bold #e8a020][white] quick mark  [/white]"
            "[bold #e8a020][[a]][/bold #e8a020][white] add  [/white]"
            "[bold #e8a020][[r]][/bold #e8a020][white] remove  [/white]"
            "[bold #e8a020][[q]][/bold #e8a020][white] back[/white]",
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
                if success:
                    invalidate_context_cache()
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
        if event.character and event.character.isdigit() and event.character != "0":
            event.stop()
            shortcut_idx = int(event.character) - 1
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
                    invalidate_context_cache()
                    msg.update(Text(f"{value} added.", style="bold #00c040"))
            elif self._mode == "remove":
                if value.isdigit():
                    idx = int(value) - 1
                    if 0 <= idx < len(habits):
                        removed = habits.pop(idx)
                        save_habits(data)
                        invalidate_context_cache()
                        msg.update(Text(f"{removed} removed.", style="bold #00c040"))
                    else:
                        msg.update(Text("Invalid habit number.", style="bold #c03040"))
                else:
                    msg.update(Text("Enter a habit number.", style="bold #c03040"))
        except Exception:
            msg.update(Text("Error updating habits.", style="bold #c03040"))
        self.action_cancel_input()
        self._populate_table()
