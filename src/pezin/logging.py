"""Centralized logging configuration for Pezin using loguru."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logging(log_level: Optional[str] = None) -> None:
    """Configure loguru logging for Pezin.

    Args:
        log_level: Optional log level override. Defaults to LOG_LEVEL env var or INFO.
    """
    # Remove default handler
    logger.remove()

    # Get log level from parameter, environment, or default to INFO
    level = log_level or os.environ.get("LOG_LEVEL", "INFO")

    try:
        logging_definitions(level)
    except subprocess.CalledProcessError:
        # Fallback to console only if not in git repo
        logger.add(
            sys.stdout,
            level=level,
            format="{level} | {message}",
        )


def logging_definitions(level):
    # Try to set up file logging in .git directory
    git_dir_result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    git_dir = Path(git_dir_result.stdout.strip())
    log_file = git_dir / "pezin.log"

    # Add file handler with rotation
    logger.add(
        log_file,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        rotation="1 MB",
        retention="10 days",
    )

    # Add console handler for immediate feedback
    logger.add(
        sys.stdout,
        level="INFO",
        format="{level} | {message}",
    )

    logger.info(f"Pezin logging to: {log_file}")


def get_logger():
    """Get the configured logger instance.

    Returns:
        loguru.Logger: Configured logger instance
    """
    return logger
