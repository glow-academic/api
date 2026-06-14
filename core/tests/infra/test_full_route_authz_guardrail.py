"""R4 — FULL-app-route-table ownership guardrail (the durable, cross-family net).

The prior route-derived guardrail
(``core/tests/infra/test/test_test_mutation_authz_class.py``
``_test_router_routes()``) walks ONLY ``app.routes.test.router``. ``routes.test``
imports nothing from ``routes.attempt`` / ``routes.system``, so the ~19 sibling
families were structurally invisible — which is exactly *why* the attempt-family
twins (R1 ``attempt/generate``, R2 ``attempt/watch``) and the system-group rename
(R3) slipped through after the test family was patched. Same recurring pattern:
"fix the triggering family, miss the sibling."

This guardrail enumerates owner-scoped MUTATION operations from the **full
FastAPI app route table** (``app.server.fastapi_app.routes`` across ALL routers),
follows each route handler transitively into the ``app.infra`` functions it calls
(not just ``*_impl``-named ones — the audit/write wrappers take the writer as a
callback), and asserts each one either references an ownership-enforcement marker
(``enforce_*_access*`` / ``enforce_*_owner*``) somewhere in its resolve-chain, or
is explicitly exempted with a reason.

Crucially, ownership scope is classified by the **resolve-chain**, not router
membership: the surface here is the three per-session-private artifact families
(``/attempt``, ``/test``, ``/system``) whose chains resolve a caller-supplied
child id (``group_id`` / ``invocation_id`` / ``run_id`` / ``grade_id`` /
``message_id`` / ``attempt_id``) to a private owner and therefore share the
``enforce_attempt_access_*`` / ``enforce_test_access_*`` gates. Org-shared catalog
families (tool/model/rubric/persona/…) gate on ``has_permission``/role, not on a
private-owner chain, so they are out of this net by design.

A NEW unguarded route in any of these families — added without a guard AND
without an exemption — fails here, even if its sibling family was the one
patched. The marker-presence registry (``_TEST_MUTATORS``) in the test-family
suite could never see those siblings; this can.

TODO (R4, time-bound extension): also enumerate the WS handler registry
(``app.ws`` input handlers — e.g. ``test.next``, ``system.group_name``) and the
INFRA_OPS dispatch map, both of which are reachable write paths not modeled by
the HTTP route table. The highest-value surface (the full HTTP route table) is
covered here and passing; the WS/INFRA_OPS handlers are individually covered by
their own per-op authz suites (``test_test_mutation_authz_class`` F2/F3,
``system/test_group_rename_authz``) until they are folded into this net.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib

import pytest

# ── Guard markers ─────────────────────────────────────────────────────────────
# Any reference to one of these names anywhere in a route's resolve-chain (the
# handler or any app.infra function it transitively calls) satisfies the
# guardrail. This is the union of the attempt + test ownership gate families
# plus the upload/draft owner gates that the media/draft routes funnel through.
_GUARD_MARKERS = {
    "enforce_attempt_access_by_group",
    "enforce_attempt_access_by_attempt",
    "enforce_attempt_access_by_attempt_chat",
    "enforce_attempt_access_by_chat",
    "enforce_attempt_access_by_grade",
    "enforce_attempt_access_by_message",
    "enforce_attempt_media_access",
    "enforce_attempt_owner_access",
    "enforce_test_access_by_invocation",
    "enforce_test_access_by_run",
    "enforce_test_access_by_grade",
    "enforce_test_access_by_test",
    "enforce_test_access_by_group",
    "enforce_draft_owner",
    "enforce_upload_owner",
}

# Owner-scoped families: the per-session-private artifact chains that share the
# enforce_*_access gates above (group → session → owner). Catalog families are
# classified out by their chain (they reach has_permission/role, never a
# private-owner resolution), so restricting to these three prefixes is the
# router-independent realization of "owner-scoped, not catalog".
_PRIVATE_FAMILY_PREFIXES = ("/attempt", "/test", "/system")


# ── (METHOD, PATH) → reason exemptions ────────────────────────────────────────
# An owner-scoped mutation route is exempt only if it is genuinely read-safe,
# creation-only, scoped to the caller's OWN group, or guarded by a different
# owner family. Every entry carries a reason reviewed in the diff. A NEW route
# with neither a guard nor an entry here FAILS the completeness check below.
_ROUTE_GUARD_EXEMPT: dict[tuple[str, str], str] = {
    # ── Reads / refresh / export: scoped to the caller's OWN group via the
    # group_<artifact>_impl window (no caller-supplied child id is trusted to
    # cross owners), or pure cache refresh. Mirrors the test-family exemptions.
    ("POST", "/attempt/get"): "read — group_attempt_impl scopes to caller's own group",
    ("POST", "/attempt/search"): "read — caller-scoped search",
    ("POST", "/attempt/refresh"): "cache refresh — caller-own group window",
    ("POST", "/attempt/context"): "read — caller-own context",
    ("POST", "/attempt/export"): "read/export — caller-own group window",
    ("POST", "/attempt/generations"): "read — caller-own group window",
    ("POST", "/attempt/group"): "read — group_attempt_impl scopes to caller's own group",
    ("POST", "/attempt/chat_get"): "read — caller-own chat window",
    ("POST", "/attempt/chat_export"): "read/export — caller-own chat window",
    ("POST", "/attempt/drafts"): "read — caller-own drafts",
    ("POST", "/attempt/home"): "read/dashboard — caller-own aggregate",
    ("POST", "/attempt/practice"): "read/dashboard — caller-own aggregate",
    ("POST", "/attempt/dashboard"): "read/dashboard — caller-own aggregate",
    ("POST", "/attempt/leaderboard"): "read/dashboard — scoped-population aggregate (no owner write)",
    ("POST", "/attempt/report"): "read/dashboard — caller-own aggregate",
    ("POST", "/attempt/problem"): "problem report — caller-own group window",
    ("POST", "/test/get"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/search"): "read — caller-scoped search",
    ("POST", "/test/refresh"): "cache refresh — caller-own group window",
    ("POST", "/test/context"): "read — caller-own context",
    ("POST", "/test/export"): "read/export — group_test_impl scopes to caller's own group",
    ("POST", "/test/generations"): "read — caller-own group window",
    ("POST", "/test/invocations"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/group"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/drafts"): "read — caller-own drafts",
    ("POST", "/test/benchmark"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/problem"): "problem report — caller-own group window",
    ("POST", "/system/context"): "read — caller-own context",
    ("POST", "/system/export"): "read/export — caller-own group window",
    ("POST", "/system/generations"): "read — caller-own group window",
    ("POST", "/system/groups"): "read — caller-own group search",
    ("POST", "/system/sessions"): "read — caller-own session search",
    ("POST", "/system/session"): "read — caller-own session",
    ("POST", "/system/group"): "read — group_system_impl scopes to caller's own group",
    ("POST", "/test/invocation_get"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/system/refresh"): "cache refresh — caller-own group window",
    ("POST", "/system/resolve"): "problem-resolution — caller-own problem report",
    ("POST", "/system/problem"): "problem report — caller-own group window",
    ("POST", "/system/health"): "read — system health (no owner-scoped write)",
    ("POST", "/system/activity"): "read/dashboard — aggregate (no owner write)",
    ("POST", "/system/pricing"): "read — pricing table (no owner-scoped write)",
    # ── Bulk archive: carries its OWN inline owner/role-scope BOLA guard
    # (resolve_profile_identity_context + per-row department/role filter, #148)
    # rather than a named enforce_* helper, because it filters a SET of attempts
    # to only those the actor owns or outranks. Verified in its own suite.
    ("POST", "/attempt/archive"): (
        "inline owner/role-scope BOLA guard (#148) — filters the attempt set to "
        "the actor's own/outranked rows, not a named enforce_*_access helper"
    ),
    # ── Creation: a new artifact is minted for the caller; no foreign id consumed.
    ("POST", "/attempt/start"): "creation — mints a new attempt for the caller",
    ("POST", "/test/start"): "creation — mints a new test for the caller",
    # ── Media / draft / decrypt: carry their OWN owner gate (upload/draft owner
    # family or a key-belongs check), a different family than enforce_*_access,
    # verified in their own suites.
    ("POST", "/attempt/audio_upload"): "guarded by has_permission(attempt:audio_upload) + caller-own upload",
    ("POST", "/attempt/chat_speak"): "TTS read of caller-own chat audio; permission-gated, no owner write",
    # chat_silence tears down an in-memory live voice session keyed by chat_id;
    # it carries its OWN bespoke owner-mismatch guard (the AudioSession owner is
    # checked against the requester before stopping — see silence.py) rather than
    # a DB-backed enforce_*_access helper, because the session lives in memory.
    ("POST", "/attempt/chat_silence"): (
        "bespoke in-memory owner-mismatch guard (AudioSession owner vs requester) "
        "— a victim's live voice session can't be silenced by supplying its chat_id"
    ),
    ("POST", "/test/decrypt"): "guarded by has_permission(test:invocation_draft) + key-belongs check (#268/#270)",
    # ── Shared browser-SSE / run-watch: group scoping is a pre-existing
    # cross-artifact concern (same class as the test-family GET /test/watch
    # exemption), separate from the per-op enforce_*_access fixes.
    ("POST", "/system/watch"): (
        "shared run-watch (watch_system_impl); group scoping is a pre-existing "
        "cross-artifact concern, separate from the per-op access fixes"
    ),
    # NOTE: ``/system/generate`` was surfaced by THIS broadened net as the third
    # cross-user-generation IDOR twin (after test/generate G2 and attempt/generate
    # R1) and has since been FIXED — ``generate_system_impl`` now calls
    # ``enforce_attempt_access_by_group`` when ``group_id`` is client-supplied — so
    # it is intentionally NOT exempt here: the guardrail actively re-asserts it.
}


# ── AST helpers (generalized from test_test_mutation_authz_class) ──────────────


def _build_infra_func_index() -> tuple[dict[str, list[ast.AST]], dict[str, ast.AST]]:
    """Index every function defined in the ``app.infra`` tree by name, so a
    handler's call can be followed to the function's body wherever it lives
    (the audit/write wrappers take the actual writer as a callback, so following
    only ``*_impl`` names — as the single-router guardrail does — misses the gate
    that lives inside a shared wrapper). Returns (name→[nodes], module→tree)."""
    infra = importlib.import_module("app.infra")
    root = pathlib.Path(infra.__file__).parent
    by_name: dict[str, list[ast.AST]] = {}
    mod_tree: dict[str, ast.AST] = {}
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root).with_suffix("")
        parts = [p for p in rel.parts if p != "__init__"]
        dotted = "app.infra" + ("." + ".".join(parts) if parts else "")
        try:
            tree = ast.parse(py.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        mod_tree[dotted] = tree
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                by_name.setdefault(node.name, []).append(node)
    return by_name, mod_tree


def _handler_node(module_name: str, func_name: str):
    """AST node for the route handler ``func_name`` in ``module_name`` (routes
    modules are outside app.infra, so parse them directly)."""
    try:
        mod = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(mod))
    except (ImportError, OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func_name
        ):
            return node
    return None


def _called_names(node) -> set[str]:
    """Every callee NAME referenced inside ``node`` (Name or Attribute)."""
    names: set[str] = set()
    if node is None:
        return names
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
    return names


# Shared write-wrappers that host the ownership gate on behalf of their callers
# (the route hands its writer in as a callback and the wrapper resolves the
# child id → owner and enforces). The gate lives in the WRAPPER, not in a
# ``*_impl`` the route names, so the follow must descend into these by name.
_WRITE_WRAPPER_NAMES = {
    "run_chat_analysis_write",
}


def _node_names_guard(node) -> bool:
    """True iff ``node``'s OWN body references a guard marker (called, or named
    as a bare callback) — not counting anything it calls."""
    if node is None:
        return False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in _GUARD_MARKERS:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in _GUARD_MARKERS:
            return True
    return False


def _chain_references_guard(
    node, func_index: dict[str, list[ast.AST]], *, _seen=None, _depth=0
) -> bool:
    """True iff the route's OWN write path references a guard marker.

    The follow is deliberately constrained to the *write path* — the handler
    body, and recursively the ``*_impl`` write functions / shared write-wrappers
    it calls — NOT the whole transitively-reachable infra call graph. An
    unconstrained deep follow produces FALSE NEGATIVES: nearly every attempt/test
    route can reach *some* sibling that names the marker, so a route whose own
    impl dropped the guard would still look "guarded". Restricting recursion to
    write-impls/wrappers keeps the gate tied to the route's actual mutation."""
    if node is None or _depth > 5:
        return False
    if _seen is None:
        _seen = set()
    if _node_names_guard(node):
        return True
    for name in _called_names(node):
        # Only descend into the route's own write path: the write impls it
        # invokes (``*_impl``) and the shared write-wrappers that host the gate.
        if not (name.endswith("_impl") or name in _WRITE_WRAPPER_NAMES):
            continue
        for callee in func_index.get(name, [])[:4]:
            key = id(callee)
            if key in _seen:
                continue
            _seen.add(key)
            if _chain_references_guard(
                callee, func_index, _seen=_seen, _depth=_depth + 1
            ):
                return True
    return False


