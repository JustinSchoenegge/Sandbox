import json
import os
from datetime import datetime

from storage import atomic_save

from rich.console import Console
from rich.console import Group
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

TASKS_FILE = "data/tasks.json"

TEMPLATES = ["Vacuum", "Clean Sink", "Clean Litter Box", "Review Stocks"]


def load_tasks():
    today = datetime.now().strftime("%Y-%m-%d")

    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == today:
                return data["tasks"]
        except json.JSONDecodeError:
            pass

    tasks = [{"name": t, "done": False} for t in TEMPLATES]
    save_tasks(tasks)
    return tasks


def save_tasks(tasks):
    today = datetime.now().strftime("%Y-%m-%d")
    atomic_save(TASKS_FILE, {"date": today, "tasks": tasks})


def build_tasks_table(tasks):
    pending = [(i, t) for i, t in enumerate(tasks) if not t["done"]]
    done = [(i, t) for i, t in enumerate(tasks) if t["done"]]

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), show_edge=False)
    table.add_column("#", style="dim", width=2)
    table.add_column("Task", width=30)

    for i, task in pending:
        table.add_row(str(i + 1), f"[bold white]{task['name']}[/bold white]")

    for i, task in done:
        table.add_row(str(i + 1), f"[dim strike]{task['name']}[/dim strike]")

    return table


def show_tasks():
    message = ""
    while True:
        console.clear()
        tasks = load_tasks()

        pending_count = sum(1 for t in tasks if not t["done"])
        total = len(tasks)
        summary = Text(f"{pending_count} of {total} remaining", style="dim cyan")

        console.print(Panel(
            Group(
                summary,
                Rule(style="cyan dim"),
                build_tasks_table(tasks),
                Rule(style="cyan dim"),
                Text.from_markup(message, justify="center") if message else Text("Enter a number to complete, a to add, or q to go back.", style="dim"),
            ),
            title="[bold cyan]TASKS[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]")

        if choice.lower() == "q":
            break
        elif choice.lower() == "a":
            name = Prompt.ask("New task").strip()
            if name:
                tasks.append({"name": name, "done": False})
                save_tasks(tasks)
                message = f"[bold green]'{name}' added.[/bold green]"
            else:
                message = "[bold red]Task name cannot be empty.[/bold red]"
        elif choice.isdigit() and 1 <= int(choice) <= len(tasks):
            idx = int(choice) - 1
            if tasks[idx]["done"]:
                message = f"[bold red]{tasks[idx]['name']} is already done.[/bold red]"
            else:
                tasks[idx]["done"] = True
                save_tasks(tasks)
                message = f"[bold green]{tasks[idx]['name']} completed.[/bold green]"
        else:
            message = "[bold red]Invalid choice.[/bold red]"
