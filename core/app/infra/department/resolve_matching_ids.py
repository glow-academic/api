"""Resolve department ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``department_ids``, the client sends
``all=true`` plus the same filter fields the search route accepts. The
server enumerates matching department ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_department_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bit is the filter set
(``/department/search`` only narrows on ``search``, with ``flag_search``
as a facet-only param). No reverse-lookup step is needed here since
``search_departments`` accepts no junction-id filters in the URL state.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.server_timing import timed
from app.tools.artifacts.department.search import search_departments

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; department
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_department_ids(
    pool: asyncpg.Pool,
    redis: Redis,  # noqa: ARG001 — kept for signature parity with persona/scenario
    *,
    profile_id: UUID,  # noqa: ARG001 — parity with persona/scenario; predicates aren't profile-scoped today
    # Same filter fields ``/department/search`` accepts.
    search: str | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/department/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    flag_search: str | None = None,  # noqa: ARG001
) -> list[UUID]:
    """Return every department id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/department/search`` does (search
    text), but skips pagination/hydration. Facet-search params are
    accepted-but-ignored here since they don't affect the row set.
    """
    with timed("query"):
     async with pool.acquire() as conn:
        ids, _total = await search_departments(
            conn,
            search=search,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