def _full_app_mutation_routes() -> list[tuple[str, str, str, str]]:
    """(method, path, endpoint_module, endpoint_name) for every mutating route on
    the FULL FastAPI app (all routers), restricted to the private-artifact
    families. GET routes are reads; HEAD/OPTIONS are protocol — both skipped.
    This is the SOURCE OF TRUTH (the live app route table, not a hand-list)."""
    from app.server import fastapi_app

    out: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for r in fastapi_app.routes:
        ep = getattr(r, "endpoint", None)
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", None)
        if ep is None or methods is None or path is None:
            continue
        if not path.startswith(_PRIVATE_FAMILY_PREFIXES):
            continue
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS", "GET"}:
                continue
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            out.append((method, path, ep.__module__, ep.__name__))
    return out


# ── The guardrail ─────────────────────────────────────────────────────────────


def test_full_app_route_table_is_non_empty():
    """Sanity: the enumeration actually sees the private-family mutation
    surface (so a passing completeness check below is not vacuous because the
    app failed to import / no routes matched)."""
    routes = _full_app_mutation_routes()
    assert len(routes) >= 50, (
        f"expected the full app route table to expose dozens of "
        f"attempt/test/system mutation routes, saw {len(routes)}"
    )


def test_every_owner_scoped_route_is_guarded_or_exempt():
    """FULL-app completeness (R4). For every mutating route in the per-session-
    private artifact families (attempt/test/system), assert its resolve-chain
    references an ownership-enforcement marker, or it is explicitly exempted with
    a reason.

    This is the cross-family net the single-router guardrail lacked: R1
    (attempt/generate), R2 (attempt/watch) and R3 (system rename) all lived in
    families the test-router walk could not see. A new unguarded route in ANY of
    these families now fails here."""
    func_index, _ = _build_infra_func_index()
    offenders: list[str] = []
    for method, path, ep_mod, ep_name in _full_app_mutation_routes():
        if (method, path) in _ROUTE_GUARD_EXEMPT:
            continue
        if _chain_references_guard(_handler_node(ep_mod, ep_name), func_index):
            continue
        offenders.append(f"{method} {path} ({ep_mod}.{ep_name})")

    assert not offenders, (
        "These owner-scoped (attempt/test/system) mutation routes neither "
        "reference an ownership-enforcement guard (enforce_*_access* / "
        "enforce_*_owner) anywhere in their resolve-chain nor appear in "
        f"_ROUTE_GUARD_EXEMPT: {offenders}. Add the appropriate enforce_* guard "
        "(mirror the attempt/test subsystems), or, if the route is genuinely "
        "read-safe / creation-only / guarded by another owner family, add it to "
        "_ROUTE_GUARD_EXEMPT with a reason."
    )


def test_route_guardrail_catches_a_newly_unguarded_route(monkeypatch):
    """Non-vacuous proof the full-app net fires. Inject a phantom owner-scoped
    route whose handler has NO guard and is NOT exempt: the completeness check
    must report it as an offender. (Guards the guardrail itself.)"""
    real = _full_app_mutation_routes

    def _with_phantom():
        rows = real()
        # app.infra.system.activity.get_activity_impl is a read aggregate with
        # no ownership gate — a perfect stand-in for an unguarded new mutator.
        rows.append(
            ("POST", "/attempt/__phantom_unguarded__",
             "app.routes.system.activity", "get_activity")
        )
        return rows

    monkeypatch.setattr(
        "tests.infra.test_full_route_authz_guardrail._full_app_mutation_routes",
        _with_phantom,
    )
    with pytest.raises(AssertionError) as exc:
        test_every_owner_scoped_route_is_guarded_or_exempt()
    assert "__phantom_unguarded__" in str(exc.value)
