"""Resolve scenario ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``scenario_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching scenario ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_scenario_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona resolver field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bits are which filter fields we
reverse-lookup (scenario uses ``simulation_ids`` → scenarios_resource
ids, where persona uses ``scenario_ids`` → personas_resource ids).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.scenario.search import search_scenarios
from app.tools.resources.simulations.get import get_simulations as get_simulations_resource

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; scenario
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_scenario_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/scenario/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    persona_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/scenario/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    persona_search: str | None = None,
    simulation_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every scenario id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/scenario/search`` does (search text,
    persona membership, simulation membership, department filter), but
    skips pagination/hydration. Facet-search params are accepted-but-
    ignored here since they don't affect the row set.
    """
    # Reverse lookup: simulation_ids → scenarios_resource ids (same
    # shape the search impl uses; lifted here so the bulk path doesn't
    # need to import the private search build helper).
    scenarios_resource_ids: list[UUID] | None = None

    async with pool.acquire() as conn:
        if simulation_ids:
            sims = await get_simulations_resource(conn, simulation_ids, redis)
            sids: set[UUID] = set()
            for s in sims:
                sids.update(s.scenario_ids or [])
            if not sids:
                return []
            scenarios_resource_ids = list(sids)

        # ``persona_ids`` are personas_resource ids — direct junction filter.

        ids, _total = await search_scenarios(
            conn,
            search=search,
            department_ids=filter_department_ids,
            persona_ids=persona_ids,
            scenario_ids=scenarios_resource_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
