#!/usr/bin/env python3

import logging
import os
import select
import sys
import time
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
    launch_camera: bool


def wait_for_operator_ready() -> None:
    LOGGER.warning("IMPORTANT SAFETY CHECK before launching robot terminals:")
    LOGGER.warning("- USER STOP MUST be open.")
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


def reboot_and_relaunch_side(
    side: str,
    arms: List["ArmConfig"],
    clients: dict[str, "FrankaLockUnlock"],
    pixi_env: str,
    logger: logging.Logger,
    mode: str = "dual",
) -> None:
    from utils.terminal_launcher import stop_single_process, start_single_launch

    arm = next((candidate for candidate in arms if candidate.label == side), None)
    if arm is None:
        logger.warning(f"No {side} arm is configured; cannot reboot the {side} arm.")
        return

    client = clients.get(side)
    if client is None:
        logger.warning(f"{side.capitalize()} Franka Desk client is missing; cannot reboot the {side} arm.")
        return

    logger.info(f"Received '{side[0]}': rebooting the {side} arm via Franka Desk...")
    client.reboot_sys()

    logger.info(f"Stopping the {side} launch process...")
    stop_single_process(arm, pixi_env)
    time.sleep(1)

    logger.info(f"Confirm safety before relaunching the {side} arm.")
    wait_for_operator_ready()

    logger.info(f"Reopening the {side} launch terminal...")
    start_single_launch(arm, pixi_env, WORKSPACE_ROOT, logger, mode)


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
