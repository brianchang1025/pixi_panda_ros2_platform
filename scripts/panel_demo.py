import time
import os
import argparse
from pathlib import Path
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.console import Console

# --- 1. Parser Definition ---

def parse_bool_arg(value):
    """Helper to handle boolean strings."""
    if isinstance(value, bool): return value
    if value.lower() in ('true', '1', 't', 'y', 'yes'): return True
    elif value.lower() in ('false', '0', 'f', 'n', 'no'): return False
    else: raise argparse.ArgumentTypeError('Boolean value expected.')

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Panda Robot Control Dashboard")
    parser.add_argument("--mode", choices=["single", "dual"], default="single")
    parser.add_argument("--camera", type=parse_bool_arg, nargs="?", const=True, default=True)
    parser.add_argument("--gripper", type=parse_bool_arg, nargs="?", const=True, default=True)
    parser.add_argument("--left-ip", default="172.16.0.2")
    parser.add_argument("--left-namespace", default="panda_left")
    parser.add_argument("--right-ip", default="172.16.0.3")
    parser.add_argument("--right-namespace", default="panda_right")
    parser.add_argument("--pixi-env", default="jazzy-realsense")
    return parser

# --- 2. Dashboard Components ---

def make_config_table(args):
    """Creates a table displaying the argparse parameters."""
    table = Table(show_header=False, box=box.SIMPLE, expand=True)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="bold white")

    table.add_row("Mode", args.mode.upper())
    table.add_row("Env", args.pixi_env)
    table.add_row("Cam", "[green]ON[/]" if args.camera else "[red]OFF[/]")
    table.add_row("Grip", "[green]ON[/]" if args.gripper else "[red]OFF[/]")
    
    table.add_section()
    
    table.add_row("L-IP", args.left_ip)
    table.add_row("L-NS", args.left_namespace)
    
    if args.mode == "dual":
        table.add_row("R-IP", args.right_ip)
        table.add_row("R-NS", args.right_namespace)
        
    return table

def get_telemetry_table(iteration):
    """Simulated robot telemetry."""
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Joint")
    table.add_column("Angle", justify="right")
    
    table.add_row("joint_1", f"{0.01 * iteration:.3f}")
    table.add_row("joint_2", "-1.570")
    table.add_row("joint_7", "0.000")
    return table

def build_dashboard(args):
    """Builds layout and populates it with parsed args."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="config", size=35),
        Layout(name="monitor", ratio=1)
    )
    
    # Header & Static Config
    layout["header"].update(Panel("[bold white]FRANKS PLATFORM DASHBOARD[/]", style="on blue", box=box.SQUARE))
    layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Launch Config[/]"))
    layout["footer"].update(Panel("Press [bold red]Ctrl+C[/] to exit and kill sessions", border_style="dim"))
    
    return layout

# --- 3. Main Logic ---

def main():
    # Parse Command Line Arguments
    args = build_parser().parse_args()
    
    # Setup Dashboard with those args
    layout = build_dashboard(args)
    
    try:
        with Live(layout, screen=True, refresh_per_second=10):
            i = 0
            while True:
                # Update the telemetry section dynamically
                layout["monitor"].update(
                    Panel(get_telemetry_table(i), title="[bold]Live Data[/]", border_style="green")
                )
                time.sleep(0.1)
                i += 1
    except KeyboardInterrupt:
        print("\n[bold red]Shutting down...[/]")

if __name__ == "__main__":
    main()