import json
import os
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
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


def render_habits(data):
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Habit", style="bold white", width=18)
    table.add_column("Today", justify="center", width=8)
    table.add_column("Streak", justify="center", width=8)

    for i, habit in enumerate(HABITS, 1):
        dates = data.get(habit, [])
        done = is_done_today(dates)
        streak = calculate_streak(dates)

        status = "[bold green]Done[/bold green]" if done else "[dim]Not yet[/dim]"
        streak_str = f"[bold yellow]{streak}d[/bold yellow]" if streak > 0 else "[dim]0d[/dim]"

        table.add_row(str(i), habit, status, streak_str)

    console.print(Panel(table, title="[bold cyan]Habits[/bold cyan]", box=box.ROUNDED, style="cyan"))


def show_habits():
    while True:
        console.clear()
        data = load_habits()
        render_habits(data)
        console.print("[dim]Enter a number to mark done, or [bold]q[/bold] to go back.[/dim]\n")

        choice = Prompt.ask("Choice")

        if choice.lower() == "q":
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(HABITS):
            habit = HABITS[int(choice) - 1]
            already = not mark_done(data, habit)
            if already:
                console.print(f"[yellow]{habit} already marked done today.[/yellow]")
            else:
                console.print(f"[green]{habit} marked done![/green]")
        else:
            console.print("[red]Invalid choice.[/red]")
