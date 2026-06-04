"""Tests for test client_types — Pydantic payload models."""
import pytest
from uuid import uuid4
from app.infra.test.client_types import (
    TestJoinPayload, TestLeavePayload, TestStartPayload,
    TestNextPayload, TestRunPayload, TEST_GRADE_ENTRY_TYPES,
)
pytestmark = pytest.mark.asyncio

async def test_join_payload():
    p = TestJoinPayload(invocation_id=uuid4())
    assert p.invocation_id is not None

async def test_start_payload():
    p = TestStartPayload(eval_id=uuid4())
    assert p.eval_id is not None
    assert p.infinite_mode is False

async def test_grade_entry_types():
    assert "grades" in TEST_GRADE_ENTRY_TYPES
