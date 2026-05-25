import json
import os
from datetime import datetime

from storage import atomic_save

from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

NOTES_FILE = "data/notes.json"


def load_notes():
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_notes(notes):
    atomic_save(NOTES_FILE, notes)


def build_notes_list(notes):
    if not notes:
        return Text("No notes yet. Press a to add one.", style="dim")

    lines = Text()
    for note in reversed(notes):
        lines.append(f"{note['timestamp']}\n", style="dim cyan")
        lines.append(f"{note['text']}\n\n", style="white")
    return lines


def show_notes():
    message = ""
    while True:
        console.clear()
        notes = load_notes()
        count = len(notes)

        console.print(Panel(
            Group(
                Text(f"{count} note{'s' if count != 1 else ''} captured", style="dim cyan"),
                Rule(style="cyan dim"),
                build_notes_list(notes),
                Rule(style="cyan dim"),
                Text.from_markup(message, justify="center") if message else Text("a to add a note, or q to go back.", style="dim"),
            ),
            title="[bold cyan]NOTES[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]")

        if choice.lower() == "q":
            break
        elif choice.lower() == "a":
            text = Prompt.ask("[cyan]  Note[/cyan]").strip()
            if text:
                tags = [w for w in text.split() if w.startswith("#")]
                notes.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                    "text": text,
                    "tags": tags,
                })
                save_notes(notes)
                message = "[bold green]Note saved.[/bold green]"
            else:
                message = "[bold red]Note cannot be empty.[/bold red]"
        else:
            message = "[bold red]Press a to add a note or q to go back.[/bold red]"
