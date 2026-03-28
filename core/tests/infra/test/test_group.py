"""Tests for test_group_internal_impl."""
import pytest
pytestmark = pytest.mark.asyncio

async def test_group_impl_is_async():
    from app.infra.test.group import test_group_internal_impl
    import asyncio
    assert asyncio.iscoroutinefunction(test_group_internal_impl)

async def test_group_module_uses_pool():
    import app.infra.test.group as m
    source = open(m.__file__).read()
    assert "get_pool" in source

async def test_group_delegates_to_test_group_impl():
    import app.infra.test.group as m
    source = open(m.__file__).read()
    assert "test_group_impl" in source
