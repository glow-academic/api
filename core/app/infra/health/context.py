"""Resolve health context — black-box tools only.

Health detail fetches hourly service health and system metrics from MVs.
Uses health_mv and metrics_mv via MV search tools.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext
from app.tools.entries.health.search import search_health
from app.tools.entries.metrics.search import search_metrics


async def resolve_health_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    service: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_limit: int = 168,
    page_offset: int = 0,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve health context for get.py.

    Entries:
      - health: hourly service health rows from health_mv
      - metrics: hourly system metrics rows from metrics_mv

    Resources: (none — health has no resource hydration)
    """

    # ── Phase 1: Fetch health + metrics in parallel ────────────────
    async def _fetch_health() -> list:
        async with pool.acquire() as c:
            return await search_health(
                c,
                service=service,
                date_from=date_from,
                date_to=date_to,
                limit=page_limit,
                offset=page_offset,
            )

    async def _fetch_metrics() -> list:
        async with pool.acquire() as c:
            return await search_metrics(
                c,
                date_from=date_from,
                date_to=date_to,
                limit=page_limit,
                offset=page_offset,
            )

    health, metrics = await asyncio.gather(
        _fetch_health(),
        _fetch_metrics(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,
        draft_version=None,
        entries={
            "health": health,
            "metrics": metrics,
        },
        resources={},
    )
