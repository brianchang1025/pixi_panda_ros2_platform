#!/usr/bin/env python3

import argparse
import logging
import time
import os
import sys
import termios
import tty
import threading
from typing import List

# ---------------------------------------------------------------------------
# 1. Terminal IO Stream Multiplexer (Captures EVERYTHING instantly)
# ---------------------------------------------------------------------------
class TerminalStreamBuffer:
    """Acts like a real terminal stream, intercepting prints, logs, and tracebacks."""
    def __init__(self, max_lines: int = 22):
        self.log_lines: List[str] = []
        self.max_lines = max_lines
        self._lock = threading.Lock()
        self.live_instance = None  # Hook to trigger immediate display refreshes

        # Keep tracks of originals to allow cleanup on shutdown
        self._stdout = sys.stdout
        self._stderr = sys.stderr

    def write(self, text: str):
        # Always mirror to the hidden background standard stream for safety
        self._stdout.write(text)
        
        if not text:
            return

        with self._lock:
            # Handle split lines gracefully if text has internal line breaks
            lines = text.splitlines()
            # If the last line didn't end in a newline, append to it instead of making a new line
            if lines:
                if text.startswith('\n') or not self.log_lines:
                    self.log_lines.extend([l for l in lines if l.strip()])
                else:
                    self.log_lines[-1] += lines[0]
                    self.log_lines.extend([l for l in lines[1:] if l.strip()])

            # Keep buffer size strictly clamped to the viewport panel height
            if len(self.log_lines) > self.max_lines:
                self.log_lines = self.log_lines[-self.max_lines:]

        # CRITICAL: Force the screen to redraw the layout immediately on every write event
        if self.live_instance:
            self.live_instance.refresh()

    def flush(self):
        self._stdout.flush()
        self._stderr.flush()

    def get_text(self) -> str:
        with self._lock:
            return "\n".join(self.log_lines)


# Instantiate the unified terminal stream interceptor
TERMINAL_STREAM = TerminalStreamBuffer()

# Redirect standard outputs instantly at load time
sys.stdout = TERMINAL_STREAM
sys.stderr = TERMINAL_STREAM

# Configure standard logger to write directly to our intercepted stream wrapper
class StreamLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            TERMINAL_STREAM.write(msg + "\n")
        except Exception:
            self.handleError(record)

DASHBOARD_LOG_HANDLER = StreamLogHandler()
DASHBOARD_LOG_HANDLER.setFormatter(
    logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s: %(message)s", 
        datefmt="%X"
    )
)

def initialize_dashboard_logging(log_level_str: str = "INFO"):
    level = getattr(logging, log_level_str.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(DASHBOARD_LOG_HANDLER)
    
    # Cascade configuration aggressively to child module spaces
    for logger_name in ["utils.utils", "utils.franka_desk", "utils.setup_logger", __name__]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = True

initialize_dashboard_logging("INFO")
LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2. Import Interactive Layouts & Local Robot Utilities
# ---------------------------------------------------------------------------
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Prompt

from utils.tmux_manager import TmuxManager
from utils.franka_desk import FrankaLockUnlock
from utils import prompt as prompt_utils
from utils.utils import (
    ArmConfig,
    get_desk_credentials,
    enable_arm_with_desk,
    read_key,
    WORKSPACE_ROOT,
    build_panda_launch_command,
    build_3rd_camera_launch_command,
    build_wrist_camera_launch_command,
    launch_rqt_background
)

# ---------------------------------------------------------------------------
# 3. Argument Parsers & Layout Configuration Panels
# ---------------------------------------------------------------------------
def parse_bool_arg(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean value (true/false).")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare Franka arms and launch franka_platform Dashboard.")
    parser.add_argument("--mode", choices=["single", "dual"], default=None)
    parser.add_argument("--camera", type=parse_bool_arg, nargs="?", const=True, default=True)
    parser.add_argument("--gripper", type=parse_bool_arg, nargs="?", const=True, default=True)
    parser.add_argument("--left-ip", default=None)
    parser.add_argument("--left-namespace", default=None)
    parser.add_argument("--right-ip", default=None)
    parser.add_argument("--right-namespace", default=None)
    parser.add_argument("--pixi-env", choices=["jazzy", "jazzy-realsense"], default="jazzy-realsense")
    parser.add_argument("--protocol", default="https")
    parser.add_argument("--log-level", type=str, default="INFO")
    return parser

def make_config_table(args: argparse.Namespace) -> Table:
    table = Table(show_header=False, box=box.SIMPLE, expand=True)
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="bold white")

    table.add_row("Mode", str(args.mode).upper() if args.mode else "[yellow bold]PENDING...[/]")
    table.add_row("Pixi Env", str(args.pixi_env))
    table.add_row("Camera", "[green]ENABLED[/]" if args.camera else "[red]DISABLED[/]")
    table.add_row("Gripper", "[green]ENABLED[/]" if args.gripper else "[red]DISABLED[/]")
    
    table.add_section()
    
    table.add_row("Left IP", args.left_ip or "[yellow]PENDING...[/]")
    table.add_row("Left Namespace", args.left_namespace or "[yellow]PENDING...[/]")
    
    if args.mode == "dual":
        table.add_row("Right IP", args.right_ip or "[yellow]PENDING...[/]")
        table.add_row("Right Namespace", args.right_namespace or "[yellow]PENDING...[/]")
        
    return table

