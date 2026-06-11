"""A4 class fix: dept-aware ``compute_can_delete`` / ``compute_can_duplicate``.

The dept-scoped siblings (eval/delete, scenario+cohort+document+persona+
simulation delete/duplicate) already refuse a cross-department actor; the same
gate was missing on agent (delete+duplicate), eval (duplicate), and
field/model/parameter/provider/rubric/setting (delete+duplicate). These tests
pin the allow/deny matrix uniformly across every fixed function.

Matrix per function:
  * cross-dept actor (has permission, wrong dept)  → DENY
  * in-dept actor (has permission, right dept)      → ALLOW
  * super-admin (role_level 0, wrong dept)          → ALLOW (bypass)
  * legacy caller (no user_department_ids)          → ALLOW (perm-only, unchanged)
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


# (artifact, perm_resource, delete_extra_kwargs)
# ``delete_extra_kwargs`` supplies each can_delete's required usage-count arg
# (named differently per artifact) so only the dept gate decides the outcome.
_DELETE_CASES = [
    ("agent", "agent", {"active_settings_count": 0}),
    ("field", "field", {"active_parameter_count": 0}),
    ("model", "model", {"active_agent_count": 0}),
    ("parameter", "parameter", {"active_scenario_count": 0}),
    ("provider", "provider", {"active_model_count": 0}),
    ("rubric", "rubric", {"active_simulation_count": 0}),
    ("setting", "setting", {}),
]

# eval/delete already dept-aware (kept fixed); included for regression.
_DELETE_CASES_REGRESSION = [
    ("eval", "eval", {}),
]

_DUPLICATE_CASES = [
    ("agent", "agent"),
    ("eval", "eval"),
    ("field", "field"),
    ("model", "model"),
    ("parameter", "parameter"),
    ("provider", "provider"),
    ("rubric", "rubric"),
    ("setting", "setting"),
]


def _import(artifact, fn_name):
    mod = __import__(
        f"app.infra.{artifact}.permissions", fromlist=[fn_name]
    )
    return getattr(mod, fn_name)


@pytest.mark.parametrize(
    "artifact,resource,extra", _DELETE_CASES + _DELETE_CASES_REGRESSION
)
class TestCanDeleteDeptScope:
    def _call(self, artifact, resource, extra, **dept):
        fn = _import(artifact, "compute_can_delete")
        return fn(
            role_level=dept.pop("role_level", 1),
            role_permissions=[(resource, "delete")],
            **{f"{artifact}_department_ids": dept.pop("art", [_DEPT])},
            **extra,
            **dept,
        )

    async def test_cross_department_denied(self, artifact, resource, extra):
        assert (
            self._call(artifact, resource, extra, user_department_ids=[_OTHER])
            is False
        )

    async def test_in_department_allowed(self, artifact, resource, extra):
        assert (
            self._call(artifact, resource, extra, user_department_ids=[_DEPT])
            is True
        )

    async def test_superadmin_bypasses_scope(self, artifact, resource, extra):
        assert (
            self._call(
                artifact,
                resource,
                extra,
                role_level=0,
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_legacy_caller_permission_only(self, artifact, resource, extra):
        # Omitting user_department_ids preserves historical permission-only
        # behaviour (list/get rendering callers rely on this).
        assert self._call(artifact, resource, extra) is True


@pytest.mark.parametrize("artifact,resource", _DUPLICATE_CASES)
class TestCanDuplicateDeptScope:
    def _call(self, artifact, resource, **dept):
        fn = _import(artifact, "compute_can_duplicate")
        return fn(
            role_level=dept.pop("role_level", 1),
            role_permissions=[(resource, "duplicate")],
            **{f"{artifact}_department_ids": dept.pop("art", [_DEPT])},
            **dept,
        )

    async def test_cross_department_denied(self, artifact, resource):
        assert self._call(artifact, resource, user_department_ids=[_OTHER]) is False

    async def test_in_department_allowed(self, artifact, resource):
        assert self._call(artifact, resource, user_department_ids=[_DEPT]) is True

    async def test_superadmin_bypasses_scope(self, artifact, resource):
        assert (
            self._call(
                artifact, resource, role_level=0, user_department_ids=[_OTHER]
            )
            is True
        )

    async def test_legacy_caller_permission_only(self, artifact, resource):
        assert self._call(artifact, resource) is True

    async def test_no_permission_denied(self, artifact, resource):
        fn = _import(artifact, "compute_can_duplicate")
        assert (
            fn(
                role_level=1,
                role_permissions=[],
                **{f"{artifact}_department_ids": [_DEPT]},
                user_department_ids=[_DEPT],
            )
            is False
        )
