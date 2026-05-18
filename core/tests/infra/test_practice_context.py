"""Tests for practice_context."""
import pytest
pytestmark = pytest.mark.asyncio

async def test_resolve_practice_context_is_async():
    from app.infra.practice_context import resolve_practice_context
    import asyncio
    assert asyncio.iscoroutinefunction(resolve_practice_context)

async def test_module_uses_artifact_context():
    import app.infra.practice_context as m
    source = open(m.__file__).read()
    assert "ArtifactContext" in source

async def test_module_uses_parallel_fetches():
    import app.infra.practice_context as m
    source = open(m.__file__).read()
    assert "asyncio.gather" in source
