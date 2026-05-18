"""Tests for eval permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.eval.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.eval.permissions import compute_can_create

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_superadmin_can_edit(self):
        assert (
            compute_can_edit(
                role_level=0,
                role_permissions=[("eval", "update")],
            )
            is True
        )

    async def test_admin_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[],
            )
            is False
        )

    async def test_member_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=3,
                role_permissions=[],
            )
            is False
        )


class TestComputeDisabledReason:
    async def test_returns_none_for_superadmin(self):
        assert (
            compute_disabled_reason(
                role_level=0,
                role_permissions=[("eval", "update")],
            )
            is None
        )

    async def test_returns_reason_for_admin(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[],
        )
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[],
        )
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access(role_level=0, user_department_ids=None, eval_department_ids=[_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access(role_level=3, user_department_ids=[_DEPT], eval_department_ids=None) is True

    async def test_overlap_grants_access(self):
        assert has_access(role_level=1, user_department_ids=[_DEPT], eval_department_ids=[_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access(role_level=1, user_department_ids=[_DEPT], eval_department_ids=[_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_superadmin(self):
        assert (
            compute_can_delete(
                role_level=0,
                role_permissions=[("eval", "delete")],
            )
            is True
        )

    async def test_can_delete_admin_denied(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[],
            )
            is False
        )

    async def test_can_duplicate_granted(self):
        assert (
            compute_can_duplicate(
                role_level=0,
                role_permissions=[("eval", "duplicate")],
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

    async def test_superadmin_can_create(self):
        assert (
            compute_can_create(
                role_level=0,
                role_permissions=[("eval", "create")],
            )
            is True
        )

    async def test_admin_cannot_create(self):
        assert (
            compute_can_create(
                role_level=1,
                role_permissions=[],
            )
            is False
        )

    async def test_can_draft_granted(self):
        assert (
            compute_can_draft(
                role_level=0,
                role_permissions=[("eval", "draft")],
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
