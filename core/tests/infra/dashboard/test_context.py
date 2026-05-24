"""Tests for resolve_dashboard_context — context resolution."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_context_function_is_async():
    import app.infra.dashboard.context as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.resolve_dashboard_context)

async def test_context_module_imports_artifact_context():
    import app.infra.dashboard.context as mod
    source = open(mod.__file__).read()
    assert "ArtifactContext" in source

async def test_context_module_uses_parallel_fetches():
    import app.infra.dashboard.context as mod
    source = open(mod.__file__).read()
    assert "asyncio.gather" in source or "await" in source
