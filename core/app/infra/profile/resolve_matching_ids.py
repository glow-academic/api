"""Resolve profile ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``profile_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching profile ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_profile_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bits are the filter-field set
(profile uses ``cohort_ids`` directly as junction filter, no reverse
lookup needed) and ``role_filter`` which is a role *name* and must be
resolved to ``role_ids`` (mirroring ``search_profile_impl``).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.roles.get import get_roles

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; profile
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_profile_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/profile/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    cohort_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    role_filter: str | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/profile/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    cohort_search: str | None = None,
    department_search: str | None = None,
    role_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every profile id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/profile/search`` does (search
    text, cohort membership, department filter, role-name filter), but
    skips pagination/hydration. Facet-search params are accepted-but-
    ignored here since they don't affect the row set.
    """
    # ``role_filter`` is a role *name* (not a UUID) — same shape the
    # search impl uses. Resolve to ``role_ids`` here so the bulk path
    # doesn't need to import the private search build helper.
    role_ids_filter: list[UUID] | None = None

    async with pool.acquire() as conn:
        if role_filter:
            all_roles = await get_roles(pool, None, redis)
            role_ids_filter = [r.id for r in all_roles if r.name == role_filter]
            if not role_ids_filter:
                # The named role doesn't exist (or isn't visible) — no
                # rows can match. Return empty rather than passing
                # ``None`` (which would skip the role filter entirely).
                return []

        # ``cohort_ids`` are cohorts_resource ids — direct junction filter.

        ids, _total = await search_profiles(
            conn,
            search=search,
            department_ids=filter_department_ids,
            cohort_ids=cohort_ids,
            role_ids=role_ids_filter,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
