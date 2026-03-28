"""Tests for agent permission helpers — pure business logic functions."""

from uuid import uuid4

import pytest

from app.infra.agent.permissions import (
    compute_can_create,
    compute_can_delete,
    compute_can_draft,
    compute_can_duplicate,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_list_can_edit,
    compute_models_required,
    compute_name_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_models,
    compute_show_name,
    compute_show_prompts,
    get_missing_tools,
    has_access,
)

pytestmark = pytest.mark.asyncio


# ---------- has_access ----------


async def test_has_access_superadmin_always():
    assert has_access("superadmin", None, [uuid4()]) is True


async def test_has_access_no_departments_open_to_all():
    assert has_access("member", [uuid4()], None) is True
    assert has_access("member", [uuid4()], []) is True


async def test_has_access_requires_department_overlap():
    shared = uuid4()
    assert has_access("admin", [shared], [shared]) is True
    assert has_access("admin", [uuid4()], [uuid4()]) is False


async def test_has_access_no_user_departments_denied():
    assert has_access("admin", None, [uuid4()]) is False


# ---------- compute_can_edit ----------


async def test_can_edit_new_mode_no_missing_tools():
    assert compute_can_edit("admin", True, [], agent_id=None) is True


async def test_can_edit_new_mode_with_missing_tools():
    assert compute_can_edit("admin", True, ["name"], agent_id=None) is False


async def test_can_edit_detail_mode_access_and_tools():
    agent_id = uuid4()
    assert compute_can_edit("admin", True, [], agent_id=agent_id) is True
    assert compute_can_edit("admin", False, [], agent_id=agent_id) is False


# ---------- compute_disabled_reason ----------


async def test_disabled_reason_none_when_allowed():
    assert compute_disabled_reason("admin", True, [], agent_id=uuid4()) is None


async def test_disabled_reason_no_access():
    result = compute_disabled_reason("admin", False, [], agent_id=uuid4())
    assert result is not None
    assert "access" in result.lower()


async def test_disabled_reason_missing_tools():
    result = compute_disabled_reason("admin", True, ["name", "model"])
    assert result is not None
    assert "name" in result and "model" in result


# ---------- compute_list_can_edit ----------


async def test_list_can_edit_admin():
    assert compute_list_can_edit("admin", ["dept"], active_settings_count=0) is True


async def test_list_can_edit_blocked_by_settings():
    assert compute_list_can_edit("admin", ["dept"], active_settings_count=1) is False


async def test_list_can_edit_default_agent_requires_superadmin():
    assert compute_list_can_edit("admin", None, active_settings_count=0) is False
    assert compute_list_can_edit("superadmin", None, active_settings_count=0) is True


# ---------- compute_can_delete ----------


async def test_can_delete_admin_no_settings():
    assert compute_can_delete("admin", active_settings_count=0) is True


async def test_can_delete_blocked_by_settings():
    assert compute_can_delete("admin", active_settings_count=2) is False


async def test_can_delete_denied_for_member():
    assert compute_can_delete("member", active_settings_count=0) is False


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
    assert compute_can_create("admin", []) is False


async def test_can_create_superadmin_no_departments():
    assert compute_can_create("superadmin", None) is True


async def test_can_create_denied_for_member():
    assert compute_can_create("member", [str(uuid4())]) is False


# ---------- compute_can_draft ----------


async def test_can_draft_admin():
    assert compute_can_draft("admin") is True


async def test_can_draft_denied_for_member():
    assert compute_can_draft("member") is False


# ---------- get_missing_tools ----------


async def test_get_missing_tools_none_missing():
    result = get_missing_tools(
        names_has_tools=True,
        models_has_tools=True,
        prompts_has_tools=True,
        instructions_has_tools=True,
    )
    assert result == []


async def test_get_missing_tools_all_missing():
    result = get_missing_tools(
        names_has_tools=False,
        models_has_tools=False,
        prompts_has_tools=False,
        instructions_has_tools=False,
    )
    assert "name" in result
    assert "model" in result
    assert "prompt" in result
    assert "instructions" in result


async def test_get_missing_tools_partial():
    result = get_missing_tools(
        names_has_tools=True,
        models_has_tools=False,
        prompts_has_tools=True,
        instructions_has_tools=False,
    )
    assert "model" in result
    assert "instructions" in result
    assert "name" not in result


# ---------- show flags ----------


async def test_show_name_depends_on_tools():
    assert compute_show_name(True) is True
    assert compute_show_name(False) is False


async def test_show_description_depends_on_tools():
    assert compute_show_description(True) is True
    assert compute_show_description(False) is False


async def test_show_flag_always_true():
    assert compute_show_flag() is True


async def test_show_models_depends_on_tools():
    assert compute_show_models(True) is True
    assert compute_show_models(False) is False


async def test_show_prompts_depends_on_tools():
    assert compute_show_prompts(True) is True
    assert compute_show_prompts(False) is False


async def test_show_departments_depends_on_tools_and_has():
    assert compute_show_departments(True, True) is True
    assert compute_show_departments(False, True) is False
    assert compute_show_departments(True, False) is False


# ---------- required flags ----------


async def test_required_flags():
    assert compute_name_required() is True
    assert compute_description_required() is False
    assert compute_models_required() is True
    assert compute_flag_required() is False
    assert compute_departments_required(show_departments=True) is True
    assert compute_departments_required(show_departments=False) is False
