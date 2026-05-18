"""Tests for generation_dispatch — role-to-handler mapping."""

import pytest

from app.infra.agents.utils.generation_dispatch import get_generation_handler

pytestmark = pytest.mark.asyncio


async def test_text_roles_return_text():
    for role in ["scenario", "document", "simulation", "grade", "hint", "classify",
                 "member", "prompt", "rubric", "title", "audio"]:
        assert get_generation_handler(role) == "text", f"Expected 'text' for role '{role}'"


async def test_image_role_returns_image():
    assert get_generation_handler("image") == "image"


async def test_video_role_returns_video():
    assert get_generation_handler("video") == "video"


async def test_voice_role_returns_audio():
    assert get_generation_handler("voice") == "audio"


async def test_unknown_role_raises_value_error():
    with pytest.raises(ValueError, match="Unknown agent role"):
        get_generation_handler("nonexistent_role")


async def test_empty_string_raises_value_error():
    with pytest.raises(ValueError, match="Unknown agent role"):
        get_generation_handler("")
