"""Tests for document permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.document.permissions import (
    DOCUMENT_RESOURCES,
    compute_can_create,
    compute_can_delete,
    compute_can_draft,
    compute_can_duplicate,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_fields_required,
    compute_flag_required,
    compute_name_required,
    compute_show_departments,
    compute_show_description,
    compute_show_fields,
    compute_show_flag,
    compute_show_name,
    compute_show_uploads,
    compute_uploads_required,
    get_missing_tools,
    has_access,
)

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_admin_with_matching_departments_can_edit(self):
        assert compute_can_edit("admin", [_DEPT], 0, [_DEPT]) is True

    async def test_superadmin_can_edit_default_document(self):
        assert compute_can_edit("superadmin", None, 0) is True

    async def test_admin_cannot_edit_default_document(self):
        assert compute_can_edit("admin", None, 0) is False

    async def test_member_cannot_edit(self):
        assert compute_can_edit("member", [_DEPT], 0) is False

    async def test_blocked_by_active_scenario(self):
        assert compute_can_edit("admin", [_DEPT], 1) is False

    async def test_admin_blocked_when_missing_department(self):
        assert compute_can_edit("admin", [_DEPT, _OTHER], 0, [_DEPT]) is False


class TestComputeDisabledReason:
    async def test_returns_none_when_allowed(self):
        assert compute_disabled_reason("admin", [_DEPT], 0, [_DEPT]) is None

    async def test_returns_reason_for_default_document(self):
        reason = compute_disabled_reason("admin", None, 0)
        assert reason is not None
        assert "default" in reason.lower()

    async def test_returns_reason_for_active_scenario(self):
        reason = compute_disabled_reason("admin", [_DEPT], 1)
        assert reason is not None
        assert "scenario" in reason.lower()

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason("member", [_DEPT], 0)
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access("superadmin", None, [_DEPT]) is True

    async def test_no_departments_means_accessible(self):
        assert has_access("member", [_DEPT], None) is True

    async def test_overlapping_department_grants_access(self):
        assert has_access("admin", [_DEPT], [_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access("admin", [_DEPT], [_OTHER]) is False

    async def test_no_user_departments_denies_access(self):
        assert has_access("admin", None, [_DEPT]) is False


class TestCanDelete:
    async def test_admin_can_delete_with_no_usage(self):
        assert compute_can_delete("admin", [_DEPT], 0) is True

    async def test_blocked_by_active_scenario(self):
        assert compute_can_delete("admin", [_DEPT], 1) is False

    async def test_member_cannot_delete(self):
        assert compute_can_delete("member", [_DEPT], 0) is False

    async def test_default_document_only_superadmin(self):
        assert compute_can_delete("admin", None, 0) is False
        assert compute_can_delete("superadmin", None, 0) is True


class TestCanCreateAndDuplicate:
    async def test_admin_can_create_with_departments(self):
        assert compute_can_create("admin", [_DEPT]) is True

    async def test_admin_cannot_create_general(self):
        assert compute_can_create("admin", None) is False

    async def test_superadmin_can_create_general(self):
        assert compute_can_create("superadmin", None) is True

    async def test_member_cannot_create(self):
        assert compute_can_create("member", [_DEPT]) is False

    async def test_admin_can_duplicate(self):
        assert compute_can_duplicate("admin") is True

    async def test_member_cannot_duplicate(self):
        assert compute_can_duplicate("member") is False


class TestCanDraft:
    async def test_admin_can_draft(self):
        assert compute_can_draft("admin") is True

    async def test_member_cannot_draft(self):
        assert compute_can_draft("member") is False


class TestShowAndRequiredFlags:
    async def test_show_name_follows_tools(self):
        assert compute_show_name(True) is True
        assert compute_show_name(False) is False

    async def test_description_always_shown(self):
        assert compute_show_description() is True

    async def test_flag_always_shown(self):
        assert compute_show_flag() is True

    async def test_show_departments_requires_count(self):
        assert compute_show_departments(0) is False
        assert compute_show_departments(3) is True

    async def test_show_fields_requires_count(self):
        assert compute_show_fields(0) is False
        assert compute_show_fields(1) is True

    async def test_uploads_always_shown(self):
        assert compute_show_uploads() is True

    async def test_name_required(self):
        assert compute_name_required() is True

    async def test_description_not_required(self):
        assert compute_description_required() is False

    async def test_flag_not_required(self):
        assert compute_flag_required() is False

    async def test_departments_required(self):
        assert compute_departments_required() is True

    async def test_fields_required(self):
        assert compute_fields_required() is True

    async def test_uploads_not_required(self):
        assert compute_uploads_required() is False


class TestGetMissingTools:
    async def test_returns_empty_when_all_present(self):
        result = get_missing_tools(
            names_has_tools=True,
            show_departments=True,
            departments_has_tools=True,
            show_fields=True,
            fields_has_tools=True,
            show_uploads=True,
            uploads_has_tools=True,
        )
        assert result == []

    async def test_reports_missing_name(self):
        result = get_missing_tools(
            names_has_tools=False,
            show_departments=False,
            departments_has_tools=False,
            show_fields=False,
            fields_has_tools=False,
            show_uploads=False,
            uploads_has_tools=False,
        )
        assert "name" in result

    async def test_skips_hidden_sections(self):
        result = get_missing_tools(
            names_has_tools=True,
            show_departments=False,
            departments_has_tools=False,
            show_fields=False,
            fields_has_tools=False,
            show_uploads=False,
            uploads_has_tools=False,
        )
        assert result == []


class TestResourceConstants:
    async def test_document_resources_contains_expected(self):
        assert "names" in DOCUMENT_RESOURCES
        assert "descriptions" in DOCUMENT_RESOURCES
        assert "departments" in DOCUMENT_RESOURCES
        assert "fields" in DOCUMENT_RESOURCES
