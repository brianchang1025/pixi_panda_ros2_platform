#!/usr/bin/env python3

import logging
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from launch_interface import ArmConfig


def launch_in_new_terminal(
    title: str,
    command: str,
    cwd: Path,
    logger: logging.Logger | None = None,
) -> None:
    payload = (
        f"cd {shlex.quote(str(cwd))} && {command}; "
        "status=$?; "
        "echo; "
        "echo '[process exited with code' \"$status\" ']'; "
        "echo 'Press Enter to close this terminal...'; "
        "read"
    )

    if shutil.which("gnome-terminal"):
        subprocess.Popen(["gnome-terminal", "--title", title, "--", "bash", "-lc", payload])
        return

    if shutil.which("konsole"):
        subprocess.Popen(["konsole", "-p", f"tabtitle={title}", "-e", "bash", "-lc", payload])
        return

    if shutil.which("xterm"):
        subprocess.Popen(["xterm", "-T", title, "-e", "bash", "-lc", payload])
        return

    if shutil.which("tilix"):
        subprocess.Popen(["tilix", "--title", title, "-e", "bash", "-lc", payload])
        return

    if shutil.which("tmux"):
        session = "franka_platform"
        has_session = subprocess.run(
            ["tmux", "has-session", "-t", session],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0

        if not has_session:
            subprocess.Popen(["tmux", "new-session", "-d", "-s", session, "-n", title, "bash", "-lc", payload])
        else:
            subprocess.Popen(["tmux", "new-window", "-t", session, "-n", title, "bash", "-lc", payload])

        if logger is not None:
            logger.info(f"Opened in tmux session '{session}'. Attach with: tmux attach -t {session}")
        return

    raise RuntimeError(
        "No supported terminal emulator found (gnome-terminal/konsole/xterm/tilix/tmux)."
    )


def stop_process_by_pattern(pattern: str, wait_seconds: float = 1.0) -> None:
    subprocess.run(
        ["pkill", "-2", "-f", pattern],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(wait_seconds)
    subprocess.run(
        ["pkill", "-15", "-f", pattern],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_launch_command(arm: "ArmConfig", pixi_env: str) -> List[str]:
    """Build ROS 2 launch command for a single arm.
    
    Args:
        arm: Arm configuration with IP, namespace, and camera settings
        pixi_env: Pixi environment name (e.g., 'jazzy-realsense')
        
    Returns:
        Command as list of strings suitable for subprocess/shlex.join()
    """
    # Quote namespace if empty to avoid "namespace:=" which is invalid syntax
    namespace_arg = f'namespace:="{arm.namespace}"' if not arm.namespace else f"namespace:={arm.namespace}"
    return [
        "pixi",
        "run",
        "-e",
        pixi_env,
        "franka_platform",
        f"robot_ip:={arm.robot_ip}",
        namespace_arg,
        f"load_camera:={'true' if arm.launch_camera else 'false'}",
    ]


def start_single_launch(
    arm: "ArmConfig",
    pixi_env: str,
    workspace_root: Path,
    logger: logging.Logger,
    mode: str = "dual",
) -> None:
    """Start a single arm's launch in a new terminal.
    
    Args:
        arm: Arm configuration
        pixi_env: Pixi environment name
        workspace_root: Root of the workspace
        logger: Logger for status messages
        mode: Robot mode ('single' or 'dual')
    """
    command = shlex.join(build_launch_command(arm, pixi_env))
    arm_display = arm.namespace if mode == "single" else arm.label
    logger.info(f"Starting {arm_display} in new terminal: {command}")
    launch_in_new_terminal(
        title=f"franka_{arm.namespace}",
        command=command,
        cwd=workspace_root,
        logger=logger,
    )


def start_launches(
    arms: List["ArmConfig"],
    pixi_env: str,
    workspace_root: Path,
    logger: logging.Logger,
    mode: str = "dual",
) -> None:
    """Start launches for multiple arms with staggered timing.
    
    Args:
        arms: List of arm configurations
        pixi_env: Pixi environment name
        workspace_root: Root of the workspace
        logger: Logger for status messages
        mode: Robot mode ('single' or 'dual')
    """
    for arm in arms:
        start_single_launch(arm, pixi_env, workspace_root, logger, mode)
        time.sleep(1)


def stop_single_process(arm: "ArmConfig", pixi_env: str) -> None:
    """Stop a single arm's launch process.
    
    Args:
        arm: Arm configuration
        pixi_env: Pixi environment name
    """
    pattern = f"pixi run -e {pixi_env} franka_platform robot_ip:={arm.robot_ip} namespace:={arm.namespace}"
    stop_process_by_pattern(pattern)


def stop_processes(arms: List["ArmConfig"], pixi_env: str) -> None:
    """Stop launch processes for multiple arms.
    
    Args:
        arms: List of arm configurations
        pixi_env: Pixi environment name
    """
    for arm in arms:
        stop_single_process(arm, pixi_env)