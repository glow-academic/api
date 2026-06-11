"""Tests for the shared artifact department-scope clamp (A3 class fix).

``clamp_artifacts_to_actor_scope`` is applied uniformly to every dept-scopable
artifact *search* (list) endpoint so the LIST path can no longer leak rows the
DETAIL ``get`` would 403. These tests pin the allow/deny matrix and the
``total_count`` adjustment that every clamped search relies on.
"""

from dataclasses import dataclass
from uuid import uuid4

from app.infra.artifact_scope import (
    actor_can_access_departments,
    clamp_artifacts_to_actor_scope,
)

_DEPT_A = uuid4()
_DEPT_B = uuid4()


@dataclass
class _Row:
    department_ids: list


class TestActorCanAccessDepartments:
    def test_superadmin_sees_everything(self):
        # role_level 0 → global, even cross-department.
        assert actor_can_access_departments(0, [_DEPT_A], [_DEPT_B]) is True

    def test_deptless_artifact_is_shared(self):
        assert actor_can_access_departments(3, [_DEPT_A], []) is True
        assert actor_can_access_departments(3, None, None) is True

    def test_same_department_allowed(self):
        assert actor_can_access_departments(1, [_DEPT_A], [_DEPT_A]) is True

    def test_cross_department_denied(self):
        assert actor_can_access_departments(1, [_DEPT_A], [_DEPT_B]) is False

    def test_overlap_allowed(self):
        assert actor_can_access_departments(1, [_DEPT_A], [_DEPT_A, _DEPT_B]) is True

    def test_deptless_user_denied_scoped_artifact(self):
        assert actor_can_access_departments(1, None, [_DEPT_B]) is False


class TestClampArtifactsToActorScope:
    def test_cross_dept_actor_loses_rows_and_count(self):
        rows = [_Row([_DEPT_A]), _Row([_DEPT_B]), _Row([])]
        # Actor in DEPT_B: keeps the DEPT_B row + the dept-less row; drops DEPT_A.
        visible, total = clamp_artifacts_to_actor_scope(
            rows, role_level=1, user_department_ids=[_DEPT_B], total_count=3
        )
        assert [r.department_ids for r in visible] == [[_DEPT_B], []]
        assert total == 2  # decremented by the one removed row

    def test_same_dept_actor_keeps_all(self):
        rows = [_Row([_DEPT_A]), _Row([_DEPT_A]), _Row([])]
        visible, total = clamp_artifacts_to_actor_scope(
            rows, role_level=1, user_department_ids=[_DEPT_A], total_count=3
        )
        assert len(visible) == 3
        assert total == 3

    def test_superadmin_keeps_all(self):
        rows = [_Row([_DEPT_A]), _Row([_DEPT_B])]
        visible, total = clamp_artifacts_to_actor_scope(
            rows, role_level=0, user_department_ids=[], total_count=2
        )
        assert len(visible) == 2
        assert total == 2

    def test_count_never_goes_negative(self):
        # total_count of 0 (e.g. setting search carries no count) must clamp to 0.
        rows = [_Row([_DEPT_A])]
        visible, total = clamp_artifacts_to_actor_scope(
            rows, role_level=1, user_department_ids=[_DEPT_B], total_count=0
        )
        assert visible == []
        assert total == 0
