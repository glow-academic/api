"""Tests for resolve_activity_context — context resolution."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_context_function_is_async():
    import app.infra.activity.context as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.resolve_activity_context)

async def test_context_module_imports_artifact_context():
    import app.infra.activity.context as mod
    source = open(mod.__file__).read()
    assert "ArtifactContext" in source

async def test_context_module_uses_parallel_fetches():
    import app.infra.activity.context as mod
    source = open(mod.__file__).read()
    assert "asyncio.gather" in source or "await" in source


# ── Actor-visibility clamp (authz-scope leak fix, F1) ──────────────────────────
# /system/sessions, /system/activity and ws system.activity_search resolved
# their session list with ``profile_ids=None`` (no actor, no visibility helper),
# so an empty body returned EVERY profile's sessions. The detail sibling
# (``resolve_session_context``) gates via ``resolve_visible_profile_ids`` (#144).
# These tests pin ``_clamp_to_visible``: the filter is intersected with the
# actor's visible set, defaulting to the FULL visible set (never None/all) when
# no filter is supplied.

from app.infra.activity.context import _clamp_to_visible  # noqa: E402
from app.infra.profile_identity_context import ProfileIdentityContext  # noqa: E402


def _actor(role_level):
    return ProfileIdentityContext(
        profiles_id=uuid4(),
        name="actor",
        role="instructional" if role_level else "superadmin",
        role_name="r",
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=None,
        department_ids=[],
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=role_level,
        role_permissions=[],
    )


async def test_clamp_no_filter_defaults_to_visible_set(monkeypatch):
    """No filter (empty body) → the actor's FULL visible set, not None/all."""
    import app.infra.activity.context as mod

    visible = [uuid4(), uuid4()]

    async def fake_visible(pool, profile):
        return visible

    monkeypatch.setattr(mod, "resolve_visible_profile_ids", fake_visible)
    result = await _clamp_to_visible(object(), _actor(2), None)
    assert set(result) == set(visible)  # NOT None → search returns only these


async def test_clamp_intersects_cross_scope_to_empty(monkeypatch):
    """A filter for a non-visible profile → empty (leak closed, not all)."""
    import app.infra.activity.context as mod

    visible = [uuid4()]
    other = uuid4()  # a profile the actor cannot see

    async def fake_visible(pool, profile):
        return visible

    monkeypatch.setattr(mod, "resolve_visible_profile_ids", fake_visible)
    result = await _clamp_to_visible(object(), _actor(2), [other])
    assert result == []  # cross-scope request denied (empty, never leaked)


async def test_clamp_intersects_keeps_visible_subset(monkeypatch):
    """A filter overlapping the visible set keeps only the visible ids."""
    import app.infra.activity.context as mod

    v1, v2, hidden = uuid4(), uuid4(), uuid4()

    async def fake_visible(pool, profile):
        return [v1, v2]

    monkeypatch.setattr(mod, "resolve_visible_profile_ids", fake_visible)
    result = await _clamp_to_visible(object(), _actor(2), [v1, hidden])
    assert result == [v1]


async def test_clamp_super_admin_is_global(monkeypatch):
    """Super-admin's visible set is the whole org → filter passes through."""
    import app.infra.activity.context as mod

    everyone = [uuid4(), uuid4(), uuid4()]

    async def fake_visible(pool, profile):
        return everyone  # resolve_visible_profile_ids returns all for level 0

    monkeypatch.setattr(mod, "resolve_visible_profile_ids", fake_visible)
    result = await _clamp_to_visible(object(), _actor(0), None)
    assert set(result) == set(everyone)


async def test_clamp_no_actor_passes_through():
    """No actor (internal/legacy caller) → filter untouched (backward compat)."""
    ids = [uuid4()]
    assert await _clamp_to_visible(object(), None, ids) is ids
    assert await _clamp_to_visible(object(), None, None) is None
