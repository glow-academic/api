"""Shared mode scoping — resolves parameter_field_ids for video vs chat mode.

Used by both chat context and scenario context to determine which
personas, documents, and parameter fields are relevant for the current mode.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis


async def resolve_mode_parameter_field_ids(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    video_mode: bool,
    department_ids: list[UUID] | None = None,
) -> list[UUID]:
    """Get parameter_field_ids relevant to the current mode.

    - Video mode: parameters with video_parameter=True
    - Chat mode: parameters with persona_parameter=True OR document_parameter=True

    Returns parameter_field_ids that can be used to filter personas and documents
    via their parameter_field_ids array overlap.
    """
    from app.tools.resources.parameters.search import search_parameters
    from app.tools.resources.parameter_fields.search import search_parameter_fields

    # Find parameters matching the mode
    if video_mode:
        params = await search_parameters(
            conn, redis,
            video_parameter=True,
            department_ids=department_ids,
            limit_count=100,
            bypass_cache=True,
        )
    else:
        # Chat mode: persona + document parameters
        persona_params = await search_parameters(
            conn, redis,
            persona_parameter=True,
            department_ids=department_ids,
            limit_count=100,
            bypass_cache=True,
        )
        document_params = await search_parameters(
            conn, redis,
            document_parameter=True,
            department_ids=department_ids,
            limit_count=100,
            bypass_cache=True,
        )
        # Dedupe by ID
        seen: set[UUID] = set()
        params = []
        for p in persona_params + document_params:
            if p.parameter_id not in seen:
                seen.add(p.parameter_id)
                params.append(p)

    if not params:
        return []

    param_ids = [p.parameter_id for p in params]

    # Find parameter_fields for those parameters
    pfs = await search_parameter_fields(
        conn, redis,
        parameter_ids=param_ids,
        limit_count=200,
        bypass_cache=True,
    )

    return [pf.id for pf in pfs]
