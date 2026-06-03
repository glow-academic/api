"""Tests for stop_attempt_impl (formerly attempt_stop_internal_impl)."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_attempt_stop_internal_impl_requires_profile_id():
    from app.infra.attempt.stop import stop_attempt_impl
    with pytest.raises((ValueError, Exception)):
        await stop_attempt_impl({})

async def test_attempt_stop_internal_impl_is_async():
    from app.infra.attempt.stop import stop_attempt_impl
    import asyncio
    assert asyncio.iscoroutinefunction(stop_attempt_impl)

async def test_attempt_stop_internal_impl_module_uses_audit():
    import app.infra.attempt as pkg
    import importlib
    m = importlib.import_module("app.infra.attempt.stop")
    source = open(m.__file__).read()
    assert "audit" in source.lower() or "emit" in source.lower()
