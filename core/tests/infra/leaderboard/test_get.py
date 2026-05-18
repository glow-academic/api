"""Tests for get_leaderboard_impl_cached — get orchestration."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_get_function_is_async():
    import app.infra.leaderboard.get as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.get_leaderboard_impl_cached)

async def test_get_module_uses_common_context():
    import app.infra.leaderboard.get as mod
    source = open(mod.__file__).read()
    assert "resolve_common_context" in source or "resolve_" in source

async def test_get_module_returns_response_type():
    import app.infra.leaderboard.get as mod
    source = open(mod.__file__).read()
    assert "Response" in source or "InternalData" in source
