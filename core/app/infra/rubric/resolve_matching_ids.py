"""Resolve rubric ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``rubric_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching rubric ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_rubric_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona resolver field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bits are which filter fields are
accepted (rubric uses ``filter_simulation_ids`` directly via
``search_rubrics``, no reverse lookup needed; ``filter_department_ids``
also passes through directly).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.rubric.search import search_rubrics

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; rubric
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_rubric_ids(
    pool: asyncpg.Pool,
    redis: Redis,  # noqa: ARG001 — kept for signature parity with peers
    *,
    profile_id: UUID,  # noqa: ARG001 — kept for signature parity
    # Same filter fields ``/rubric/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/rubric/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    department_search: str | None = None,  # noqa: ARG001
    simulation_search: str | None = None,  # noqa: ARG001
    flag_search: str | None = None,  # noqa: ARG001
) -> list[UUID]:
    """Return every rubric id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/rubric/search`` does (search text,
    department filter, simulation membership), but skips
    pagination/hydration. Facet-search params are accepted-but-ignored
    here since they don't affect the row set.
    """
    async with pool.acquire() as conn:
        # ``filter_simulation_ids`` are passed straight through —
        # ``search_rubrics`` already supports the simulation predicate
        # via scenario_rubrics_resource. No reverse hop needed.
        ids, _total = await search_rubrics(
            conn,
            search=search,
            department_ids=filter_department_ids,
            simulation_ids=filter_simulation_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
