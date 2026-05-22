"""Resolve cohort ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``cohort_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching cohort ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_cohort_impl`` (which hydrates rows, computes facets, runs the
big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bits are which filter fields we
accept (cohort uses ``filter_profile_ids`` / ``filter_simulation_ids``
which are direct junction filters, no reverse lookup needed).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.server_timing import timed
from app.tools.artifacts.cohort.search import search_cohorts

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; cohort
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_cohort_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/cohort/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    filter_profile_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/cohort/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    profile_search: str | None = None,
    simulation_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every cohort id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/cohort/search`` does (search
    text, profile membership, simulation membership, department
    filter), but skips pagination/hydration. Facet-search params are
    accepted-but-ignored here since they don't affect the row set.
    """
    # Cohort uses direct junction filters: ``filter_profile_ids`` →
    # profiles_resource ids, ``filter_simulation_ids`` →
    # simulations_resource ids. No reverse lookup needed (unlike
    # persona/scenario which translate through scenario/simulation
    # membership).
    with timed("query"):
     async with pool.acquire() as conn:
        ids, _total = await search_cohorts(
            conn,
            search=search,
            department_ids=filter_department_ids,
            profile_ids=filter_profile_ids,
            simulation_ids=filter_simulation_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
