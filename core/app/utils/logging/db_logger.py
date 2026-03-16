"""Centralized logger utility.

Provides a logger with automatic module-based logger names and profile ID context.
"""

import contextvars
import logging

# Context variable to store profile_id for logger access
profile_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "profile_id", default=None
)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance that writes to console
    """
    logger = logging.getLogger(name)

    # Ensure logger propagates to root logger (for console output)
    logger.propagate = True

    return logger


def set_profile_id(profile_id: str | None) -> None:
    """Set the profile_id in context for logger access.

    Args:
        profile_id: Profile ID to set in context
    """
    profile_id_context.set(profile_id)
