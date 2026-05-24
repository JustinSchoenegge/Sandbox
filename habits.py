import json
import os
from datetime import datetime, timedelta

from rich.console import Console
from rich.console import Group
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

HABITS_FILE = "data/habits.json"

HABITS = ["AI", "Running", "Lifting", "Reading", "Eating Healthy", "Streaming"]


def load_habits():
    if not os.path.exists(HABITS_FILE):
        return {habit: [] for habit in HABITS}
    with open(HABITS_FILE, "r") as f:
        return json.load(f)


def save_habits(data):
    with open(HABITS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def calculate_streak(dates):
    if not dates:
        return 0
    sorted_dates = sorted(dates, reverse=True)
    today = datetime.now().date()
    streak = 0
    current = today
    for date_str in sorted_dates:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if date == current:
            streak += 1
            current -= timedelta(days=1)
        elif date < current:
            break
    return streak


def is_done_today(dates):
    today = datetime.now().strftime("%Y-%m-%d")
    return today in dates


def mark_done(data, habit):
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in data[habit]:
        data[habit].append(today)
        save_habits(data)
        return True
    return False


def build_habits_table(data):
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1), show_edge=False)
    table.add_column("#", style="dim", width=2)
    table.add_column("Habit", style="bold white", width=14)
    table.add_column("Today", justify="center", width=18)
    table.add_column("Streak", justify="center", width=6)

    for i, habit in enumerate(HABITS, 1):
        dates = data.get(habit, [])
        done = is_done_today(dates)
        streak = calculate_streak(dates)

        status = "[bold red]Already done today[/bold red]" if done else "[dim]Not yet[/dim]"
        streak_str = f"[bold yellow]{streak}d[/bold yellow]" if streak > 0 else "[dim]0d[/dim]"

        table.add_row(str(i), habit, status, streak_str)
    return table


def build_history(data):
    today = datetime.now().date()
    start = today.replace(day=1)
    days = [start + timedelta(days=i) for i in range((today - start).days + 1)]

    header = Text(" " * 16, style="dim")
    for day in days:
        header.append(day.strftime("%d"), style="dim")
        header.append(" ")

    lines = [header]
    for habit in HABITS:
        dates = data.get(habit, [])
        date_set = set(dates)
        line = Text(f"{habit:<16}", style="bold white")
        for day in days:
            if day.strftime("%Y-%m-%d") in date_set:
                line.append("█ ", style="bold green")
            else:
                line.append("░ ", style="dim")
        lines.append(line)

    return Text("\n").join(lines)


def show_habits():
    message = ""
    while True:
        console.clear()
        data = load_habits()

        console.print(Panel(
            Group(
                build_habits_table(data),
                Rule(style="cyan dim"),
                Text(f"This Month — {datetime.now().strftime('%B %Y')}", style="dim cyan"),
                build_history(data),
                Rule(style="cyan dim"),
                Text.from_markup(message, justify="center") if message else Text("Enter a number to mark done, or q to go back.", style="dim"),
            ),
            title="[bold cyan]HABITS[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("")

        if choice.lower() == "q":
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(HABITS):
            habit = HABITS[int(choice) - 1]
            already = not mark_done(data, habit)
            if already:
                message = f"[bold red]{habit} has already been completed today![/bold red]"
            else:
                message = f"[bold green]{habit} marked done![/bold green]"
        else:
            message = "[bold red]Invalid choice — enter a number between 1 and 6.[/bold red]"