def build_dashboard_skeleton(args: argparse.Namespace) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="config", size=38),
        Layout(name="logs", ratio=1)
    )
    
    layout["header"].update(Panel("[bold white]FRANK RESILIENT CONTROL INTERFACE[/]", style="white on blue", box=box.SQUARE))
    layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Configuration Status[/]"))
    layout["logs"].update(Panel(TERMINAL_STREAM.get_text(), title="[bold green]System Output Logs[/]"))
    layout["footer"].update(Panel("Awaiting startup definitions parameter sequences...", border_style="dim"))
    return layout

# ---------------------------------------------------------------------------
# 4. Main Runtime Entry Point
# ---------------------------------------------------------------------------
def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    initialize_dashboard_logging(args.log_level)
    LOGGER.info("Dashboard logging stream fully hooked.")

    layout = build_dashboard_skeleton(args)

    # Use auto-refresh as a fallback, but our streams will bypass this and force instant updates
    with Live(layout, screen=True, refresh_per_second=10) as live:
        # Register the live render engine window with our stream engine for instantaneous updates
        TERMINAL_STREAM.live_instance = live
        
        def resolve_interactive_param(prompt_msg: str, choices: List[str] = None, default: str = None) -> str:
            live.stop()
            try:
                if choices:
                    result = Prompt.ask(f"[bold yellow]?[/] {prompt_msg}", choices=choices, default=default)
                else:
                    result = Prompt.ask(f"[bold yellow]?[/] {prompt_msg}", default=default)
            finally:
                live.start()
            return result

        # --- Dynamic Configuration Step Sequence ---
        if args.mode is None:
            args.mode = resolve_interactive_param("Select system operational mode", choices=["single", "dual"], default="single")
            layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Configuration Status[/]"))

        left_arm_label = "arm" if args.mode == "single" else "left arm"

        if args.left_ip is None:
            fallback = os.getenv("FRANKA_IP_LEFT", "192.168.31.10")
            args.left_ip = resolve_interactive_param(f"Enter target IP address for {left_arm_label}", default=fallback)
            layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Configuration Status[/]"))

        if args.left_namespace is None:
            fallback = os.getenv("FRANKA_NAMESPACE_LEFT", "left")
            args.left_namespace = resolve_interactive_param(f"Enter target ROS namespace for {left_arm_label}", default=fallback)
            layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Configuration Status[/]"))

        if args.mode == "dual":
            if args.right_ip is None:
                fallback = os.getenv("FRANKA_IP_RIGHT", "192.168.32.10")
                args.right_ip = resolve_interactive_param("Enter target IP address for right arm", default=fallback)
                layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Configuration Status[/]"))

            if args.right_namespace is None:
                fallback = os.getenv("FRANKA_NAMESPACE_RIGHT", "right")
                args.right_namespace = resolve_interactive_param("Enter target ROS namespace for right arm", default=fallback)
                layout["config"].update(Panel(make_config_table(args), title="[bold cyan]Configuration Status[/]"))

        # Build arm configurations post-input
        arms = [ArmConfig(label="left", robot_ip=args.left_ip, namespace=args.left_namespace, launch_gripper=bool(args.gripper))]
        if args.mode == "dual":
            arms.append(ArmConfig(label="right", robot_ip=args.right_ip, namespace=args.right_namespace, launch_gripper=bool(args.gripper)))

        layout["footer"].update(Panel("Controls: [cyan]Q[/]: Shut Down Sequence | [cyan]L[/]: Reboot Left | [cyan]R[/]: Reboot Right", border_style="dim"))
        LOGGER.info("Parameter settings verified. Connecting to hardware controllers...")

        # Hardware API Integration Runtime
        pixi_env = args.pixi_env
        protocol = args.protocol
        clients: dict[str, FrankaLockUnlock] = {}
        
        tmux_manager = TmuxManager(cwd=WORKSPACE_ROOT)
        tmux_manager.launch_tmux()

        try:
            for arm in arms:
                username, password = get_desk_credentials(arm.label)
                LOGGER.info(f"Connecting to Franka Desk WebAPI: {protocol}://{arm.robot_ip}")
                clients[arm.label] = enable_arm_with_desk(arm, username, password, protocol)
            
            # --- Interactive Operational Safety Acknowledgment Loop ---
            LOGGER.warning("[SAFETY CHECK] EMERGENCY STOP MUST be open & Status Ring light MUST show Blue.")
            LOGGER.warning("==> Press [bold yellow]ENTER[/] directly inside this window context to confirm safety compliance...")
            
            while True:
                layout["logs"].update(Panel(TERMINAL_STREAM.get_text(), title="[bold green]System Output Logs[/]"))
                check_key = read_key()
                if check_key in ("\n", "\r"):
                    LOGGER.info("Safety compliance checklist acknowledged by operator.")
                    break
                time.sleep(0.02)

            # Route execution profiles to Tmux target frames
            left_panda_command = build_panda_launch_command(arms[0], pixi_env)
            tmux_manager.send_command_to_pane(0, left_panda_command)
            
            if args.mode == "dual":
                right_panda_command = build_panda_launch_command(arms[1], pixi_env)
                tmux_manager.send_command_to_pane(1, right_panda_command)

            if args.camera:
                tmux_manager.send_command_to_pane(2, build_3rd_camera_launch_command(pixi_env))
                tmux_manager.send_command_to_pane(3, build_wrist_camera_launch_command(pixi_env))
                
            LOGGER.info("Core pipelines running. Activating background RQT diagnostics panel...")
            time.sleep(10)
            launch_rqt_background()

            # -------------------------------------------------------------------
            # Main Telemetry Interface Framework Monitor Loop
            # -------------------------------------------------------------------
            old_terminal_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            try:
                while True:
                    # Sync structural text view container
                    layout["logs"].update(Panel(TERMINAL_STREAM.get_text(), title="[bold green]System Output Logs[/]"))
                    
                    key = read_key().lower()
                    if key == "q":
                        LOGGER.info("System operational quit call received. Tearing down active process sessions...")
                        return 0
                    
                    elif key == "l":
                        LOGGER.warning("Reboot sequence triggered for Left arm controller...")
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                        try:
                            tmux_manager.send_interupt_to_pane(0)
                            clients[arms[0].label].reboot_sys()
                            LOGGER.info("Awaiting hardware brake re-engagement. Press Enter when ready...")
                            input()
                            tmux_manager.send_command_to_pane(0, left_panda_command)
                        finally:
                            tty.setcbreak(sys.stdin.fileno())
                            
                    elif key == "r" and args.mode == "dual":
                        LOGGER.warning("Reboot sequence triggered for Right arm controller...")
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                        try:
                            tmux_manager.send_interupt_to_pane(1)
                            clients[arms[1].label].reboot_sys()
                            LOGGER.info("Awaiting hardware brake re-engagement. Press Enter when ready...")
                            input()
                            tmux_manager.send_command_to_pane(1, right_panda_command)
                        finally:
                            tty.setcbreak(sys.stdin.fileno())
                            
                    time.sleep(0.02)
            finally:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                
        except KeyboardInterrupt:
            LOGGER.info("Ctrl+C call caught. Terminating workspace runtime processes...")
            return 130
        except Exception as e:
            import traceback
            # Restore normal streams to cleanly output tracebacks on fallback crashes
            sys.stdout = TERMINAL_STREAM._stdout
            sys.stderr = TERMINAL_STREAM._stderr
            print(f"\nCRITICAL CORE FAULT: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return 1
        finally:
            tmux_manager.kill_tmux_session()

if __name__ == "__main__":
    sys.exit(main())