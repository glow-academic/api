"""Resolve tool ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``tool_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching tool ids, applies any client-side ``excluded_ids``,
then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_tool_impl`` (which hydrates rows, computes facets, runs the
big-cache wrap). All we need is a list of UUIDs; the per-row permission
check inside the bulk impl filters out anything the user can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical doc
strings. Tool's row-narrowing filters today are just ``search``,
``filter_department_ids``, and (boolean facet) ``filter_creatable`` —
no reverse-lookup needed. ``filter_agent_ids`` is exposed as a facet
on the list page but is not yet wired into ``search_tools`` (see the
TODO in ``infra/tool/search.py``); the resolver accepts it for
signature parity and silently ignores it until the server side lands.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.tool.search import search_tools

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; tool
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_tool_ids(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Same filter fields ``/tool/search`` accepts. ``profile_id`` is
    # here for parity but the search predicates aren't profile-scoped
    # today; left in the signature so future divergence (e.g. "only
    # show rows the profile can see") doesn't break callers.
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_creatable: list[str] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/tool/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass URL state through unchanged) but
    # they're a no-op here. Listed explicitly rather than **kwargs so
    # misspelled fields fail loud.
    department_search: str | None = None,
    flag_search: str | None = None,
    agent_search: str | None = None,
) -> list[UUID]:
    """Return every tool id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/tool/search`` does (search text,
    department membership), but skips pagination/hydration. Facet-
    search params are accepted-but-ignored here since they don't
    affect the row set. ``filter_creatable`` / ``filter_agent_ids``
    aren't yet wired into ``search_tools`` — accepted for forward
    compatibility, ignored today.
    """
    # No reverse lookup needed for tool today. ``filter_department_ids``
    # are department resource ids — direct junction filter on
    # ``search_tools``.
    _ = filter_creatable  # accepted for signature parity; not wired yet
    _ = filter_agent_ids  # accepted for signature parity; not wired yet

    async with pool.acquire() as conn:
        ids, _total = await search_tools(
            conn,
            search=search,
            department_ids=filter_department_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
