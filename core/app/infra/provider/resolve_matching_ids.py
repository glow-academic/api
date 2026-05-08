"""Resolve provider ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``provider_ids``, the client sends
``all=true`` plus the same filter fields the search route accepts. The
server enumerates matching provider ids, applies any client-side
``excluded_ids``, then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_provider_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings — the only artifact-specific bit is which filter fields we
reverse-lookup (provider uses ``filter_model_ids`` → providers_resource
ids by walking model_artifact → provider_id, where persona uses
``scenario_ids`` → personas_resource ids).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.provider.search import search_providers

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; provider
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_provider_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/provider/search`` accepts. ``profile_id``
    # is here for parity but the search predicates aren't profile-
    # scoped today; left in the signature so future divergence
    # (e.g. "only show rows the profile can see") doesn't break callers.
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_model_ids: list[UUID] | None = None,
    filter_status: list[str] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/provider/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    department_search: str | None = None,
    model_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every provider id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/provider/search`` does (search
    text, model membership, status, department filter), but skips
    pagination/hydration. Facet-search params are accepted-but-ignored
    here since they don't affect the row set.
    """
    # Reverse lookup: filter_model_ids → providers_resource ids (same
    # shape the search impl uses; lifted here so the bulk path doesn't
    # need to import the private search build helper). Each model
    # artifact has a ``provider_id`` (a providers_resource id), which
    # is what ``search_providers`` accepts via the ``provider_ids``
    # junction filter.
    provider_resource_ids: list[UUID] | None = None

    if filter_model_ids:
        from app.tools.artifacts.model.get import (
            get_models as get_model_artifacts,
        )

        async with pool.acquire() as conn:
            model_artifacts = await get_model_artifacts(
                conn, filter_model_ids, providers=True,
            )
        pids: set[UUID] = set()
        for m in model_artifacts:
            if m.provider_id:
                pids.add(m.provider_id)
        if not pids:
            return []
        provider_resource_ids = list(pids)

    # Status filter → active_only flag + optional post-filter (mirrors
    # search_provider_impl). When BOTH ``active`` and ``inactive`` are
    # selected (or none), we drop the active filter entirely.
    active_only = True
    inactive_only = False
    if filter_status:
        has_active = any(s.lower() in ("active", "true") for s in filter_status)
        has_inactive = any(s.lower() in ("inactive", "false") for s in filter_status)
        if has_active and not has_inactive:
            active_only = True
        elif has_inactive and not has_active:
            active_only = False
            inactive_only = True
        else:
            active_only = False

    async with pool.acquire() as conn:
        ids, _total = await search_providers(
            conn,
            search=search,
            department_ids=filter_department_ids,
            provider_ids=provider_resource_ids,
            active_only=active_only,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )

        # ``inactive_only`` post-filter: search_providers' active_only
        # only knows "active=true" or "no filter"; to get just the
        # inactive rows we re-fetch with active_only=False and
        # subtract. Cheap enough at id-only level.
        if inactive_only:
            from app.tools.artifacts.provider.get import get_providers
            artifacts = await get_providers(conn, ids)
            ids = [a.id for a in artifacts if not a.active]

        return ids
