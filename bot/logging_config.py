"""
bot/logging_config.py
=====================
Logging configuration for the trading bot.

Sets up two output handlers:
  Console handler : INFO level and above — concise, human-readable
  File handler    : DEBUG level and above — full trace with timestamps

Log file location : logs/trading_bot.log (created automatically)
Rotation policy   : Max 5 MB per file, 3 backup files kept

Why two handlers?
  The console shows the user what's happening without noise.
  The file captures everything including full API request/response
  bodies, which are essential for debugging and auditing orders.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# Log directory is at the project root (one level above this file)
LOG_DIR  = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """
    Initialise and return the root trading_bot logger.

    Safe to call multiple times — duplicate handlers are prevented by
    checking if handlers are already attached before adding new ones.

    Parameters
    ----------
    level : Minimum log level for the logger itself (default DEBUG).
            Handlers have their own levels set independently.

    Returns
    -------
    logging.Logger : The configured "trading_bot" logger instance.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("trading_bot")

    # Guard against duplicate handlers if setup_logging() is called again
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Verbose format for the log file — includes module name for traceability
    fmt_file = logging.Formatter(
        "%(asctime)s  [%(levelname)-8s]  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Compact format for the console — just time, level, and message
    fmt_console = logging.Formatter(
        "%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%H:%M:%S",
    )

    # File handler: DEBUG and above, rotates at 5 MB, keeps 3 backups
    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt_file)

    # Console handler: INFO and above (suppress debug-level API traces)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt_console)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
