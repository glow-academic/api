"""Tests for test workflows."""
import pytest
pytestmark = pytest.mark.asyncio

async def test_test_progress_impl_is_async():
    from app.infra.test.workflows import test_progress_impl
    import asyncio
    assert asyncio.iscoroutinefunction(test_progress_impl)

async def test_test_next_impl_is_async():
    from app.infra.test.workflows import test_next_impl
    import asyncio
    assert asyncio.iscoroutinefunction(test_next_impl)

async def test_test_run_impl_is_async():
    from app.infra.test.workflows import test_run_impl
    import asyncio
    assert asyncio.iscoroutinefunction(test_run_impl)
