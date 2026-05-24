from rich.console import Console
from rich.prompt import Prompt
from rich import box
from rich.panel import Panel

from dashboard import show_dashboard
from habits import show_habits
from tasks import show_tasks
from game import main as play_game

console = Console()


def main():
    while True:
        show_dashboard()

        console.print(Panel(
            "[dim]\[1][/dim] Habits  [dim]\[2][/dim] Tasks  [dim]\[3][/dim] Notes  [dim]\[4][/dim] Game  [dim]\[q][/dim] Quit",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]", choices=["1", "2", "3", "4", "q"])

        if choice == "1":
            show_habits()
        elif choice == "2":
            show_tasks()
        elif choice == "4":
            play_game()
        elif choice == "q":
            console.print("\n[dim]See you tomorrow.[/dim]\n")
            break
        else:
            console.print("\n[yellow]Coming soon — building this next![/yellow]\n")


main()
