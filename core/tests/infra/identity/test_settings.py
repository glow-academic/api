"""Tests for identity settings — resolve_settings_theme and resolve_thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.infra.identity.settings import (
    SettingsThemeResult,
    resolve_settings_theme,
    resolve_thresholds,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class _FakeColor:
    type: str
    hex_code: str


@dataclass
class _FakeThreshold:
    type: str
    value: int


@dataclass
class _FakeFlag:
    name: str
    value: bool


@dataclass
class _FakeSettingArtifact:
    color_ids: list
    threshold_ids: list
    flag_ids: list


def _mock_pool():
    """Create a mock pool with async context manager on acquire."""
    pool = MagicMock()
    conn = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool, conn


async def test_resolve_settings_theme_returns_none_when_no_artifacts():
    """Returns None when the setting artifact is not found."""
    pool, conn = _mock_pool()
    redis = AsyncMock()

    with patch(
        "app.infra.identity.settings.get_setting_artifacts",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await resolve_settings_theme(pool, redis, uuid4())

    assert result is None


async def test_resolve_settings_theme_inactive_when_no_active_flag():
    """Returns is_active=False when setting_active flag is missing or False."""
    pool, conn = _mock_pool()
    redis = AsyncMock()

    artifact = _FakeSettingArtifact(
        color_ids=[uuid4()],
        threshold_ids=[],
        flag_ids=[uuid4()],
    )

    with patch(
        "app.infra.identity.settings.get_setting_artifacts",
        new_callable=AsyncMock,
        return_value=[artifact],
    ):
        with patch(
            "app.infra.identity.settings.get_colors",
            new_callable=AsyncMock,
            return_value=[_FakeColor(type="primary", hex_code="#ff0000")],
        ):
            with patch(
                "app.infra.identity.settings.get_flags",
                new_callable=AsyncMock,
                return_value=[_FakeFlag(name="setting_active", value=False)],
            ):
                result = await resolve_settings_theme(pool, redis, uuid4())

    assert result is not None
    assert result.is_active is False
    assert result.light.primary == ""


async def test_resolve_settings_theme_active_with_colors_and_thresholds():
    """Returns full theme when active flag is True."""
    pool, conn = _mock_pool()
    redis = AsyncMock()
    settings_id = uuid4()

    artifact = _FakeSettingArtifact(
        color_ids=[uuid4()],
        threshold_ids=[uuid4()],
        flag_ids=[uuid4()],
    )

    colors = [
        _FakeColor(type="primary", hex_code="#123456"),
        _FakeColor(type="accent", hex_code="#abcdef"),
    ]
    thresholds = [
        _FakeThreshold(type="success", value=90),
        _FakeThreshold(type="warning", value=75),
        _FakeThreshold(type="danger", value=60),
    ]
    flags = [_FakeFlag(name="setting_active", value=True)]

    with patch(
        "app.infra.identity.settings.get_setting_artifacts",
        new_callable=AsyncMock,
        return_value=[artifact],
    ):
        with patch(
            "app.infra.identity.settings.get_colors",
            new_callable=AsyncMock,
            return_value=colors,
        ):
            with patch(
                "app.infra.identity.settings.get_thresholds",
                new_callable=AsyncMock,
                return_value=thresholds,
            ):
                with patch(
                    "app.infra.identity.settings.get_flags",
                    new_callable=AsyncMock,
                    return_value=flags,
                ):
                    result = await resolve_settings_theme(
                        pool, redis, settings_id
                    )

    assert result is not None
    assert result.is_active is True
    assert result.light.primary == "#123456"
    assert result.light.accent == "#abcdef"
    assert result.success_threshold == 90
    assert result.warning_threshold == 75
    assert result.danger_threshold == 60


async def test_resolve_thresholds_returns_defaults_when_no_profile():
    """Returns default thresholds when profile_id is None."""
    pool, conn = _mock_pool()
    redis = AsyncMock()

    result = await resolve_thresholds(pool, redis, profile_id=None)

    assert result == {"success": 85, "warning": 80, "danger": 70}


async def test_resolve_thresholds_returns_defaults_when_no_identity():
    """Returns defaults when resolve_profile_identity_context returns None."""
    pool, conn = _mock_pool()
    redis = AsyncMock()

    with patch(
        "app.infra.profile_identity_context.resolve_profile_identity_context",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await resolve_thresholds(pool, redis, profile_id=uuid4())

    assert result["success"] == 85
    assert result["warning"] == 80
    assert result["danger"] == 70


async def test_settings_theme_result_dataclass():
    """SettingsThemeResult is frozen and has expected fields."""
    from app.utils.settings.theme import ThemePrimitives

    result = SettingsThemeResult(
        is_active=True,
        light=ThemePrimitives(primary="#fff"),
        success_threshold=90,
    )
    assert result.is_active is True
    assert result.light.primary == "#fff"
    assert result.success_threshold == 90
    assert result.warning_threshold is None
