"""Regression test for the #87 problem-report bug — real DB, no mocks.

Guards against the bug where ``problem_<artifact>_impl`` (~20 sibling
functions across ``app/infra/*/problem.py``) called ``create_problem_entry``
without passing the required ``redis`` positional argument, raising
``TypeError: create_problem() missing 1 required positional argument: 'redis'``
and turning every ``POST /<artifact>/problem`` into a 500.

``problem_system_impl`` is exercised because it runs the full
group -> run -> call -> problem chain end to end (creating a real ``call_id``),
so a successful return proves ``redis`` reached ``create_problem``.
"""

from collections.abc import Awaitable, Callable

import asyncpg
import pytest
from redis.asyncio import Redis

from app.infra.system.problem import problem_system_impl
from tests.infra.route_helpers import create_admin_route_actor

pytestmark = pytest.mark.asyncio


async def test_problem_system_impl_passes_redis_through(
    pool: asyncpg.Pool,
    redis_client: Redis,
    setting_graph_factory: Callable[..., Awaitable[object]],
) -> None:
    """A permitted actor can report a system problem without a redis TypeError."""
    actor = await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["agent"],
        extra_permissions=[("system", "problem")],
        group_name="system-problem",
        role_name_prefix="System Problem Admin",
    )

    result = await problem_system_impl(
        pool,
        redis_client,
        profile_id=actor.profile_id,
        session_id=actor.session_id,
        type="bug",
        message="Regression guard for #87 — redis must reach create_problem.",
    )

    assert result.success is True
    assert result.problem_id is not None
