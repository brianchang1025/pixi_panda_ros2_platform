#!/usr/bin/env python3

import argparse
import logging
import os
import select
import sys
import termios
import time
import tty
from typing import List

try:
    from rich import print as rich_print  # type: ignore[import-not-found]
    from rich.panel import Panel  # type: ignore[import-not-found]
    from rich.text import Text  # type: ignore[import-not-found]
except ImportError:
    rich_print = None
    Panel = None
    Text = None

from utils.franka_desk import FrankaLockUnlock
from utils import prompt as prompt_utils
from utils.prompt import prompt_bool
from utils.setup_logger import setup_logging, log_arguments, log_runtime_status
from utils.terminal_launcher import (
    launch_in_new_terminal,
    stop_process_by_pattern,
    build_launch_command,
    start_single_launch,
    start_launches,
    stop_single_process,
    stop_processes,
)
from utils.utils import (
    ArmConfig,
    wait_for_operator_ready,
    get_desk_credentials,
    enable_arm_with_desk,
    reboot_and_relaunch_side,
    read_key,
    show_keyboard_controls_panel,
    WORKSPACE_ROOT,
)


DEFAULT_PROTOCOL = "https"
LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare one or two Franka arms using Desk, then launch franka_platform.",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "dual"],
        default=None,
        help="Robot mode: single arm or dual arm for teleoperation.",
    )
    camera_group = parser.add_mutually_exclusive_group()
    camera_group.add_argument(
        "--camera",
        dest="camera",
        action="store_true",
        default=True,
        help="Launch camera nodes in franka_platform.",
    )
    camera_group.add_argument(
        "--no-camera",
        dest="camera",
        action="store_false",
        default=None,
        help="Disable camera launch explicitly.",
    )
    parser.add_argument(
        "--camera-arm",
        choices=["left", "right"],
        default="left",
        help="In dual mode, which side gets load_camera true.",
    )
    parser.add_argument(
        "--left-ip",
        default=None,
        help="IP address for left arm.",
    )
    parser.add_argument(
        "--left-namespace",
        default=None,
        help="ROS namespace for left arm.",
    )
    parser.add_argument(
        "--right-ip",
        default=None,
        help="IP address for right arm.",
    )
    parser.add_argument(
        "--right-namespace",
        default=None,
        help="ROS namespace for right arm.",
    )
    parser.add_argument(
        "--pixi-env",
        choices=["jazzy", "jazzy-realsense"],
        default="jazzy-realsense",
        help="Pixi environment. If not set, defaults to jazzy-realsense with camera, otherwise jazzy.",
    )
    parser.add_argument(
        "--protocol",
        default=DEFAULT_PROTOCOL,
        help="Desk protocol for the robot web API.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logger level.",
    )
    return parser


