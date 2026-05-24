"""Tests for setting permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.setting.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

_DEPT = uuid4()
_OTHER = uuid4()

# Role levels: superadmin=0, admin=1, member=3
# Permission tuples use ("setting", "<operation>")


class TestComputeCanEdit:
    async def test_admin_with_departments_can_edit(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("setting", "update")],
                setting_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_superadmin_can_edit_default(self):
        assert (
            compute_can_edit(
                role_level=0,
                role_permissions=[("setting", "update")],
                setting_department_ids=None,
            )
            is True
        )

    async def test_member_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=3,
                role_permissions=[],
                setting_department_ids=[_DEPT],
            )
            is False
        )


class TestComputeDisabledReason:
    async def test_returns_none_when_allowed(self):
        assert (
            compute_disabled_reason(
                role_level=1,
                role_permissions=[("setting", "update")],
                setting_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is None
        )

    async def test_returns_reason_for_default(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[("setting", "update")],
            setting_department_ids=None,
        )
        assert reason is not None
        assert "default" in reason.lower()

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(
            role_level=3,
            role_permissions=[],
            setting_department_ids=[_DEPT],
        )
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access(0, [], [_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access(3, [_DEPT], []) is True

    async def test_overlap_grants_access(self):
        assert has_access(1, [_DEPT], [_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access(1, [_DEPT], [_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_granted(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("setting", "delete")],
                setting_department_ids=[_DEPT],
            )
            is True
        )

    async def test_can_delete_default_blocked(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("setting", "delete")],
                setting_department_ids=None,
            )
            is False
        )

    async def test_can_duplicate_granted(self):
        assert (
            compute_can_duplicate(
                role_level=1,
                role_permissions=[("setting", "duplicate")],
            )
            is True
        )

    async def test_can_duplicate_denied(self):
        assert (
            compute_can_duplicate(
                role_level=3,
                role_permissions=[],
            )
            is False
        )

    async def test_can_draft_granted(self):
        assert (
            compute_can_draft(
                role_level=1,
                role_permissions=[("setting", "draft")],
            )
            is True
        )

    async def test_can_draft_denied(self):
        assert (
            compute_can_draft(
                role_level=3,
                role_permissions=[],
            )
            is False
        )
