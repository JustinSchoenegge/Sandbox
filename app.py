from rich.console import Console
from rich.prompt import Prompt
from rich import box
from rich.panel import Panel

from config import load_config
from dashboard import show_dashboard
from habits import show_habits
from tasks import show_tasks
from notes import show_notes
from portfolio import show_portfolio
from game import main as play_game

console = Console()


def main():
    config = load_config()
    name = config["name"]

    while True:
        show_dashboard(name)

        console.print(Panel(
            "[dim]\[1][/dim] Habits  [dim]\[2][/dim] Tasks  [dim]\[3][/dim] Notes  [dim]\[4][/dim] Game  [dim]\[5][/dim] Portfolio  [dim]\[q][/dim] Quit",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]", choices=["1", "2", "3", "4", "5", "q"])

        if choice == "1":
            show_habits()
        elif choice == "2":
            show_tasks()
        elif choice == "3":
            show_notes()
        elif choice == "4":
            play_game(name)
        elif choice == "5":
            show_portfolio()
        elif choice == "q":
            console.print("\n[dim]See you tomorrow.[/dim]\n")
            break


if __name__ == "__main__":
    main()
