"""Prompt utility for user input in command-line applications."""

import logging

from rich import print as rich_print
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt

LOGGER = logging.getLogger(__name__)


def prompt_bool(message: str, default: bool) -> bool:
    """Prompt user for a yes/no boolean response.
    
    Args:
        message: The prompt message to display
        default: The default value if user presses Enter
        
    Returns:
        bool: True for 'yes', False for 'no'
    """
    default_text = "yes" if default else "no"
    value = prompt(
        message=message,
        options=["yes", "no"],
        default=default_text,
    )
    return value.lower() == "yes"


def prompt(
    message: str = "Choose an option:",
    options: list | None = None,
    default: str | None = None,
) -> str:
    """Prompt the user to choose from a list of options or enter a string using a styled Rich Panel.

    Args:
        message (str): The prompt message to display.
        options (list, optional): A list of string options to choose from.
        default (str, optional): The default value to use if user enters nothing.

    Returns:
        str: The selected or entered string.
    """
    if options:
        # Build the text block to place inside our display Panel
        panel_content = Text()
        panel_content.append(f"{message}\n\n", style="bold white")
        
        # Enumerate options visually as 1. option, 2. option
        for i, option in enumerate(options, 1):
            panel_content.append(f"  [{i}] ", style="cyan bold")
            panel_content.append(f"{option}\n", style="white")
            
        # Draw the clean container Panel on the standard terminal
        rich_print(Panel(panel_content, border_style="cyan", title="[bold cyan]Input Required[/]", expand=False))
        
        # We accept either raw option strings OR their respective index numbers
        valid_choices = options + [str(i) for i in range(1, len(options) + 1)]
        
        while True:
            # Gather input using Rich's built-in validation prompt
            choice = Prompt.ask(
                "[bold yellow]?[/] Enter selection", 
                choices=valid_choices, 
                default=default,
                show_choices=False # Prevents printing a messy choice list in the prompt string
            ).strip()
            
            # If the user typed an index number, map it back to the option string
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    selection = options[idx]
                    LOGGER.info(f"User selected: {selection} (via index {choice})")
                    return selection
            else:
                LOGGER.info(f"User selected: {choice}")
                return choice
    else:
        # Handling standard string inputs without discrete option sequences
        panel_content = Text(message, style="bold white")
        rich_print(Panel(panel_content, border_style="yellow", title="[bold yellow]Input Required[/]", expand=False))
        
        while True:
            response = Prompt.ask("[bold yellow]?[/] Enter string", default=default).strip()
            
            # Replicates your original shortcut: convert a singular '/' into a true empty string
            if response == "/":
                LOGGER.info("User explicitly requested empty string via '/'")
                return ""
                
            if response:
                LOGGER.info(f"User entered text string: {response}")
                return response
            elif default is not None:
                return default
            else:
                rich_print("[bold red]![/] Value cannot be empty and no default is configured. Try again.")
