"""Tests for the test-group wrapper (app.infra.test.group).

The module is now a thin wrapper over the shared resolve_group_impl: it
declares the artifact type plus per-artifact request/response subclasses and
delegates the actual resolve logic. These tests assert that current contract
rather than removed internals.
"""
import inspect

import asyncio

import pytest

pytestmark = pytest.mark.asyncio


async def test_group_impl_is_async():
    from app.infra.test.group import group_test_impl
    assert asyncio.iscoroutinefunction(group_test_impl)


async def test_group_impl_takes_pool():
    from app.infra.test.group import group_test_impl
    params = inspect.signature(group_test_impl).parameters
    assert "pool" in params


async def test_group_module_declares_test_artifact():
    import app.infra.test.group as m
    assert m.ARTIFACT_TYPE == "test"


async def test_group_delegates_to_resolve_group_impl():
    import app.infra.test.group as m
    from app.infra.group.resolve import resolve_group_impl
    # The wrapper imports the canonical resolver into its namespace and uses it.
    assert m.resolve_group_impl is resolve_group_impl
    source = inspect.getsource(m.group_test_impl)
    assert "resolve_group_impl" in source
