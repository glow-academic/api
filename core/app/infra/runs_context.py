"""Resolve runs context — today's runs for a profile.

Given a profile_id, fetches today's runs.

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from app.tools.entries.runs.search import RunViewItem, search_runs


@dataclass(frozen=True)
class RunsContext:
    """Today's runs for a profile."""

    items: list[RunViewItem]
    total_count: int


async def resolve_runs_context(
    pool: asyncpg.Pool,
    *,
    profile_id: UUID,
    group_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> RunsContext:
    """Resolve today's runs for a profile.

    Defaults date_from and date_to to today if not provided.
    """
    now = datetime.now(UTC)
    start = date_from or now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = date_to or now

    async with pool.acquire() as conn:
        items, total_count = await search_runs(
            conn,
            group_ids=[group_id] if group_id else None,
            profiles_ids=[profile_id],
            date_from=start,
            date_to=end,
        )

    return RunsContext(
        items=items,
        total_count=total_count,
    )
