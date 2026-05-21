import logging
from rich import print as rich_print
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.prompt import Prompt

LOGGER = logging.getLogger(__name__)


def configuration_panel(args) -> None:
    """Prints a clean, non-blocking configuration panel using Rich in the normal terminal,

    dynamically listing all parsed command-line arguments.
    """
    
    # Build an internal layout table for the panel
    table = Table(show_header=False, box=box.SIMPLE, expand=False)
    table.add_column("Parameter", style="cyan", width=22)
    table.add_column("Value", style="bold white")

    # Use a loop to grab all arguments dynamically, matching log_arguments logic
    for arg, value in vars(args).items():
        # Clean up the argument name string for display (e.g., "left_ip" -> "Left Ip")
        display_name = arg.replace("_", " ").title()
        
        # Colorize and format the values beautifully depending on their type
        if isinstance(value, bool):
            value_str = "[green]ENABLED[/]" if value else "[red]DISABLED[/]"
        elif value is None:
            value_str = "[yellow]NOT SET[/]"
        elif arg.endswith("_ip"):
            value_str = f"[bold white]{value}[/]"
        elif arg.endswith("_namespace"):
            value_str = f"[cyan]/{value}[/]"
        else:
            value_str = str(value)

        table.add_row(display_name, value_str)

    # Print the unified static panel directly to the standard terminal scroll line
    rich_print("\n")
    rich_print(
        Panel(
            table, 
            title="[bold white]FRANKA PLATFORM CONFIGURATION SUMMARY[/]", 
            border_style="blue", 
            expand=False
        )
    )
    rich_print("\n")
    

def safety_check_panel() -> None:
    """Displays a high-visibility safety check panel and blocks until Enter is pressed."""
    # Create bold, styled text content for the safety message
    safety_text = Text()
    safety_text.append("IMPORTANT SAFETY CHECK BEFORE LAUNCHING ROBOT TERMINALS:\n\n", style="bold yellow")
    safety_text.append(" 🚨  EMERGENCY STOP ", style="bold white")
    safety_text.append("MUST", style="bold red underline")
    safety_text.append(" be open.\n", style="bold white")
    
    safety_text.append(" 🔵  Robot status light ", style="bold white")
    safety_text.append("MUST", style="bold red underline")
    safety_text.append(" show Blue.\n\n", style="bold white")
    
    safety_text.append("Press ", style="dim white")
    safety_text.append("[ENTER]", style="bold green")
    safety_text.append(" only after both conditions are manually verified.", style="dim white")

    # Render a thick red panel to explicitly denote a critical safety gate
    rich_print("\n")
    rich_print(
        Panel(
            safety_text, 
            border_style="red", 
            title="[bold red]⚠️ SAFETY VERIFICATION REQUIRED[/]", 
            expand=False
        )
    )
    rich_print("\n")

    # Halt execution completely until they hit Enter
    input()
    


def control_panel(args, hardware_status_list: list = None):
    """Generates the side-by-side dashboard layout object.
    
    Returns a Rich Panel instead of printing it directly.
    """

    # --- [LEFT COMPONENT: Configuration Table] ---
    config_table = Table(show_header=False, box=box.SIMPLE, expand=False)
    config_table.add_column("Parameter", style="cyan", width=22)
    config_table.add_column("Value", style="bold white")

    for arg, value in vars(args).items():
        display_name = arg.replace("_", " ").title()
        if isinstance(value, bool):
            value_str = "[green]ENABLED[/]" if value else "[red]DISABLED[/]"
        elif value is None:
            value_str = "[yellow]NOT SET[/]"
        elif arg.endswith("_ip"):
            value_str = f"[bold white]{value}[/]"
        elif arg.endswith("_namespace"):
            value_str = f"[cyan]/{value}[/]"
        else:
            value_str = str(value)
        config_table.add_row(display_name, value_str)

    left_panel = Panel(config_table, title="[bold cyan]📋 Configuration Summary[/]", border_style="cyan", expand=True)

    # --- [RIGHT COMPONENT 1: Keyboard Controls] ---
    mode = getattr(args, "mode", "dual")
    controls_table = Table(show_header=False, box=box.SIMPLE, expand=False)
    controls_table.add_column("Key", style="bold yellow", width=8, justify="center")
    controls_table.add_column("Action", style="white")
    controls_table.add_row("[ Q ]", "Quit launcher ")
    controls_table.add_row("[ V ]", "Open Visualizer")
    
    if mode == "single":
        controls_table.add_row("[ L ]", "Reboot robot arm")
    else:
        controls_table.add_row("[ L ]", "Reboot [bold]left[/] arm")
        controls_table.add_row("[ R ]", "Reboot [bold]right[/] arm")

    right_controls_panel = Panel(controls_table, title="[bold yellow]🕹️ Keyboard Controls[/]", border_style="yellow", expand=True)

    # --- [RIGHT COMPONENT 2: Hardware Status] ---
    status_table = Table(show_header=False, box=box.SIMPLE, expand=False)
    status_table.add_column("Component", style="magenta", width=16)
    status_table.add_column("Status", width=14)

    if hardware_status_list:
        iterable = hardware_status_list.items() if isinstance(hardware_status_list, dict) else hardware_status_list
        for component, status in iterable:
            status_upper = str(status).upper().strip()
            if status_upper in ["CONNECTED", "ACTIVE", "RUNNING", "OK", "TRUE"]:
                status_str = f"[green]● {status_upper}[/]"
            elif status_upper in ["DISCONNECTED", "OFFLINE", "ERROR", "STALE", "FALSE", "FAULT", "INACTIVE", "COLLISION", "EMERGENCY STOP"]:
                status_str = f"[red]✖ {status_upper}[/]"
            elif status_upper in ["INITIALIZING", "WARN", "BOOTING"]:
                status_str = f"[yellow]▲ {status_upper}[/]"
            else:
                status_str = f"[white]{status_upper}[/]"
            status_table.add_row(component, status_str)
    else:
        status_table.add_row("[dim]Hardware Profiles[/]", "[dim]Awaiting Topics...[/]")

    right_status_panel = Panel(status_table, title="[bold magenta]⚙️ Hardware Status[/]", border_style="magenta", expand=True)

    # --- [CONSOLIDATION & ALIGNMENT] ---
    right_column_grid = Table.grid(padding=(0, 0))
    right_column_grid.add_row(right_controls_panel)
    right_column_grid.add_row(right_status_panel)

    master_dashboard_layout = Table.grid(padding=2)
    master_dashboard_layout.add_row(left_panel, right_column_grid)

    # Return the master layout panel instead of printing it
    return Panel(master_dashboard_layout, title="[bold white]FRANKA PLATFORM OPERATIONAL DASHBOARD[/]", border_style="blue", expand=False)
    

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