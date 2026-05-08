"""Resolve persona ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``ids``, the client sends ``all=true`` plus
the same filter fields the search route accepts. The server enumerates
matching persona ids, applies any client-side ``excluded_ids``, then
runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_persona_impl`` (which hydrates rows, computes facets, runs the
big-cache wrap). All we need is a list of UUIDs; the per-row permission
check inside the bulk impl filters out anything the user can't write to.

Keeping this small + focused (vs. reusing the full search build):
  - Bulk endpoints can diverge from search if predicates need to differ
    (e.g. delete might exclude rows referenced by active scenarios).
  - The audit shows the bulk endpoint as the actor, not search.
  - No facet aggregation / row hydration cost on a 10k-row delete.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.persona.search import search_personas
from app.tools.artifacts.scenario.get import get_scenarios

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; persona
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_persona_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/persona/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/persona/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    scenario_search: str | None = None,
    field_search: str | None = None,
    department_search: str | None = None,
    color_search: str | None = None,
    icon_search: str | None = None,
    voice_search: str | None = None,
    instruction_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every persona id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/persona/search`` does (search text,
    scenario membership, field membership, department filter), but skips
    pagination/hydration. Facet-search params are accepted-but-ignored
    here since they don't affect the row set.
    """
    # Reverse lookup: scenario_ids → personas_resource ids (same shape
    # the search impl uses; lifted here so the bulk path doesn't need
    # to import the private search build helper).
    personas_resource_ids: list[UUID] | None = None

    async with pool.acquire() as conn:
        if scenario_ids:
            scenarios = await get_scenarios(conn, scenario_ids, redis)
            pids: set[UUID] = set()
            for s in scenarios:
                pids.update(s.persona_ids)
            if not pids:
                return []
            personas_resource_ids = list(pids)

        # ``field_ids`` are parameter_fields_resource ids — direct junction filter.
        parameter_field_ids = field_ids

        ids, _total = await search_personas(
            conn,
            search=search,
            department_ids=filter_department_ids,
            parameter_field_ids=parameter_field_ids,
            persona_ids=personas_resource_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
