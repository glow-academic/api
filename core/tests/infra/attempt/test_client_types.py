"""Tests for attempt client_types — Pydantic payload models."""
import pytest
from uuid import uuid4
from app.infra.attempt.client_types import (
    AttemptJoinPayload, AttemptLeavePayload, AttemptStartPayload,
    MESSAGE_ENTRY_TYPES,
)
pytestmark = pytest.mark.asyncio

async def test_join_payload():
    p = AttemptJoinPayload(chat_id=uuid4())
    assert p.chat_id is not None

async def test_leave_payload():
    p = AttemptLeavePayload(chat_id=uuid4())
    assert p.chat_id is not None

async def test_start_payload_requires_one_parent():
    with pytest.raises(ValueError):
        AttemptStartPayload()

async def test_message_entry_types_constant():
    assert "contents" in MESSAGE_ENTRY_TYPES
