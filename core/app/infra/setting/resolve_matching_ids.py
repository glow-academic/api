"""Resolve setting ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``setting_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching setting ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_setting_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings. Setting has no reverse-lookup hop — every filter id is a
direct junction filter accepted by ``search_settings`` as-is, so the
resolver is a single tool call.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.setting.search import search_settings

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; setting
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_setting_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/setting/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    flag_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    system_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/setting/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    flag_search: str | None = None,
    provider_search: str | None = None,
    auth_search: str | None = None,
    system_search: str | None = None,
    department_search: str | None = None,
) -> list[UUID]:
    """Return every setting id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/setting/search`` does (search text,
    flag membership, provider/auth/system membership, department filter),
    but skips pagination/hydration. Facet-search params are accepted-but-
    ignored here since they don't affect the row set.
    """
    # No reverse-lookup hop required — every filter id below is a
    # direct junction filter ``search_settings`` accepts natively.
    async with pool.acquire() as conn:
        ids, _total = await search_settings(
            conn,
            search=search,
            department_ids=filter_department_ids,
            flag_ids=flag_ids,
            provider_ids=provider_ids,
            auth_ids=auth_ids,
            system_ids=system_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
