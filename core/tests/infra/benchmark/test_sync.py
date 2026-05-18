"""Tests for benchmark sync."""
import pytest
pytestmark = pytest.mark.asyncio

async def test_sync_benchmark_entries_is_async():
    from app.infra.benchmark.sync import sync_benchmark_entries
    import asyncio
    assert asyncio.iscoroutinefunction(sync_benchmark_entries)

async def test_sync_returns_zero_for_empty_models(monkeypatch):
    from app.infra.benchmark.sync import sync_benchmark_entries
    from unittest.mock import AsyncMock
    from uuid import uuid4
    pool = AsyncMock()
    result = await sync_benchmark_entries(pool, uuid4(), model_ids=[], model_flag_ids=[], model_rubric_ids=[], model_position_ids=[], department_ids=[])
    assert result == 0

async def test_sync_module_uses_entry_tools():
    import app.infra.benchmark.sync as m
    source = open(m.__file__).read()
    assert "create_benchmark" in source
    assert "create_invocation" in source
