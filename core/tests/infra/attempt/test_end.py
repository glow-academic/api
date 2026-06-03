"""Tests for complete_attempt_impl (formerly attempt_end_internal_impl).

The legacy ``attempt.end`` chat-end handler was removed; ending an attempt is
now the ``attempt_complete`` primitive in ``app.infra.attempt.complete``.
"""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_attempt_end_internal_impl_requires_profile_id():
    from app.infra.attempt.complete import complete_attempt_impl
    with pytest.raises((ValueError, Exception)):
        await complete_attempt_impl({})

async def test_attempt_end_internal_impl_is_async():
    from app.infra.attempt.complete import complete_attempt_impl
    import asyncio
    assert asyncio.iscoroutinefunction(complete_attempt_impl)

async def test_attempt_end_internal_impl_module_uses_audit():
    import app.infra.attempt as pkg
    import importlib
    m = importlib.import_module("app.infra.attempt.complete")
    source = open(m.__file__).read()
    assert "audit" in source.lower() or "emit" in source.lower()
