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

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.queries: list[str] = []

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
        the email lookup at all (regression guard for the early-return)."""
        pid = uuid4()

        def _boom(*_a, **_k):
            raise AssertionError("email lookup should be skipped")

        conn = _FakeConn([])
        result = await _resolve_profile_id(
            {"profile_id": str(pid)}, _FakePool(conn)
        )

        assert result == pid
        assert conn.queries == []
