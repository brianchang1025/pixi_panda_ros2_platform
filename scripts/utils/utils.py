#!/usr/bin/env python3

import logging
import os
import select
import sys
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.franka_desk import FrankaLockUnlock

try:
    from rich import print as rich_print  # type: ignore[import-not-found]
    from rich.panel import Panel  # type: ignore[import-not-found]
    from rich.text import Text  # type: ignore[import-not-found]
except ImportError:
    rich_print = None
    Panel = None
    Text = None

LOGGER = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ArmConfig:
    label: str
    robot_ip: str
    namespace: str
    launch_gripper: bool


def wait_for_operator_ready() -> None:
    LOGGER.warning("IMPORTANT SAFETY CHECK before launching robot terminals:")
    LOGGER.warning("- EMERGENCY STOP MUST be open.")
    LOGGER.warning("- Robot status light MUST be blue.")
    LOGGER.warning("Press Enter only after both conditions are confirmed.")
    input()


def get_desk_credentials(arm_label: str) -> tuple[str, str]:
    arm_key = arm_label.upper()
    username = os.getenv(f"FRANKA_DESK_USERNAME_{arm_key}") or os.getenv("FRANKA_DESK_USERNAME")
    password = os.getenv(f"FRANKA_DESK_PASSWORD_{arm_key}") or os.getenv("FRANKA_DESK_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "Missing Franka Desk credentials. Set per-arm env vars "
            f"FRANKA_DESK_USERNAME_{arm_key}/FRANKA_DESK_PASSWORD_{arm_key} "
            "or global FRANKA_DESK_USERNAME/FRANKA_DESK_PASSWORD."
        )
    return username, password


def enable_arm_with_desk(
    arm: "ArmConfig",
    username: str,
    password: str,
    protocol: str,
) -> "FrankaLockUnlock":
    from utils.franka_desk import FrankaLockUnlock

    LOGGER.info(
        f"Connecting to Franka Desk at {protocol}://{arm.robot_ip}")
    client = FrankaLockUnlock(
        hostname=arm.robot_ip,
        username=username,
        password=password,
        protocol=protocol,
        relock=True,
    )
    client.enable_robot()
    return client




def read_key() -> str:
    select.select([sys.stdin], [], [])
    return sys.stdin.read(1)


def show_keyboard_controls_panel(mode: str = "dual") -> None:
    if rich_print is not None and Panel is not None and Text is not None:
        if mode == "single":
            panel_text = (
                "[q] Quit launcher\n"
                "[s] Show runtime status\n"
                "[h] Show this help\n"
                "[l] Reboot and relaunch arm"
            )
        else:
            panel_text = (
                "[q] Quit launcher\n"
                "[s] Show runtime status\n"
                "[h] Show this help\n"
                "[l] Reboot and relaunch left arm\n"
                "[r] Reboot and relaunch right arm"
            )
        content = Text(panel_text)
        rich_print(Panel(content, title="Control Panel", border_style="blue"))
        return

def build_panda_launch_command(arm: "ArmConfig", pixi_env: str) -> List[str]:
    """Build ROS 2 launch command for a single arm.
    
    Args:
        arm: Arm configuration with IP, namespace, and camera settings
        pixi_env: Pixi environment name (e.g., 'jazzy-realsense')
        
    Returns:
        Command as list of strings suitable for subprocess/shlex.join()
    """
    # Quote namespace if empty to avoid "namespace:=" which is invalid syntax
    cmd = [
        "pixi",
        "run",
        "-e",
        pixi_env,
        "franka_platform",
        f"robot_ip:={arm.robot_ip}",
        f"namespace:={arm.namespace}",
        f"load_gripper:={'true' if arm.launch_gripper else 'false'}",
    ]
    return " ".join(cmd)

def build_3rd_camera_launch_command(pixi_env: str) -> List[str]:
    """Build ROS 2 launch command for third-person camera in its own terminal."""
    cmd = [
        "pixi",
        "run",
        "-e",
        pixi_env,
        "third_person_realsense",
    ]
    return " ".join(cmd)

def build_wrist_camera_launch_command(pixi_env: str) -> List[str]:
    """Build ROS 2 launch command for wrist camera in its own terminal."""
    cmd = [
        "pixi",
        "run",
        "-e",
        pixi_env,
        "wrist_realsense",
    ]
    return " ".join(cmd)

def launch_rqt_background():
    """
    Launches rqt in the background, redirecting output and errors to /dev/null
    to keep the terminal clean.
    """
    # We use a single string with shell=True to easily handle the redirects
    cmd = "rqt > /dev/null 2>&1 &"
    
    try:
        # Popen starts the process and moves on immediately
        subprocess.Popen(cmd, shell=True, preexec_fn=os.setpgrp)
        LOGGER.info("🚀 rqt launched in background (logs silenced).")
    except Exception as e:
        LOGGER.error(f"❌ Failed to launch rqt: {e}")