"""Resolve agent ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``agent_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching agent ids, applies any client-side ``excluded_ids``,
then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_agent_impl`` (which hydrates rows, computes facets, runs the
big-cache wrap). All we need is a list of UUIDs; the per-row permission
check inside the bulk impl filters out anything the user can't write to.

Mirrors the persona resolver field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bits are which filter fields we
forward (agent uses ``filter_model_ids`` / ``filter_tool_ids`` as
direct junction filters, where persona uses scenario-membership as a
reverse-lookup).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.agent.search import search_agents

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; agent
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_agent_ids(
    pool: asyncpg.Pool,
    redis: Redis,  # noqa: ARG001 — accepted for parity with other resolvers
    *,
    profile_id: UUID,  # noqa: ARG001 — see persona resolver doc
    # Same filter fields ``/agent/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_model_ids: list[UUID] | None = None,
    filter_tool_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/agent/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    department_search: str | None = None,  # noqa: ARG001
    model_search: str | None = None,  # noqa: ARG001
    tool_search: str | None = None,  # noqa: ARG001
    flag_search: str | None = None,  # noqa: ARG001
) -> list[UUID]:
    """Return every agent id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/agent/search`` does (search text,
    department/model/tool junction membership), but skips
    pagination/hydration. Facet-search params are accepted-but-ignored
    here since they don't affect the row set.
    """
    async with pool.acquire() as conn:
        ids, _total = await search_agents(
            conn,
            search=search,
            department_ids=filter_department_ids,
            model_ids=filter_model_ids,
            tool_ids=filter_tool_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
