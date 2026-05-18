"""Tests for app.utils.logging.db_logger."""

import logging

from app.utils.logging.db_logger import get_logger, profile_id_context, set_profile_id


def test_get_logger_returns_logger_instance():
    """get_logger returns a standard logging.Logger."""
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)


def test_get_logger_uses_given_name():
    """The returned logger has the name that was passed in."""
    logger = get_logger("my.custom.module")
    assert logger.name == "my.custom.module"


def test_logger_propagates():
    """Logger should have propagate=True so it reaches the root handler."""
    logger = get_logger("propagation.test")
    assert logger.propagate is True


def test_set_profile_id_stores_value():
    """set_profile_id stores the value in the context variable."""
    set_profile_id("profile-abc-123")
    assert profile_id_context.get() == "profile-abc-123"
    # Clean up
    set_profile_id(None)


def test_set_profile_id_none_clears():
    """Setting profile_id to None clears it."""
    set_profile_id("some-id")
    set_profile_id(None)
    assert profile_id_context.get() is None
