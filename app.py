from rich.console import Console
from rich.prompt import Prompt
from rich import box
from rich.panel import Panel

from dashboard import show_dashboard
from game import main as play_game

console = Console()


def main():
    show_dashboard()

    console.print(Panel(
        "[1] Habits\n[2] Tasks\n[3] Notes\n[4] Play Number Guesser\n[q] Quit",
        title="[bold cyan]Menu[/bold cyan]",
        box=box.ROUNDED,
        style="cyan",
    ))

    choice = Prompt.ask("\nWhat would you like to do", choices=["1", "2", "3", "4", "q"])

    if choice == "4":
        play_game()
    elif choice == "q":
        console.print("\n[dim]See you tomorrow.[/dim]\n")
    else:
        console.print("\n[yellow]Coming soon — building this next![/yellow]\n")


main()
