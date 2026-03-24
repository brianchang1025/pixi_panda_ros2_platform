"""Prompt utility for user input in command-line applications."""

import logging

logger = logging.getLogger(__name__)


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
    """Prompt the user to choose from a list of options or just enter a string.

    Args:
        message (str): The prompt message to display.
        options (list, optional): A list of string options to choose from.
        default (str, optional): The default value to use if user enters nothing.

    Returns:
        str: The selected or entered string.
    """
    logger.info("-" * 40)
    if options:
        logger.info(message)
        for i, option in enumerate(options, 1):
            logger.info(f"{i}. {option}")
        if default:
            logger.info(f"(Default: {default})")
        logger.info("-" * 40)

        while True:
            logger.info("Enter number, text, or press Enter for default: ")
            choice = input().strip()
            if not choice:
                if default:
                    return default
                else:
                    logger.info("No input given and no default set. Try again.")
                    continue
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(options):
                    return options[index]
                else:
                    logger.info("Invalid number. Try again.")
            elif choice in options:
                return choice
            else:
                logger.info("Invalid input. Try again.")
    else:
        # For string input without options
        if default is not None:
            message += f" (Default: '{default}')"
        logger.info(message)
        logger.info("-" * 40)
        
        while True:
            logger.info("Enter string, press Enter for default, or type / for empty string:")
            response = input()
            # Allow typing / to explicitly set empty string
            response = response.strip()
            if response:
                return response
            elif default is not None:
                return default
            else:
                logger.info("No input given and no default set. Try again.")
