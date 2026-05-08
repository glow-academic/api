"""Shared mode scoping — resolves parameter_field_ids for video vs chat mode.

Used by chat context to determine which parameter fields, personas, and
documents are relevant for the current mode.

Rules (from scenario parameter flags):
  - video_parameter=True  → shows when video is enabled
  - scenario_parameter=True → shows in chat (scenario) mode
  - Dual-flagged (both true) → shows in both modes
  - Neither flag → shows in both modes (untagged)

For personas/documents, scoping is derived through:
  persona.parameter_field_ids → parameter_fields_resource.parameter_id
  → parameters_resource.video_parameter
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
    - Chat mode: parameters with scenario_parameter=True OR video_parameter=False
      (includes unflagged parameters like Temperament, Intensity)

    Returns parameter_field_ids for filtering personas, documents, and
    the parameter_fields section.
    """
    from app.tools.resources.parameter_fields.search import search_parameter_fields
    from app.tools.resources.parameters.search import search_parameters

    if video_mode:
        # Video mode: video_parameter=True (Concepts, Role, Location, Time)
        params = await search_parameters(
            conn, redis,
            video_parameter=True,
            department_ids=department_ids,
            limit_count=100,
            bypass_cache=True,
        )
    else:
        # Chat mode: everything NOT video-only
        # scenario_parameter=True gives Class, Crowdedness, Deadline, Location, Time
        # But we also need unflagged params (Temperament, Intensity) for chat personas
        # Simplest: get all parameters where video_parameter is False
        params = await search_parameters(
            conn, redis,
            video_parameter=False,
            department_ids=department_ids,
            limit_count=100,
            bypass_cache=True,
        )
        # Also include dual-flagged (scenario=True AND video=True) like Location, Time
        dual_params = await search_parameters(
            conn, redis,
            scenario_parameter=True,
            video_parameter=True,
            department_ids=department_ids,
            limit_count=100,
            bypass_cache=True,
        )
        # Dedupe
        seen = {p.parameter_id for p in params}
        for p in dual_params:
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
