"""Resolve field ids matching a filter — shared by bulk write endpoints.

The bulk delete and bulk update routes accept a ``select-all-matching``
shape: instead of explicit ``field_ids``, the client sends ``all=true``
plus the same filter fields the search route accepts. The server
enumerates matching field ids, applies any client-side ``excluded_ids``,
then runs the existing per-row write flow.

This resolver is **id-only** — it deliberately does NOT call
``search_field_impl`` (which hydrates rows, computes facets, runs
the big-cache wrap). All we need is a list of UUIDs; the per-row
permission check inside the bulk impl filters out anything the user
can't write to.

Mirrors the persona/scenario resolvers field-for-field; see
``app/infra/persona/resolve_matching_ids.py`` for the canonical
docstrings — the only artifact-specific bits are which filter fields
we pass through to ``search_fields`` (field uses ``parameter_ids`` and
``persona_ids``, both of which the underlying tool already accepts as
junction filters — no reverse-lookup needed).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.field.search import search_fields

# Sentinel for "we want every matching row, not a page". The underlying
# tool takes ``limit_count: int`` so we just pass a big number; field
# datasets shouldn't realistically exceed this on a single tenant. If
# they do, we can switch to a paged loop here without touching callers.
_UNBOUNDED_LIMIT = 100_000


async def resolve_matching_field_ids(
    pool: asyncpg.Pool,
    redis: Redis,  # noqa: ARG001 — kept for signature parity with sibling resolvers
    *,
    profile_id: UUID,  # noqa: ARG001 — same parity rationale as ``redis``
    # Same filter fields ``/field/search`` accepts. ``profile_id`` is
    # here for parity but the search predicates aren't profile-scoped
    # today; left in the signature so future divergence (e.g. "only
    # show rows the profile can see") doesn't break callers.
    search: str | None = None,
    parameter_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet-search text params accepted for signature parity with
    # ``/field/search``. They narrow facet *option* lists in search;
    # they do NOT filter the row set. Bulk write endpoints accept
    # them (so the client can pass the URL state through unchanged)
    # but they're a no-op here. Listed explicitly rather than
    # **kwargs so misspelled fields fail loud.
    parameter_search: str | None = None,
    persona_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> list[UUID]:
    """Return every field id matching the row-filter predicates.

    Mirrors the row-narrowing that ``/field/search`` does (search text,
    parameter membership, persona membership, department filter), but
    skips pagination/hydration. Facet-search params are accepted-but-
    ignored here since they don't affect the row set.
    """
    del parameter_search, persona_search, department_search, flag_search

    async with pool.acquire() as conn:
        ids, _total = await search_fields(
            conn,
            search=search,
            department_ids=filter_department_ids,
            parameter_ids=parameter_ids,
            persona_ids=persona_ids,
            limit_count=_UNBOUNDED_LIMIT,
            offset_count=0,
        )
        return ids
