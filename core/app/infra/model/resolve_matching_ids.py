"""Resolve model ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``model_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching model ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_model_impl`` (which hydrates rows, computes facets, runs the
big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona resolver field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bit is the ``filter_agent_ids``
reverse lookup (agent_artifact ids → models_resource ids via the
agent's models_junction), which mirrors the same hop ``/model/search``
performs.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.agent.get import get_agents as get_agent_artifacts
from app.tools.artifacts.model.search import search_models

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; model
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_model_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/model/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    filter_provider_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/model/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    provider_search: str | None = None,
    department_search: str | None = None,
    agent_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every model id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/model/search`` does (search text,
    provider membership, department filter, agent reverse-lookup), but
    skips pagination/hydration. Facet-search params are accepted-but-
    ignored here since they don't affect the row set.
    """
    # Reverse lookup: filter_agent_ids → models_resource ids (same
    # shape the search impl uses; lifted here so the bulk path doesn't
    # need to import the private search build helper).
    model_resource_ids: list[UUID] | None = None

    async with pool.acquire() as conn:
        if filter_agent_ids:
            agent_artifacts = await get_agent_artifacts(
                conn, filter_agent_ids, models=True,
            )
            mids: set[UUID] = set()
            for a in agent_artifacts:
                mids.update(a.model_ids or [])
            if not mids:
                return []
            model_resource_ids = list(mids)

        ids, _total = await search_models(
            conn,
            search=search,
            department_ids=filter_department_ids,
            provider_ids=filter_provider_ids,
            model_ids=model_resource_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
