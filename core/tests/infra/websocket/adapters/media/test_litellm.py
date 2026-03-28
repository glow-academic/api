"""Tests for LitellmMediaAdapter — image/video format detection and structure."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.infra.websocket.adapters.media.litellm import LitellmMediaAdapter

pytestmark = pytest.mark.asyncio


async def test_detect_image_format_png():
    """PNG magic bytes are detected correctly."""
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_image_format(png_header)

    assert ext == ".png"
    assert mime == "image/png"


async def test_detect_image_format_jpeg():
    """JPEG magic bytes are detected correctly."""
    jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_image_format(jpeg_header)

    assert ext == ".jpg"
    assert mime == "image/jpeg"


async def test_detect_image_format_gif():
    """GIF magic bytes are detected correctly."""
    gif_header = b"GIF89a" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_image_format(gif_header)

    assert ext == ".gif"
    assert mime == "image/gif"


async def test_detect_image_format_webp():
    """WebP magic bytes are detected correctly."""
    webp_header = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_image_format(webp_header)

    assert ext == ".webp"
    assert mime == "image/webp"


async def test_detect_image_format_unknown_defaults_to_png():
    """Unknown image format defaults to PNG."""
    unknown = b"\x00\x00\x00\x00" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_image_format(unknown)

    assert ext == ".png"
    assert mime == "image/png"


async def test_detect_video_format_mp4():
    """MP4 magic bytes (ftyp) are detected correctly."""
    mp4_header = b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_video_format(mp4_header)

    assert ext == ".mp4"
    assert mime == "video/mp4"


async def test_detect_video_format_webm():
    """WebM magic bytes (EBML) are detected correctly."""
    webm_header = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_video_format(webm_header)

    assert ext == ".webm"
    assert mime == "video/webm"


async def test_detect_video_format_unknown_defaults_to_mp4():
    """Unknown video format defaults to MP4."""
    unknown = b"\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
    ext, mime = LitellmMediaAdapter._detect_video_format(unknown)

    assert ext == ".mp4"
    assert mime == "video/mp4"


async def test_generate_raises_for_unsupported_modality():
    """generate raises ValueError for unsupported modality."""
    emitter = AsyncMock()
    adapter = LitellmMediaAdapter(emitter)

    with pytest.raises(ValueError, match="Unsupported modality"):
        await adapter.generate(
            "3d-model",
            prompt="a cube",
            model="test-model",
            api_key="key",
            context={"sid": "s1", "run_id": "r1"},
        )

    # Error emitter should have been called
    emitter.on_error.assert_called_once()
