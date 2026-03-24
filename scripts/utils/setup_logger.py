"""Setup logging for the project scripts."""

import atexit
import logging
import queue
from logging.handlers import QueueListener
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from launch_interface import ArmConfig

try:
    from rich.logging import RichHandler  # pyright: ignore[reportMissingImports]
except ModuleNotFoundError:
    RichHandler = None


def setup_logging(level=logging.INFO):  # noqa: ANN001
    """Recommended logging setup for the project."""
    console_formatter = logging.Formatter(fmt="%(message)s", datefmt="[%X]")
    if RichHandler is not None:
        console_handler = RichHandler(rich_tracebacks=True)
    else:
        console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]"
    )
    file_handler = logging.FileHandler("crisp.log")
    file_handler.setFormatter(file_formatter)

    log_queue = queue.Queue()
    # queue_handler = QueueHandler(log_queue)

    logger = logging.getLogger()
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(console_handler)

    handlers = [
        console_handler,
    ]

    listener = QueueListener(log_queue, *handlers)
    listener.start()

    atexit.register(listener.stop)


def log_arguments(args, logger: logging.Logger) -> None:
    """Log command-line arguments.
    
    Args:
        args: Argument namespace from argparse
        logger: Logger instance to use for output
    """
    logger.info("Arguments:")
    for arg, value in vars(args).items():
        logger.info(f"{arg:<20}: {value}")


def log_runtime_status(arms: List["ArmConfig"], pixi_env: str, logger: logging.Logger) -> None:
    """Log current runtime status with arm information.
    
    Args:
        arms: List of arm configurations
        pixi_env: Pixi environment name
        logger: Logger instance to use for output
    """
    arm_status = ", ".join(
        [
            f"{arm.label}(ip={arm.robot_ip}, ns={arm.namespace}, camera={arm.launch_camera})"
            for arm in arms
        ]
    )
    logger.info(f"Runtime status | env={pixi_env} | arms: {arm_status}")
