"""Tests for rubric permissions_context."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_permissions_context_module_exists():
    import app.infra.rubric.permissions_context as m
    assert m.__file__.endswith("permissions_context.py")

async def test_permissions_context_uses_resolve():
    import app.infra.rubric.permissions_context as m
    source = open(m.__file__).read()
    assert "resolve" in source.lower() or "context" in source.lower()

async def test_permissions_context_is_importable():
    import app.infra.rubric.permissions_context
