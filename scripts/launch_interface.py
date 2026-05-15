#!/usr/bin/env python3

import argparse
import logging
import time
import os
import sys
import termios
import tty
from typing import List

from utils.tmux_manager import TmuxManager
from utils.franka_desk import FrankaLockUnlock
from utils import prompt as prompt_utils
from utils.setup_logger import setup_logging, log_arguments, log_runtime_status
from utils.utils import (
    ArmConfig,
    wait_for_operator_ready,
    get_desk_credentials,
    enable_arm_with_desk,
    read_key,
    show_keyboard_controls_panel,
    WORKSPACE_ROOT,
    build_panda_launch_command,
    build_3rd_camera_launch_command,
    build_wrist_camera_launch_command,
    launch_rqt_background
)

LOGGER = logging.getLogger(__name__)


def parse_bool_arg(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False

    raise argparse.ArgumentTypeError(
        "Expected a boolean value (true/false, yes/no, 1/0)."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare one or two Franka arms using Desk, then launch franka_platform.",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "dual"],
        default=None,
        help="Robot mode: single arm or dual arm for operation.",
    )
    parser.add_argument(
        "--camera",
        type=parse_bool_arg,
        nargs="?",
        const=True,
        default=True,
        metavar="{true,false}",
        help="Launch camera nodes in franka_platform (e.g. --camera false).",
    )
    parser.add_argument(
        "--gripper",
        type=parse_bool_arg,
        nargs="?",
        const=True,
        default=True,
        metavar="{true,false}",
        help="Load gripper in franka_platform (e.g. --gripper false).",
    )
    parser.add_argument(
        "--left-ip",
        default=None,
        help="IP address for left arm.",
    ) # change to first-ip after testing
    parser.add_argument(
        "--left-namespace",
        default=None,
        help="ROS namespace for left arm.",
    ) # change to first-namespace after testing
    parser.add_argument(
        "--right-ip",
        default=None,
        help="IP address for right arm.",
    ) # change to second-ip after testing
    parser.add_argument(
        "--right-namespace",
        default=None,
        help="ROS namespace for right arm.",
    ) # change to second-namespace after testing
    parser.add_argument(
        "--pixi-env",
        choices=["jazzy", "jazzy-realsense"],
        default="jazzy-realsense",
        help="Pixi environment. If not set, defaults to jazzy-realsense with camera, otherwise jazzy.",
    ) # delete after testing
    parser.add_argument(
        "--protocol",
        default="https",
        help="Desk protocol for the robot web API.",
    ) # dlete after testing
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

    logger.info(f"Using camera_enabled: {args.camera}")
    logger.info(f"Using gripper_enabled: {args.gripper}")

    left_arm_text = "arm" if args.mode == "single" else "left arm"

    if args.left_ip is None:
        args.left_ip = prompt_utils.prompt(
            message=f"Please enter IP address for {left_arm_text}",
            default=os.getenv("FRANKA_IP_LEFT", "192.168.31.10"),
        )
        logger.info(f"Using {left_arm_text} IP: {args.left_ip}")

    if args.left_namespace is None:
        args.left_namespace = prompt_utils.prompt(
            message=f"Please enter namespace for {left_arm_text}",
            default=os.getenv("FRANKA_NAMESPACE_LEFT", "left"),
        )
        logger.info(f"Using {left_arm_text} namespace: {args.left_namespace}")

    if args.mode == "dual":
        if args.right_ip is None:
            args.right_ip = prompt_utils.prompt(
                message="Please enter IP address for right arm",
                default=os.getenv("FRANKA_IP_RIGHT", "192.168.32.10"),
            )
            logger.info(f"Using right arm IP: {args.right_ip}")

        if args.right_namespace is None:
            args.right_namespace = prompt_utils.prompt(
                message="Please enter namespace for right arm",
                default=os.getenv("FRANKA_NAMESPACE_RIGHT", "right"),
            )
            logger.info(f"Using right namespace: {args.right_namespace}")

    arms = [
        ArmConfig(
            label="left",
            robot_ip=args.left_ip,
            namespace=args.left_namespace,
            launch_gripper=bool(args.gripper),
        )
    ] # camera part should be removed after testing

    if args.mode == "dual":
        arms.append(
            ArmConfig(
                label="right",
                robot_ip=args.right_ip,
                namespace=args.right_namespace,
                launch_gripper=bool(args.gripper),
            )
        ) # camera part should be removed after testing

        namespaces = {arm.namespace for arm in arms}
        if len(namespaces) != len(arms):
            raise ValueError("Dual-arm mode requires unique namespaces for each arm.")

    return args.mode, bool(args.camera), arms


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(level=getattr(logging, args.log_level.upper()))
    log_arguments(args, LOGGER)

    mode, camera_enabled, arms = resolve_runtime_arguments(args, LOGGER)

    pixi_env = args.pixi_env # delete after testing
    protocol = args.protocol # delete after testing

    clients: dict[str, FrankaLockUnlock] = {}
    tmux_manager = TmuxManager(cwd=WORKSPACE_ROOT)
    tmux_manager.launch_tmux()

    try:
        for arm in arms:
            username, password = get_desk_credentials(arm.label) #map the arm label to the appropriate credentials
            arm_display = "" if mode == "single" else arm.label
            LOGGER.info(f"Preparing {arm_display} arm with ip={arm.robot_ip}, namespace={arm.namespace}")
            clients[arm.label] = enable_arm_with_desk(arm, username, password, protocol)
        wait_for_operator_ready()
        
        if mode == "single":
            left_panda_command = build_panda_launch_command(arms[0], pixi_env)
            tmux_manager.send_command_to_pane(0, left_panda_command)
        else:
            left_panda_command = build_panda_launch_command(arms[0], pixi_env)
            tmux_manager.send_command_to_pane(0, left_panda_command)
            right_panda_command = build_panda_launch_command(arms[1], pixi_env)
            tmux_manager.send_command_to_pane(1, right_panda_command)

        if camera_enabled:
            third_camera_command = build_3rd_camera_launch_command(pixi_env)
            tmux_manager.send_command_to_pane(2, third_camera_command)
            wrist_camera_command = build_wrist_camera_launch_command(pixi_env)
            tmux_manager.send_command_to_pane(3, wrist_camera_command)
            
        time.sleep(10)  # Wait a bit for the main launches to start before launching RQT
        launch_rqt_background()

        old_terminal_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        try:
            while True:
                show_keyboard_controls_panel(mode)
                key = read_key()
                key = key.lower()
                if key == "q":
                    LOGGER.info("Received 'q': stopping the launch interface.")
                    return 0
                if key == "s":
                    pass
                    continue
                if key == "h":
                    show_keyboard_controls_panel(mode)
                    continue
                if key == "l":
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                    try:
                        tmux_manager.send_interupt_to_pane(0)
                        clients[arms[0].label].reboot_sys()
                        wait_for_operator_ready()
                        tmux_manager.send_command_to_pane(0, left_panda_command)
                    finally:
                        tty.setcbreak(sys.stdin.fileno())
                    continue
                if key == "r":
                    if mode == "dual":
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
                        try:
                            tmux_manager.send_interupt_to_pane(1)
                            clients[arms[1].label].reboot_sys()
                            wait_for_operator_ready()
                            tmux_manager.send_command_to_pane(1, right_panda_command)
                        finally:
                            tty.setcbreak(sys.stdin.fileno())
                    continue
        finally:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal_settings)
    except KeyboardInterrupt:
        LOGGER.info("Interrupted. Stopping launch processes...")
        return 130
    except Exception as e:
        LOGGER.exception(f"An error occurred while launching: {e}")
        return 1
    finally:
        tmux_manager.kill_tmux_session()
        # Keep references alive until shutdown so Desk cleanup can relock on exit.
        _ = clients


if __name__ == "__main__":
    sys.exit(main())