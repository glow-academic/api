"""Tests for auth permission helpers — pure business logic functions."""

from uuid import uuid4

import pytest

from app.infra.auth.permissions import (
    compute_can_create,
    compute_can_delete,
    compute_can_draft,
    compute_can_duplicate,
    compute_can_edit,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_protocols_required,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_protocols,
    compute_show_slugs,
    compute_slugs_required,
    has_access,
)

pytestmark = pytest.mark.asyncio

# Permission tuples for auth operations
_AUTH_UPDATE = [("auth", "update")]
_AUTH_DELETE = [("auth", "delete")]
_AUTH_DUPLICATE = [("auth", "duplicate")]
_AUTH_CREATE = [("auth", "create")]
_AUTH_DRAFT = [("auth", "draft")]
_NO_PERMS = []


# ---------- compute_can_edit ----------


async def test_can_edit_superadmin_no_active_settings():
    assert compute_can_edit(role_level=0, role_permissions=_AUTH_UPDATE, active_settings_count=0) is True


async def test_can_edit_blocked_by_active_settings():
    assert compute_can_edit(role_level=0, role_permissions=_AUTH_UPDATE, active_settings_count=3) is False


async def test_can_edit_denied_for_non_superadmin():
    assert compute_can_edit(role_level=1, role_permissions=_NO_PERMS, active_settings_count=0) is False
    assert compute_can_edit(role_level=3, role_permissions=_NO_PERMS, active_settings_count=0) is False
    assert compute_can_edit(role_level=99, role_permissions=_NO_PERMS, active_settings_count=0) is False


# ---------- compute_disabled_reason ----------


async def test_disabled_reason_none_for_superadmin():
    result = compute_disabled_reason(role_permissions=_AUTH_UPDATE, active_settings_count=0)
    assert result is None


async def test_disabled_reason_active_settings():
    result = compute_disabled_reason(role_permissions=_AUTH_UPDATE, active_settings_count=1)
    assert result is not None
    assert "linked to settings" in result


async def test_disabled_reason_non_superadmin():
    result = compute_disabled_reason(role_permissions=_NO_PERMS, active_settings_count=0)
    assert result is not None
    assert "cannot be edited" in result


# ---------- compute_can_delete ----------


async def test_can_delete_superadmin_no_settings():
    assert compute_can_delete(role_level=0, role_permissions=_AUTH_DELETE, active_settings_count=0) is True


async def test_can_delete_blocked_by_active_settings():
    assert compute_can_delete(role_level=0, role_permissions=_AUTH_DELETE, active_settings_count=1) is False


async def test_can_delete_denied_for_admin():
    assert compute_can_delete(role_level=1, role_permissions=_NO_PERMS, active_settings_count=0) is False


# ---------- compute_can_duplicate ----------


async def test_can_duplicate_superadmin():
    assert compute_can_duplicate(role_level=0, role_permissions=_AUTH_DUPLICATE) is True


async def test_can_duplicate_denied_for_admin():
    assert compute_can_duplicate(role_level=1, role_permissions=_NO_PERMS) is False


async def test_can_duplicate_denied_for_none():
    assert compute_can_duplicate(role_level=99, role_permissions=_NO_PERMS) is False


# ---------- compute_can_create ----------


async def test_can_create_superadmin():
    assert compute_can_create(role_level=0, role_permissions=_AUTH_CREATE) is True


async def test_can_create_denied_for_admin():
    assert compute_can_create(role_level=1, role_permissions=_NO_PERMS) is False


# ---------- compute_can_draft ----------


async def test_can_draft_superadmin():
    assert compute_can_draft(role_level=0, role_permissions=_AUTH_DRAFT) is True


async def test_can_draft_denied_for_member():
    assert compute_can_draft(role_level=3, role_permissions=_NO_PERMS) is False


# ---------- has_access ----------


async def test_has_access_authenticated_profile():
    assert has_access(role_level=0) is True
    assert has_access(role_level=1) is True
    assert has_access(role_level=3) is True


async def test_has_access_denied_for_none():
    assert has_access(role_level=None) is False


# ---------- show flags ----------


async def test_show_name_depends_on_tools():
    assert compute_show_name(names_has_tools=True) is True
    assert compute_show_name(names_has_tools=False) is False


async def test_show_description_always_true():
    assert compute_show_description() is True


async def test_show_flag_always_true():
    assert compute_show_flag() is True


async def test_show_protocols_requires_tools_and_count():
    assert compute_show_protocols(protocols_has_tools=True, protocols_count=5) is True
    assert compute_show_protocols(protocols_has_tools=False, protocols_count=5) is False
    assert compute_show_protocols(protocols_has_tools=True, protocols_count=0) is False


async def test_show_slugs_requires_tools_and_count():
    assert compute_show_slugs(slugs_has_tools=True, slugs_count=3) is True
    assert compute_show_slugs(slugs_has_tools=False, slugs_count=3) is False
    assert compute_show_slugs(slugs_has_tools=True, slugs_count=0) is False


# ---------- required flags ----------


async def test_name_required():
    assert compute_name_required() is True


async def test_description_not_required():
    assert compute_description_required() is False


async def test_flag_not_required():
    assert compute_flag_required() is False


async def test_protocols_required_when_shown():
    assert compute_protocols_required(show_protocols=True) is True
    assert compute_protocols_required(show_protocols=False) is False


async def test_slugs_required_when_shown():
    assert compute_slugs_required(show_slugs=True) is True
    assert compute_slugs_required(show_slugs=False) is False
