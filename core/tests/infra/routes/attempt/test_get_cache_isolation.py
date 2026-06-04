"""Cross-profile cache-isolation test for the ``POST /attempt/get`` route.

Companion to the #191 home/practice fix. ``get_attempt_impl`` caches the
attempt-detail bundle, but ``GetAttemptDetailRequest`` carries only
``attempt_id`` — no actor identity. The response, however, is built
per-actor: ``get_attempt_internal`` runs ``check_attempt_access`` (owner, or
strictly-higher role) and only returns the full bundle to an authorized
caller, returning ``access_denied=True`` otherwise.

If the cache key is built from ``attempt_id`` alone it collides across all
callers, so an authorized profile (the owner) warming the cache would leak
the entire attempt bundle to an unauthorized profile on the next hit —
bypassing ``check_attempt_access`` (cross-profile attempt-content leak /
IDOR). The key must be scoped to the actor's ``profile_id``.

This test fails on the pre-fix code (profile B receives A's cached bundle)
and passes once the key includes ``user_ctx=str(profile_id)``.
"""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import create_attempt_chat_graph
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def attempt_owner_actor(pool, redis_client, setting_graph_factory):
    """The actor that OWNS the attempt and warms the cache."""
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        extra_permissions=[("attempt", "start")],
        group_name="attempt-cache-owner",
        role_name_prefix="Attempt Cache Owner",
    )


@pytest_asyncio.fixture
async def attempt_other_actor(pool, redis_client, setting_graph_factory):
    """A DISTINCT base-role actor that does NOT own the attempt.

    Created with the same default (non-canonical, level<=1) role as the
    owner, so ``check_attempt_access`` denies it any attempt it does not
    own — making it the correct probe for the cross-profile leak.
    """
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        extra_permissions=[("attempt", "start")],
        group_name="attempt-cache-other",
        role_name_prefix="Attempt Cache Other",
    )


async def _create_owned_attempt(pool, redis, actor) -> str:
    """Build a full attempt graph owned by ``actor`` and materialize the MVs."""
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_bridge.refresh import (
        refresh_attempt_chat_bridge,
    )
    from app.tools.entries.attempt_message.create import create_attempt_message
    from app.tools.entries.attempt_message.refresh import refresh_attempt_message

    async with pool.acquire() as conn:
        graph = await create_attempt_chat_graph(
            conn,
            redis,
            actor.profiles_id,
            title="Cache Isolation Chat",
            position=0,
            text_enabled=True,
        )
        await create_attempt_message(
            conn,
            redis,
            chat_id=graph.attempt_chat_id,
            session_id=graph.session_id,
        )
        await refresh_attempt_chat_bridge(conn)
        await refresh_attempt_chat(conn)
        await refresh_attempt_message(conn)
        await refresh_attempt(conn)

    return str(graph.attempt_id)


@pytest.mark.asyncio
async def test_attempt_get_cache_does_not_leak_across_profiles(
    pool,
    redis_client,
    attempt_route_client,
    attempt_owner_actor,
    attempt_other_actor,
):
    attempt_id = await _create_owned_attempt(
        pool, redis_client, attempt_owner_actor
    )

    # Owner A: warm the cache (NO bypass header → the full bundle is cached).
    attempt_route_client.authenticate(
        profile_id=attempt_owner_actor.profile_id,
        session_id=attempt_owner_actor.session_id,
    )
    resp_a = await attempt_route_client.client.post(
        "/attempt/get",
        json={"attempt_id": attempt_id},
    )
    assert resp_a.status_code == 200, resp_a.text
    payload_a = resp_a.json()
    assert payload_a["attempt_exists"] is True
    assert payload_a["access_denied"] is False
    assert payload_a["attempt"]["id"] == attempt_id

    # Other B: identical request body, same un-bypassed cache path. B does
    # not own the attempt and holds a base role, so check_attempt_access must
    # deny it — B must NEVER be served A's cached, access-granted bundle.
    attempt_route_client.authenticate(
        profile_id=attempt_other_actor.profile_id,
        session_id=attempt_other_actor.session_id,
    )
    resp_b = await attempt_route_client.client.post(
        "/attempt/get",
        json={"attempt_id": attempt_id},
    )
    assert resp_b.status_code == 200, resp_b.text
    payload_b = resp_b.json()

    # The leak: pre-fix, B gets A's cached bundle (access_denied False + full
    # attempt content). Post-fix, B gets its own access-gated response.
    assert payload_b["access_denied"] is True, (
        "cross-profile leak: unauthorized profile B was served the owner's "
        "cached attempt bundle"
    )
    assert payload_b.get("attempt") is None
    assert not payload_b.get("entries")

    _ = UUID(attempt_id)  # sanity: attempt_id is a well-formed UUID
