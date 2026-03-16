"""Tests for centralized logger helpers."""

from app.utils.logging.db_logger import get_logger, profile_id_context, set_profile_id


def test_get_logger_preserves_propagation():
    logger = get_logger("test.logger")

    assert logger.name == "test.logger"
    assert logger.propagate is True


def test_set_profile_id_updates_contextvar():
    token = profile_id_context.set(None)
    try:
        set_profile_id("profile-123")
        assert profile_id_context.get() == "profile-123"
    finally:
        profile_id_context.reset(token)
