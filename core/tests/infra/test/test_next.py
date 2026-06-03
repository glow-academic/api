"""Tests for test_run_internal_impl (formerly test_next_internal_impl).

The legacy ``test.next`` canonical-orchestration entry was removed; it
delegated to the test-run orchestration, which survives as
``test_run_internal_impl`` in ``app.infra.test.run``.
"""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_test_next_internal_impl_requires_profile_id():
    from app.infra.test.run import test_run_internal_impl
    with pytest.raises((ValueError, Exception)):
        await test_run_internal_impl({})

async def test_test_next_internal_impl_is_async():
    from app.infra.test.run import test_run_internal_impl
    import asyncio
    assert asyncio.iscoroutinefunction(test_run_internal_impl)

async def test_test_next_internal_impl_module_uses_audit():
    import app.infra.test as pkg
    import importlib
    m = importlib.import_module("app.infra.test.run")
    source = open(m.__file__).read()
    assert "audit" in source.lower() or "emit" in source.lower()
