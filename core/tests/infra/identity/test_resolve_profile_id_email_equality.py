"""P4 regression: the auth-path `_resolve_profile_id` email lookup must be an
EQUALITY query (served by the `emails_email_idx` btree), NOT the leading-
wildcard substring search (`LIKE '%'||$1||'%'`) that `search_emails` performs.

Two properties are pinned:
1. An exact email claim resolves to its profile_id.
2. A substring of a stored email no longer spuriously matches (the old
   `LIKE '%sub%'` path would have matched "alice@example.com" for a token
   email of "alice@example", letting one user resolve as another).

The DB is faked at the connection boundary: `conn.fetch` applies real
equality semantics over a tiny `emails_resource` fixture, and asserts the
auth path issued an `email = $1` predicate (not `LIKE`). `search_profiles`
is monkeypatched (its own behavior is out of scope here). Fully modular —
no DB / Redis fixtures.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

import app.infra.identity.resolve_identity as ri
from app.infra.identity.resolve_identity import _resolve_profile_id


class _AcquireContext:
    def __init__(self, conn: object) -> None:
        self._conn = conn

    async def __aenter__(self) -> object:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConn:
    """Applies exact-equality semantics over an in-memory emails_resource so
    a substring claim cannot match — and records the SQL so the test can
    assert it is an equality predicate, never a LIKE."""

    def __init__(self, rows: list[dict], *, artifact_active: bool | None = True) -> None:
        # ``artifact_active`` is what ``SELECT active FROM profile_artifact``
        # returns for the ID1 direct-claim gate: True (active), False
        # (deactivated), or None (no such artifact).
        self._rows = rows
        self.queries: list[str] = []
        self._artifact_active = artifact_active
        self.fetchvals: list[str] = []

    async def fetch(self, sql: str, *args):
        self.queries.append(sql)
        assert "LIKE" not in sql.upper(), (
            "auth-path email lookup must not use a substring LIKE"
        )
        assert "=" in sql, "auth-path email lookup must be an equality predicate"
        email = args[0]
        return [
            {"id": r["id"]}
            for r in self._rows
            if r["email"] == email and r.get("active", True)
        ]

    async def fetchval(self, sql: str, *args):
        # ID1 direct-claim gate queries profile_artifact.active.
        self.fetchvals.append(sql)
        assert "profile_artifact" in sql
        return self._artifact_active


class _FakePool:
    def __init__(self, conn: object) -> None:
        self._conn = conn

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self._conn)


@pytest.mark.asyncio
class TestResolveProfileIdEmailEquality:
    async def test_exact_email_resolves(self, monkeypatch):
        email_id = uuid4()
        profile_id = uuid4()
        conn = _FakeConn([{"id": email_id, "email": "alice@example.com"}])

        async def fake_search_profiles(_conn, *, email_ids, active_only, limit_count):
            assert email_ids == [email_id]
            # ID1: the auth path must look up ACTIVE profiles only.
            assert active_only is True
            return ([profile_id], None)

        monkeypatch.setattr(
            "app.tools.artifacts.profile.search.search_profiles",
            fake_search_profiles,
        )

        result = await _resolve_profile_id(
            {"email": "alice@example.com"}, _FakePool(conn)
        )

        assert result == profile_id
        assert isinstance(result, UUID)

    async def test_substring_does_not_spuriously_match(self, monkeypatch):
        """A token email that is a *substring* of a stored email must NOT
        resolve — the old leading-wildcard LIKE would have matched it."""
        conn = _FakeConn([{"id": uuid4(), "email": "alice@example.com"}])

        async def fake_search_profiles(_conn, *, email_ids, active_only, limit_count):
            # Should never be reached: no email id matched.
            raise AssertionError("search_profiles called despite no email match")

        monkeypatch.setattr(
            "app.tools.artifacts.profile.search.search_profiles",
            fake_search_profiles,
        )

        # "alice@example" is a substring of the stored "alice@example.com".
        result = await _resolve_profile_id(
            {"email": "alice@example"}, _FakePool(conn)
        )

        assert result is None
        # Confirms the auth path actually executed the email equality query.
        assert any("emails_resource" in q for q in conn.queries)

    async def test_direct_profile_id_claim_skips_email_lookup(self, monkeypatch):
        """default_idp tokens carry profile_id directly and must not touch
        the email lookup — but DO verify the artifact is active (ID1)."""
        pid = uuid4()

        conn = _FakeConn([], artifact_active=True)
        result = await _resolve_profile_id(
            {"profile_id": str(pid)}, _FakePool(conn)
        )

        assert result == pid
        # No email lookup, but the ID1 active gate ran against profile_artifact.
        assert conn.queries == []
        assert any("profile_artifact" in q for q in conn.fetchvals)

    async def test_direct_profile_id_claim_inactive_is_revoked(self):
        """ID1: a direct profile_id claim for a DEACTIVATED artifact must be
        revoked (ValueError → 401), never resolved, and must not fall through
        to guest auto-create."""
        pid = uuid4()
        conn = _FakeConn([], artifact_active=False)

        with pytest.raises(ValueError, match="inactive"):
            await _resolve_profile_id({"profile_id": str(pid)}, _FakePool(conn))

        # The email path must not have been touched as a fallback.
        assert conn.queries == []

    async def test_direct_profile_id_claim_unknown_is_revoked(self):
        """ID1: a direct profile_id claim naming a non-existent artifact is a
        hard revoke, not a silent pass-through."""
        pid = uuid4()
        conn = _FakeConn([], artifact_active=None)

        with pytest.raises(ValueError):
            await _resolve_profile_id({"profile_id": str(pid)}, _FakePool(conn))

    async def test_email_resolves_only_active_then_revokes_deactivated(
        self, monkeypatch
    ):
        """ID1: when an email maps only to a DEACTIVATED profile, the auth path
        must revoke (ValueError) rather than return None — which would let
        resolve_identity reprovision the disabled user as a fresh guest."""
        email_id = uuid4()
        conn = _FakeConn([{"id": email_id, "email": "bob@example.com"}])

        calls: list[bool] = []

        async def fake_search_profiles(_conn, *, email_ids, active_only, limit_count):
            assert email_ids == [email_id]
            calls.append(active_only)
            # No ACTIVE match; an INACTIVE one exists.
            return ([] if active_only else [uuid4()], None)

        monkeypatch.setattr(
            "app.tools.artifacts.profile.search.search_profiles",
            fake_search_profiles,
        )

        with pytest.raises(ValueError, match="deactivated"):
            await _resolve_profile_id({"email": "bob@example.com"}, _FakePool(conn))

        # Probed active-only first, then fell back to an inactive existence check.
        assert calls == [True, False]

    async def test_email_no_profile_at_all_returns_none_for_guest_create(
        self, monkeypatch
    ):
        """ID1: a genuinely unknown email (no profile, active or not) returns
        None so the caller can auto-provision a guest — deactivation gating
        must not block first-time logins."""
        email_id = uuid4()
        conn = _FakeConn([{"id": email_id, "email": "carol@example.com"}])

        async def fake_search_profiles(_conn, *, email_ids, active_only, limit_count):
            return ([], None)  # nothing, either way

        monkeypatch.setattr(
            "app.tools.artifacts.profile.search.search_profiles",
            fake_search_profiles,
        )

        result = await _resolve_profile_id(
            {"email": "carol@example.com"}, _FakePool(conn)
        )
        assert result is None
