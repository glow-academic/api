"""Tests for attempt workflows."""
import pytest
pytestmark = pytest.mark.asyncio

async def test_generate_flag_to_resource_mapping():
    from app.infra.attempt.workflows import GENERATE_FLAG_TO_RESOURCE
    assert "generate_personas" in GENERATE_FLAG_TO_RESOURCE
    assert GENERATE_FLAG_TO_RESOURCE["generate_personas"] == "personas"

async def test_generate_flag_to_connection_mapping():
    from app.infra.attempt.workflows import GENERATE_FLAG_TO_CONNECTION
    assert "generate_personas" in GENERATE_FLAG_TO_CONNECTION

async def test_attempt_message_impl_is_async():
    from app.infra.attempt.workflows import attempt_message_impl
    import asyncio
    assert asyncio.iscoroutinefunction(attempt_message_impl)
