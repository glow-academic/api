"""Behavior tests for `core/app/infra/identity/resolve_identity.py`.

Targets:
- `get_system_session_id(conn, redis)` — refactored recently to take an
  injected Redis client (was reaching for the app-global, untestable).
  Caching: first call mints a session in sessions_entry, subsequent calls
  return the same id even with a different conn.
- `extract_bearer_token` — pure parser for the `Authorization` header.
- `extract_api_key` — pure parser for `X-Api-Key`.
- `_issuer_matches` — JWT-issuer comparison that ignores dev ports.

The integration cases (`get_system_session_id`) use the real `pool` /
`redis_client` fixtures from conftest. The pure helpers don't need DB
or Redis.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from tests.helpers import nonexistent_id

import app.infra.identity.resolve_identity as ri
from app.infra.identity.resolve_identity import (
    _issuer_matches,
    extract_api_key,
    extract_bearer_token,
    get_system_session_id,
)

# NOTE: `get_sessions` / `search_sessions` are intentionally NOT used to verify
# the system session exists because sessions_mv inner-joins
# profiles_sessions_connection — system sessions (profile_id=None) are
# excluded by design and not visible through those primitives. We verify the
# system-session contract through the function's own caching behavior:
# successive calls returning the same UUID prove (a) the session was minted
# and (b) the DB existence check inside get_system_session_id still passes,
# i.e. the row is present and active.


@pytest.fixture(autouse=True)
def _reset_system_session_cache():
    """Module-level `_system_session_id` cache must reset between tests
    so caching behavior is observable. Without this, the second test sees
    the first test's session and the test order becomes load-bearing."""
    ri._system_session_id = None
    yield
    ri._system_session_id = None


# ─── extract_bearer_token ──────────────────────────────────────────────────


class TestExtractBearerToken:
    def test_returns_token_from_well_formed_header(self):
        assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_lowercase_bearer_keyword_works(self):
        # The OAuth2 spec says case-insensitive; the parser uses
        # `.lower()` to confirm.
        assert extract_bearer_token("bearer xyz") == "xyz"

    def test_strips_trailing_whitespace(self):
        assert extract_bearer_token("Bearer   token-with-padding  ") == (
            "token-with-padding"
        )

    @pytest.mark.parametrize(
        "header",
        [None, "", "Basic dXNlcjpwYXNz", "Bearer", "bearertoken-without-space"],
    )
    def test_returns_none_for_malformed_inputs(self, header):
        assert extract_bearer_token(header) is None


# ─── extract_api_key ───────────────────────────────────────────────────────


class TestExtractApiKey:
    def test_returns_trimmed_key(self):
        assert extract_api_key("  sk-abc123  ") == "sk-abc123"

    @pytest.mark.parametrize("header", [None, ""])
    def test_returns_none_for_empty(self, header):
        assert extract_api_key(header) is None


# ─── _issuer_matches ───────────────────────────────────────────────────────


class TestIssuerMatches:
    def test_identical_issuers_match(self):
        assert _issuer_matches(
            "https://glow.example.com/auth/realms/master",
            "https://glow.example.com/auth/realms/master",
        ) is True

    def test_dev_ports_normalized_away(self):
        """8080 / 3000 / 8000 are stripped before comparison so a token
        issued by `http://localhost:8080/auth/realms/master` matches an
        expected issuer of `http://localhost/auth/realms/master`."""
        assert _issuer_matches(
            "http://localhost:8080/auth/realms/master",
            "http://localhost/auth/realms/master",
        ) is True
        assert _issuer_matches(
            "http://localhost:3000/api",
            "http://localhost/api",
        ) is True

    def test_non_dev_ports_do_not_match(self):
        """Port 9090 is NOT in the dev-ports list; tokens from a non-dev
        port must not silently match a no-port expected issuer."""
        assert _issuer_matches(
            "http://localhost:9090/api",
            "http://localhost/api",
        ) is False

    def test_different_hosts_never_match(self):
        assert _issuer_matches(
            "https://attacker.com/auth/realms/master",
            "https://glow.example.com/auth/realms/master",
        ) is False


# ─── get_system_session_id ─────────────────────────────────────────────────


pytestmark_async = pytest.mark.asyncio


class TestGetSystemSessionId:
    """The system session is the bookkeeping session used for non-user
    background work (metrics snapshots, health checks). Contract:

    1. First call mints a row in `sessions_entry` and returns its id.
    2. Subsequent calls — even with a different `conn` — return the SAME
       id from the module cache (no duplicate sessions).
    3. If the cached session_id no longer exists in the DB (e.g. session
       expired or was archived), a fresh one is minted.
    4. Cached session_id remains valid across pool acquisitions.
    """

    @pytest.mark.asyncio
    async def test_returns_same_id_across_calls(self, pool, redis_client):
        """First call mints the system session; second call (different
        conn from the same pool) returns the SAME id.

        The fact that the second call returns the same id proves two
        things: (a) the first call wrote a real row in sessions_entry,
        and (b) that row is still `active=true` — the function's internal
        existence check would otherwise remint and we'd see a different
        id. Avoids the 'unbounded sessions_entry growth under steady
        metrics load' failure mode.
        """
        async with pool.acquire() as conn:
            first = await get_system_session_id(conn, redis_client)

        async with pool.acquire() as conn:
            second = await get_system_session_id(conn, redis_client)

        assert isinstance(first, UUID)
        assert second == first
        assert ri._system_session_id == first  # cache populated

    @pytest.mark.asyncio
    async def test_remints_when_cache_points_at_nonexistent_id(
        self, pool, redis_client
    ):
        """If the module cache holds a UUID that doesn't exist in
        sessions_entry (e.g. a stale id surviving across deploys, or
        process restart followed by table truncation), the function must
        observe the existence check failing and mint a fresh row.

        Stability check: a follow-up call must return the SAME new id —
        proving the minted session is real, not another fake.
        """
        stale_id = nonexistent_id()
        ri._system_session_id = stale_id

        async with pool.acquire() as conn:
            minted = await get_system_session_id(conn, redis_client)

        async with pool.acquire() as conn:
            followup = await get_system_session_id(conn, redis_client)

        assert minted != stale_id, (
            "Returned the stale cached id without re-checking existence."
        )
        assert followup == minted, (
            "Follow-up call returned a different id; the freshly-minted "
            "session is not actually persisted/active."
        )
