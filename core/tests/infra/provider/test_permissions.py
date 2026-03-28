"""Tests for provider permission helpers — pure business logic functions."""

from uuid import uuid4

import pytest

from app.infra.provider.permissions import (
    compute_can_create,
    compute_can_delete,
    compute_can_draft,
    compute_can_duplicate,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_value_required,
    get_missing_tools,
    has_access,
)

pytestmark = pytest.mark.asyncio


# ---------- has_access ----------


async def test_has_access_superadmin_always():
    assert has_access("superadmin", None, [uuid4()]) is True


async def test_has_access_default_provider_open_to_all():
    assert has_access("member", [uuid4()], None) is True
    assert has_access("member", [uuid4()], []) is True


async def test_has_access_requires_department_overlap():
    shared = uuid4()
    assert has_access("admin", [shared], [shared]) is True
    assert has_access("admin", [uuid4()], [uuid4()]) is False


async def test_has_access_no_user_departments():
    assert has_access("admin", None, [uuid4()]) is False


# ---------- compute_can_edit ----------


async def test_can_edit_admin_no_active_models():
    assert compute_can_edit("admin", ["dept"], active_model_count=0) is True


async def test_can_edit_blocked_by_active_models():
    assert compute_can_edit("admin", ["dept"], active_model_count=1) is False


async def test_can_edit_default_provider_needs_superadmin():
    assert compute_can_edit("admin", None, active_model_count=0) is False
    assert compute_can_edit("superadmin", None, active_model_count=0) is True


async def test_can_edit_denied_for_member():
    assert compute_can_edit("member", ["dept"], active_model_count=0) is False


async def test_can_edit_department_subset_check():
    dept1 = uuid4()
    dept2 = uuid4()
    # Admin owns dept1, provider has dept1+dept2 => denied (not subset)
    assert (
        compute_can_edit(
            "admin", [dept1, dept2], active_model_count=0, user_department_ids=[dept1]
        )
        is False
    )
    # Admin owns both => allowed
    assert (
        compute_can_edit(
            "admin",
            [dept1, dept2],
            active_model_count=0,
            user_department_ids=[dept1, dept2],
        )
        is True
    )


# ---------- compute_disabled_reason ----------


async def test_disabled_reason_none_when_allowed():
    result = compute_disabled_reason("admin", ["dept"], active_model_count=0)
    assert result is None


async def test_disabled_reason_default_provider():
    result = compute_disabled_reason("admin", None, active_model_count=0)
    assert result is not None
    assert "default provider" in result.lower()


async def test_disabled_reason_active_models():
    result = compute_disabled_reason("admin", ["dept"], active_model_count=1)
    assert result is not None
    assert "models" in result.lower()


# ---------- compute_can_delete ----------


async def test_can_delete_admin_no_models():
    assert compute_can_delete("admin", ["dept"], active_model_count=0) is True


async def test_can_delete_blocked_by_models():
    assert compute_can_delete("admin", ["dept"], active_model_count=1) is False


async def test_can_delete_default_provider_denied():
    assert compute_can_delete("admin", None, active_model_count=0) is False
    assert compute_can_delete("superadmin", None, active_model_count=0) is True


# ---------- compute_can_duplicate ----------


async def test_can_duplicate_admin():
    assert compute_can_duplicate("admin") is True


async def test_can_duplicate_denied_for_member():
    assert compute_can_duplicate("member") is False


# ---------- compute_can_create ----------


async def test_can_create_admin_with_departments():
    assert compute_can_create("admin", [str(uuid4())]) is True


async def test_can_create_non_superadmin_no_departments():
    assert compute_can_create("admin", None) is False


async def test_can_create_denied_for_member():
    assert compute_can_create("member", [str(uuid4())]) is False


# ---------- compute_can_draft ----------


async def test_can_draft_admin():
    assert compute_can_draft("admin") is True


async def test_can_draft_denied_for_member():
    assert compute_can_draft("member") is False


# ---------- get_missing_tools ----------


async def test_get_missing_tools_none_missing():
    result = get_missing_tools(names_has_tools=True, flags_has_tools=True)
    assert result == []


async def test_get_missing_tools_all_missing():
    result = get_missing_tools(names_has_tools=False, flags_has_tools=False)
    assert "name" in result
    assert "flag" in result


# ---------- show/required flags ----------


async def test_show_name_depends_on_tools():
    assert compute_show_name(True) is True
    assert compute_show_name(False) is False


async def test_show_description_always_true():
    assert compute_show_description() is True


async def test_show_flag_always_true():
    assert compute_show_flag() is True


async def test_show_departments_depends_on_count():
    assert compute_show_departments(3) is True
    assert compute_show_departments(0) is False


async def test_required_flags():
    assert compute_name_required() is True
    assert compute_description_required() is False
    assert compute_flag_required() is False
    assert compute_departments_required() is False
    assert compute_value_required() is True