def resolve_runtime_arguments(args: argparse.Namespace, logger: logging.Logger) -> tuple[str, bool, List[ArmConfig]]:
    if args.mode is None:
        args.mode = prompt_utils.prompt(
            message="Select teleoperation mode",
            options=["single", "dual"],
            default="single",
        )
        logger.info(f"Using teleoperation mode: {args.mode}")

    if args.camera is None:
        args.camera = prompt_bool("Launch camera nodes", default=True)
        logger.info(f"Using camera_enabled: {args.camera}")

    left_arm_text = "arm" if args.mode == "single" else "left arm"

    if args.left_ip is None:
        args.left_ip = prompt_utils.prompt(
            message=f"Please enter IP address for {left_arm_text}",
            default=os.getenv("LEFT_ROBOT_IP", os.getenv("ROBOT1_IP", "192.168.31.10")),
        )
        logger.info(f"Using {left_arm_text} IP: {args.left_ip}")

    if args.left_namespace is None:
        args.left_namespace = prompt_utils.prompt(
            message=f"Please enter namespace for {left_arm_text}",
            default=os.getenv("LEFT_ROBOT_NS", os.getenv("ROBOT1_NS", "left")),
        )
        logger.info(f"Using {left_arm_text} namespace: {args.left_namespace}")

    if args.mode == "dual":
        if args.right_ip is None:
            args.right_ip = prompt_utils.prompt(
                message="Please enter IP address for right arm",
                default=os.getenv("RIGHT_ROBOT_IP", os.getenv("ROBOT2_IP", "192.168.32.10")),
            )
            logger.info(f"Using right arm IP: {args.right_ip}")

        if args.right_namespace is None:
            args.right_namespace = prompt_utils.prompt(
                message="Please enter namespace for right arm",
                default=os.getenv("RIGHT_ROBOT_NS", os.getenv("ROBOT2_NS", "right")),
            )
            logger.info(f"Using right namespace: {args.right_namespace}")

    if len(sys.argv) == 1 and args.mode == "dual" and args.camera:
        args.camera_arm = prompt_utils.prompt(
            message="Select which arm launches camera",
            options=["left", "right"],
            default="left",
        )

    if args.mode == "single" and args.camera_arm == "right" and args.camera:
        raise ValueError("--camera-arm right is only valid in dual-arm mode.")

    arms = [
        ArmConfig(
            label="left",
            robot_ip=args.left_ip,
            namespace=args.left_namespace,
            launch_camera=bool(args.camera) and args.camera_arm == "left",
        )
    ]

    if args.mode == "dual":
        arms.append(
            ArmConfig(
                label="right",
                robot_ip=args.right_ip,
                namespace=args.right_namespace,
                launch_camera=bool(args.camera) and args.camera_arm == "right",
            )
        )

        namespaces = {arm.namespace for arm in arms}
        if len(namespaces) != len(arms):
            raise ValueError("Dual-arm mode requires unique namespaces for each arm.")

    return args.mode, bool(args.camera), arms




def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(level=getattr(logging, args.log_level.upper()))
    logger = logging.getLogger(__name__)

    log_arguments(args, logger)

    mode, camera_enabled, arms = resolve_runtime_arguments(args, logger)

    pixi_env = args.pixi_env 
    protocol = args.protocol

    if mode == "dual" and camera_enabled:
        selected_arm = next(arm.label for arm in arms if arm.launch_camera)

    clients: dict[str, FrankaLockUnlock] = {}
    started_launches = False

    try:
        for arm in arms:
            username, password = get_desk_credentials(arm.label)
            arm_display = "" if mode == "single" else arm.label
            logger.info(f"Preparing {arm_display} arm with ip={arm.robot_ip}, namespace={arm.namespace}")
            clients[arm.label] = enable_arm_with_desk(arm, username, password, protocol)

        wait_for_operator_ready()
        start_launches(arms, pixi_env, WORKSPACE_ROOT, logger, mode)
        started_launches = True
 

        old_terminal_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        try:
            show_keyboard_controls_panel(mode)
            while True:
                key = read_key()
                key = key.lower()
                if key == "q":
                    logger.info("Received 'q': stopping the launch interface.")
                    return 0
                if key == "s":
                    log_runtime_status(arms, pixi_env, logger)
                    continue
                if key == "h":
                    show_keyboard_controls_panel(mode)
                    continue
                if key == "l":
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                    try:
                        reboot_and_relaunch_side("left", arms, clients, pixi_env, logger, mode)
                    finally:
                        tty.setcbreak(sys.stdin.fileno())
                    continue
                if key == "r":
                    if mode == "dual":
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                        try:
                            reboot_and_relaunch_side("right", arms, clients, pixi_env, logger, mode)
                        finally:
                            tty.setcbreak(sys.stdin.fileno())
                    continue
        finally:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
    except KeyboardInterrupt:
        logger.info("Interrupted. Stopping launch processes...")
        return 130
    except Exception as e:
        logger.exception(f"An error occurred while launching: {e}")
        return 1
    finally:
        if started_launches:
            stop_processes(arms, pixi_env)
        # Keep references alive until shutdown so Desk cleanup can relock on exit.
        _ = clients


if __name__ == "__main__":
    sys.exit(main())