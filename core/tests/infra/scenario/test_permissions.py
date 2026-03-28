"""Tests for scenario permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.scenario.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.scenario.permissions import compute_can_create

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_admin_with_matching_departments_can_edit(self):
        assert compute_can_edit("admin", [_DEPT], 0, [_DEPT]) is True

    async def test_superadmin_can_edit_default(self):
        assert compute_can_edit("superadmin", None, 0) is True

    async def test_admin_cannot_edit_default(self):
        assert compute_can_edit("admin", None, 0) is False

    async def test_member_cannot_edit(self):
        assert compute_can_edit("member", [_DEPT], 0) is False

    async def test_blocked_by_usage(self):
        assert compute_can_edit("admin", [_DEPT], 1) is False


class TestComputeDisabledReason:
    async def test_returns_none_when_allowed(self):
        assert compute_disabled_reason("admin", [_DEPT], 0, [_DEPT]) is None

    async def test_returns_reason_for_default(self):
        reason = compute_disabled_reason("admin", None, 0)
        assert reason is not None
        assert "default" in reason.lower()

    async def test_returns_reason_for_usage(self):
        reason = compute_disabled_reason("admin", [_DEPT], 1)
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason("member", [_DEPT], 0)
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access("superadmin", None, [_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access("member", [_DEPT], None) is True

    async def test_overlap_grants_access(self):
        assert has_access("admin", [_DEPT], [_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access("admin", [_DEPT], [_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_granted(self):
        assert compute_can_delete("admin", [_DEPT], 0) is True

    async def test_can_delete_blocked_by_usage(self):
        assert compute_can_delete("admin", [_DEPT], 1) is False

    async def test_can_duplicate_granted(self):
        assert compute_can_duplicate("admin") is True

    async def test_can_duplicate_denied(self):
        assert compute_can_duplicate("member") is False

    async def test_can_create_with_departments(self):
        assert compute_can_create("admin", [_DEPT]) is True

    async def test_cannot_create_without_department(self):
        assert compute_can_create("admin", None) is False

    async def test_member_cannot_create(self):
        assert compute_can_create("member", [_DEPT]) is False

    async def test_can_draft_granted(self):
        assert compute_can_draft("admin") is True

    async def test_can_draft_denied(self):
        assert compute_can_draft("member") is False
