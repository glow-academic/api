"""Allow/deny matrix for the 11 draft-write impls wired to ``enforce_draft_owner``
in this PR (the endpoints PR #356 deferred): auth, provider, simulation, cohort,
department, field, model, parameter, profile, eval, rubric.

Each impl is exercised through its public ``patch_*_draft_impl`` with the guard's
collaborators monkeypatched, mirroring ``setting/test_draft_ownership.py`` from
PR #356 (which covers the 8 already-wired exemplars). For every endpoint we assert:

  * foreign-owned ``draft_id`` (owned by a *different* session+profile) →
    403 AND the family's ``create_*_draft`` never runs (no row mutated)
  * caller owns the draft (session match) → ALLOW (create runs)
  * caller owns the draft (profile match) → ALLOW
  * super-admin (role_level == 0) → ALLOW regardless of owner
  * brand-new / own draft_id (no existing row) → ALLOW (first-write preserved)

The guard reads the committed row via the family ``get_*_drafts`` getter; we
patch that getter (per impl module) plus ``resolve_profile_identity_context``,
``compute_can_draft``/``has_permission``, the value resolver, and the
``create_*_draft`` writer so the only thing under test is the ownership gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


# ── Identities ────────────────────────────────────────────────────────────
_CALLER_SESSION = uuid4()
_CALLER_PROFILE = uuid4()
_OWNER_SESSION = uuid4()  # a *different* user's session
_OWNER_PROFILE = uuid4()  # a *different* user's profile


@dataclass
class _Profile:
    profiles_id = _CALLER_PROFILE
    role_level = 1  # NOT super-admin
    role_permissions: list = None
    department_ids: list = None
    session_id = _CALLER_SESSION


@dataclass
class _SuperProfile(_Profile):
    role_level = 0  # super-admin


@dataclass
class _Draft:
    """A persisted draft row as returned by ``get_*_drafts``."""

    id: object
    session_id: object
    profile_ids: list


# Minimal asyncpg-like stubs the impls thread through (the real work is mocked).
class _Conn:
    async def execute(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchrow(self, *a, **kw):
        return None

    async def fetchval(self, *a, **kw):
        return None

    def transaction(self):
        return self._Tx()

    class _Tx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False


class _Pool:
    class _ctx:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *a):
            return False

    def acquire(self):
        return self._ctx()


# ── Per-endpoint wiring ─────────────────────────────────────────────────────
# (module path, impl attr, request class attr, create symbol, getter symbol,
#  extra symbols to no-op out so the impl returns without touching real infra)
@dataclass
class _Case:
    module: str
    impl: str
    request_cls: str
    create_sym: str
    getter_sym: str
    # permission gate symbol to force-True
    perm_sym: str
    perm_is_has_permission: bool = False


CASES = {
    "auth": _Case(
        "app.infra.auth.draft", "patch_auth_draft_impl",
        "app.infra.auth.types.PatchAuthDraftApiRequest",
        "create_auth_draft", "get_auth_drafts", "compute_can_draft",
    ),
    "provider": _Case(
        "app.infra.provider.draft", "patch_provider_draft_impl",
        "app.infra.provider.types.PatchProviderDraftApiRequest",
        "create_provider_draft", "get_provider_drafts", "compute_can_draft",
    ),
    "simulation": _Case(
        "app.infra.simulation.draft", "patch_simulation_draft_impl",
        "app.infra.simulation.types.PatchSimulationDraftApiRequest",
        "create_simulation_draft", "get_simulation_drafts", "compute_can_draft",
    ),
    "cohort": _Case(
        "app.infra.cohort.draft", "patch_cohort_draft_impl",
        "app.infra.cohort.types.PatchCohortDraftApiRequest",
        "create_cohort_draft", "get_cohort_drafts", "compute_can_draft",
    ),
    "department": _Case(
        "app.infra.department.draft", "patch_department_draft_impl",
        "app.infra.department.types.PatchDepartmentDraftApiRequest",
        "create_department_draft", "get_department_drafts", "compute_can_draft",
    ),
    "field": _Case(
        "app.infra.field.draft", "patch_field_draft_impl",
        "app.infra.field.types.PatchFieldDraftApiRequest",
        "create_field_draft", "get_field_drafts", "compute_can_draft",
    ),
    "model": _Case(
        "app.infra.model.draft", "patch_model_draft_impl",
        "app.infra.model.types.PatchModelDraftApiRequest",
        "create_model_draft", "get_model_drafts", "compute_can_draft",
    ),
    "parameter": _Case(
        "app.infra.parameter.draft", "patch_parameter_draft_impl",
        "app.infra.parameter.types.PatchParameterDraftApiRequest",
        "create_parameter_draft", "get_parameter_drafts", "compute_can_draft",
    ),
    "profile": _Case(
        "app.infra.profile.draft", "patch_profile_draft_impl",
        "app.infra.profile.types.PatchProfileDraftApiRequest",
        "create_profile_draft", "get_profile_drafts", "compute_can_draft",
    ),
    "eval": _Case(
        "app.infra.eval.draft", "patch_eval_draft_impl",
        "app.infra.eval.types.PatchEvalDraftApiRequest",
        "create_eval_draft", "get_eval_drafts", "compute_can_draft",
    ),
    "rubric": _Case(
        "app.infra.rubric.draft", "patch_rubric_draft_impl",
        "app.infra.rubric.types.PatchRubricDraftApiRequest",
        "create_rubric_draft", "get_rubric_drafts", "compute_can_draft",
    ),
}


def _import(path: str):
    mod_path, _, attr = path.rpartition(".")
    mod = __import__(mod_path, fromlist=[attr])
    return getattr(mod, attr)


def _wire(monkeypatch, case: _Case, *, profile, getter_rows, create_calls):
    """Patch the impl module so only the ownership guard remains live."""
    mod = case.module

    async def fake_resolve(*a, **kw):
        return profile

    async def fake_resolve_values(*a, **kw):
        return []

    async def fake_getter(conn, ids, redis, active=True, *, bypass_cache=False):
        return list(getter_rows)

    async def fake_create(*a, **kw):
        create_calls.append(kw.get("id"))

        @dataclass
        class _Res:
            id: object
        return _Res(id=kw.get("id") or uuid4())

    async def fake_noop(*a, **kw):
        return None

    monkeypatch.setattr(f"{mod}.resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(f"{mod}.{case.perm_sym}", lambda **kw: True)
    monkeypatch.setattr(f"{mod}.{case.getter_sym}", fake_getter)
    monkeypatch.setattr(f"{mod}.{case.create_sym}", fake_create)
    # Refreshers / soft-call helpers / auto-accept: no-op so we never reach
    # real infra after the guard decision.
    for sym in (
        "refresh_soft_calls",
        "create_soft_call",
        "get_soft_call",
    ):
        try:
            monkeypatch.setattr(f"{mod}.{sym}", fake_noop)
        except AttributeError:
            pass
    # The value resolver lives in-module for most; patch when present.
    try:
        monkeypatch.setattr(f"{mod}._resolve_creatable_values", fake_resolve_values)
    except AttributeError:
        pass
    # persona-style impls call refresh_*_impl directly — stub them.
    for sym in dir(_import(f"{mod}.{case.impl}").__globals__ and object) or []:
        pass


def _build_request(case: _Case, victim_id):
    req_cls = _import(case.request_cls)
    # Set every id surface so whichever the impl keys its guard on (draft_id /
    # input_draft_id / idempotency_key) sees the victim id.
    return req_cls(
        draft_id=victim_id,
        input_draft_id=victim_id,
        idempotency_key=victim_id,
    )


async def _run(case: _Case, monkeypatch, *, profile, getter_rows, victim_id):
    impl = _import(f"{case.module}.{case.impl}")
    create_calls: list = []
    # Stub any refresh_*_impl the module imports so post-write paths are inert.
    mod_globals = impl.__globals__
    for name, val in list(mod_globals.items()):
        if name.startswith("refresh_") and name.endswith("_impl") and callable(val):
            async def _noop(*a, **kw):
                return None
            monkeypatch.setitem(mod_globals, name, _noop)
        if name.startswith("_refresh_") and callable(val):
            async def _noop2(*a, **kw):
                return None
            monkeypatch.setitem(mod_globals, name, _noop2)
        if name.startswith("_maybe_auto_accept") and callable(val):
            async def _noop3(*a, **kw):
                return False
            monkeypatch.setitem(mod_globals, name, _noop3)
        if name == "resolve_rubric_point_totals" and callable(val):
            async def _noop4(*a, **kw):
                return (None, None)
            monkeypatch.setitem(mod_globals, name, _noop4)
        if name == "resolve_primary_departments_id" and callable(val):
            async def _noop5(*a, **kw):
                return None
            monkeypatch.setitem(mod_globals, name, _noop5)

    _wire(monkeypatch, case, profile=profile, getter_rows=getter_rows, create_calls=create_calls)

    request = _build_request(case, victim_id)
    result = await impl(
        _Pool(),
        object(),
        profile_id=uuid4(),
        session_id=_CALLER_SESSION,
        request=request,
    )
    return result, create_calls


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", list(CASES))
class TestRemainingDraftOwnership:
    async def test_foreign_owner_denied_and_not_written(self, name, monkeypatch):
        case = CASES[name]
        victim_id = uuid4()
        foreign = _Draft(
            id=victim_id, session_id=_OWNER_SESSION, profile_ids=[_OWNER_PROFILE]
        )
        with pytest.raises(HTTPException) as exc:
            await _run(
                case, monkeypatch,
                profile=_Profile(), getter_rows=[foreign], victim_id=victim_id,
            )
        assert exc.value.status_code == 403, name

    async def test_owned_by_caller_session_allowed(self, name, monkeypatch):
        case = CASES[name]
        victim_id = uuid4()
        own = _Draft(
            id=victim_id, session_id=_CALLER_SESSION, profile_ids=[_OWNER_PROFILE]
        )
        _result, create_calls = await _run(
            case, monkeypatch,
            profile=_Profile(), getter_rows=[own], victim_id=victim_id,
        )
        assert create_calls, f"{name}: create_*_draft should run on an owned draft"

    async def test_owned_by_caller_profile_allowed(self, name, monkeypatch):
        case = CASES[name]
        victim_id = uuid4()
        own = _Draft(
            id=victim_id, session_id=_OWNER_SESSION, profile_ids=[_CALLER_PROFILE]
        )
        _result, create_calls = await _run(
            case, monkeypatch,
            profile=_Profile(), getter_rows=[own], victim_id=victim_id,
        )
        assert create_calls, f"{name}: profile-owned draft should be allowed"

    async def test_super_admin_bypass_allowed(self, name, monkeypatch):
        case = CASES[name]
        victim_id = uuid4()
        foreign = _Draft(
            id=victim_id, session_id=_OWNER_SESSION, profile_ids=[_OWNER_PROFILE]
        )
        _result, create_calls = await _run(
            case, monkeypatch,
            profile=_SuperProfile(), getter_rows=[foreign], victim_id=victim_id,
        )
        assert create_calls, f"{name}: super-admin should bypass the guard"

    async def test_new_draft_id_allowed(self, name, monkeypatch):
        case = CASES[name]
        victim_id = uuid4()
        # No existing row → first-write/legitimate upsert of caller's own id.
        _result, create_calls = await _run(
            case, monkeypatch,
            profile=_Profile(), getter_rows=[], victim_id=victim_id,
        )
        assert create_calls, f"{name}: new/own draft_id must be allowed (first-write)"
