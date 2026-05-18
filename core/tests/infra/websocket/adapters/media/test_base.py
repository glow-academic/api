"""Tests for media adapter base — MediaResult, MediaEventEmitter, BaseMediaAdapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.infra.websocket.adapters.media.base import (
    BaseMediaAdapter,
    MediaEventEmitter,
    MediaResult,
)

pytestmark = pytest.mark.asyncio


async def test_media_result_fields():
    """MediaResult carries file_path, mime_type, file_size, upload_id."""
    result = MediaResult(
        file_path="uploads/images/abc.png",
        mime_type="image/png",
        file_size=1024,
        upload_id="upload-123",
    )

    assert result.file_path == "uploads/images/abc.png"
    assert result.mime_type == "image/png"
    assert result.file_size == 1024
    assert result.upload_id == "upload-123"


async def test_media_result_serialization():
    """MediaResult serializes to JSON-compatible dict."""
    result = MediaResult(
        file_path="path/to/video.mp4",
        mime_type="video/mp4",
        file_size=2048,
        upload_id="u1",
    )
    data = result.model_dump()

    assert data["file_path"] == "path/to/video.mp4"
    assert data["mime_type"] == "video/mp4"
    assert isinstance(data["file_size"], int)


async def test_base_media_adapter_is_abstract():
    """BaseMediaAdapter cannot be instantiated directly — generate is abstract."""
    emitter = AsyncMock(spec=MediaEventEmitter)

    with pytest.raises(TypeError):
        BaseMediaAdapter(emitter)


async def test_concrete_adapter_can_be_instantiated():
    """A concrete subclass implementing generate can be instantiated."""

    class ConcreteAdapter(BaseMediaAdapter):
        async def generate(
            self,
            modality: str,
            prompt: str,
            model: str,
            api_key: str,
            **kwargs: Any,
        ) -> MediaResult:
            return MediaResult(
                file_path="test.png",
                mime_type="image/png",
                file_size=100,
                upload_id="u-test",
            )

    emitter = AsyncMock()
    adapter = ConcreteAdapter(emitter)
    assert adapter._emitter is emitter

    result = await adapter.generate("image", "a cat", "dall-e-3", "key")
    assert result.file_path == "test.png"


async def test_media_result_equality():
    """Two MediaResult instances with same values are equal."""
    a = MediaResult(file_path="a.png", mime_type="image/png", file_size=1, upload_id="u")
    b = MediaResult(file_path="a.png", mime_type="image/png", file_size=1, upload_id="u")
    assert a == b
