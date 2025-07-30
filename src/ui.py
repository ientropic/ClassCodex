# src/ui.py
# Contains functions for displaying TUI elements using the 'rich' library.

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

console = Console()

def display_main_menu():
    """Displays the main menu using rich."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=2)
    )

    layout["header"].update(Panel("[center][bold magenta]Academic Recording Organizer[/bold magenta][/center]"))
    layout["main"].update(Panel("""
[bold]Main Menu:[/bold]
1. Process New Recordings
2. View Processed Recordings
3. Manage Courses
4. Add Notes to Class
5. Settings
6. Exit
    """, title="[bold blue]Navigation[/bold blue]", border_style="blue"))
    layout["footer"].update(Panel("Enter your choice: ", style="dim"))


    # Use console.print directly as live.update is for dynamic updates within a loop
    # If this is meant to be part of a live display, it needs to be managed differently.
    # For now, assuming it's a static display before input.
    console.print(layout)

# Placeholder for other UI functions that might be moved later
# e.g., display_progress_bar, display_table, etc.
