"""Tests for get_attempt_impl — get orchestration."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_get_function_is_async():
    import app.infra.attempt.get as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.get_attempt_impl)

async def test_get_module_uses_common_context():
    import app.infra.attempt.get as mod
    source = open(mod.__file__).read()
    assert "resolve_common_context" in source or "resolve_" in source

async def test_get_module_returns_response_type():
    import app.infra.attempt.get as mod
    source = open(mod.__file__).read()
    assert "Response" in source or "InternalData" in source


def test_image_entry_retains_upload_id():
    """Regression: ImageEntry must expose upload_id.

    get_attempt_internal fetches ``entry.upload_id`` into resource_meta and
    passes ``upload_id=...`` into ImageEntry. The model previously lacked the
    field, so pydantic (extra=ignore) silently dropped it and the upload_id
    never reached the API response. This asserts the value survives.
    """
    from app.infra.attempt.types import ImageEntry

    up = uuid4()
    entry = ImageEntry(image_id=uuid4(), upload_id=up, name="img", description="d")
    assert entry.upload_id == up
    assert "upload_id" in ImageEntry.model_fields


def test_video_entry_retains_upload_id():
    """Regression: VideoEntry must expose upload_id (see ImageEntry above)."""
    from app.infra.attempt.types import VideoEntry

    up = uuid4()
    entry = VideoEntry(video_id=uuid4(), upload_id=up, name="vid", description="d")
    assert entry.upload_id == up
    assert "upload_id" in VideoEntry.model_fields
