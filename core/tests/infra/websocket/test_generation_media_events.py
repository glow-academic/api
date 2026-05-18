"""Tests for generation_media_events — InternalBusMediaEmitter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infra.websocket.adapters.media.base import MediaResult
from app.infra.websocket.generation_media_events import (
    InternalBusMediaEmitter,
    get_media_emitter,
)

pytestmark = pytest.mark.asyncio


def _make_mock_bus():
    """Create a mock internal bus."""
    bus = AsyncMock()
    bus.emit = AsyncMock()
    return bus


async def test_on_start_emits_correct_event():
    """on_start emits generate_{modality}_start with correct payload."""
    bus = _make_mock_bus()

    with patch(
        "app.infra.websocket.generation_media_events.get_internal_sio",
        return_value=bus,
    ):
        emitter = InternalBusMediaEmitter()
        await emitter.on_start(
            "image",
            sid="sid-1",
            run_id="run-1",
            group_id="group-1",
            artifact_type="persona",
            resource_type="images",
            resource_id="res-1",
            metadata={"key": "val"},
        )

    bus.emit.assert_called_once()
    event_name, payload = bus.emit.call_args[0]
    assert event_name == "persona.generate.image.start"
    assert payload["modality"] == "image"
    assert payload["sid"] == "sid-1"
    assert payload["run_id"] == "run-1"
    assert payload["type"] == "start"


async def test_on_progress_emits_progress_event():
    """on_progress emits generate_{modality}_progress with message."""
    bus = _make_mock_bus()

    with patch(
        "app.infra.websocket.generation_media_events.get_internal_sio",
        return_value=bus,
    ):
        emitter = InternalBusMediaEmitter()
        await emitter.on_progress(
            "video",
            sid="sid-2",
            run_id="run-2",
            group_id=None,
            artifact_type=None,
            resource_type=None,
            resource_id=None,
            message="Processing frame 42/100",
            metadata=None,
        )

    event_name, payload = bus.emit.call_args[0]
    assert event_name == "unknown.generate.video.progress"
    assert payload["message"] == "Processing frame 42/100"
    assert payload["type"] == "progress"


async def test_on_complete_emits_with_media_result():
    """on_complete emits generate_{modality}_complete with file details."""
    bus = _make_mock_bus()
    result = MediaResult(
        file_path="uploads/img/abc.png",
        mime_type="image/png",
        file_size=12345,
        upload_id="upload-1",
    )

    with patch(
        "app.infra.websocket.generation_media_events.get_internal_sio",
        return_value=bus,
    ):
        emitter = InternalBusMediaEmitter()
        await emitter.on_complete(
            "image",
            sid="sid-3",
            run_id="run-3",
            group_id="grp-3",
            artifact_type="persona",
            resource_type="images",
            resource_id="res-3",
            result=result,
            metadata=None,
        )

    event_name, payload = bus.emit.call_args[0]
    assert event_name == "persona.generate.image.complete"
    assert payload["file_path"] == "uploads/img/abc.png"
    assert payload["mime_type"] == "image/png"
    assert payload["file_size"] == 12345
    assert payload["upload_id"] == "upload-1"
    assert payload["event_type"] == "media_complete"


async def test_on_error_emits_error_event():
    """on_error emits generate_{modality}_error with error message."""
    bus = _make_mock_bus()

    with patch(
        "app.infra.websocket.generation_media_events.get_internal_sio",
        return_value=bus,
    ):
        emitter = InternalBusMediaEmitter()
        await emitter.on_error(
            "video",
            sid="sid-4",
            run_id="run-4",
            group_id=None,
            artifact_type=None,
            resource_type=None,
            resource_id=None,
            error_message="Generation failed",
            metadata=None,
        )

    event_name, payload = bus.emit.call_args[0]
    assert event_name == "unknown.generate.video.error"
    assert payload["error_message"] == "Generation failed"
    assert payload["type"] == "error"


async def test_get_media_emitter_returns_emitter():
    """get_media_emitter returns an InternalBusMediaEmitter instance."""
    with patch(
        "app.infra.websocket.generation_media_events.get_internal_sio",
        return_value=_make_mock_bus(),
    ):
        emitter = get_media_emitter()

    assert isinstance(emitter, InternalBusMediaEmitter)
