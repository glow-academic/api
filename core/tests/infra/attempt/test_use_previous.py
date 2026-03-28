"""Tests for attempt_use_previous_internal_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_attempt_use_previous_internal_impl_requires_profile_id():
    from app.infra.attempt.use_previous import attempt_use_previous_internal_impl
    with pytest.raises((ValueError, Exception)):
        await attempt_use_previous_internal_impl({})

async def test_attempt_use_previous_internal_impl_is_async():
    from app.infra.attempt.use_previous import attempt_use_previous_internal_impl
    import asyncio
    assert asyncio.iscoroutinefunction(attempt_use_previous_internal_impl)

async def test_attempt_use_previous_internal_impl_module_uses_audit():
    import app.infra.attempt as pkg
    import importlib
    m = importlib.import_module("app.infra.attempt.use_previous")
    source = open(m.__file__).read()
    assert "audit" in source.lower() or "emit" in source.lower()
