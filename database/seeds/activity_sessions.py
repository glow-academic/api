"""Shared analytical session/activity seed helpers.

These helpers keep dashboard seeds aligned with the app's canonical
write path: sessions are real ``sessions_entry`` rows, activity/logins
are linked through their profile connection tables, and problems are
created through group -> run -> call -> problem.
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg

from app.tools.entries.activity.create import create_activity
from app.tools.entries.calls.create import create_call
from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.grants.create import create_grant
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.logins.create import create_login
from app.tools.entries.problems.create import create_problem
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from database.seeds.ids import sid


@dataclass(frozen=True)
class SeedActivitySession:
    session_id: UUID


async def _ignore_existing(coro: Awaitable[Any]) -> UUID | None:
    """Run a canonical create helper and tolerate deterministic replays."""
    try:
        result = await coro
    except asyncpg.UniqueViolationError:
        return None
    return result.id


async def ensure_activity_session(
    conn: asyncpg.Connection,
    *,
    slug: str,
    profile_id: UUID,
    label: str,
    include_problem: bool = False,
    include_grant: bool = False,
    include_emulation: bool = False,
) -> SeedActivitySession:
    """Create a real session plus Activity-page metadata.

    All writes go through existing entry create helpers. The deterministic
    IDs make the seed repeatable; duplicate rows from a prior run are
    treated as already present.
    """
    session_id = sid(f"{slug}/session")
    activity_id = sid(f"{slug}/activity")
    login_id = sid(f"{slug}/login")

    await _ignore_existing(
        create_session(conn, profile_id=profile_id, id=session_id)
    )
    await _ignore_existing(
        create_activity(
            conn,
            session_id=session_id,
            profile_id=profile_id,
            id=activity_id,
        )
    )
    await _ignore_existing(
        create_login(
            conn,
            session_id=session_id,
            profile_id=profile_id,
            id=login_id,
        )
    )

    grant_id: UUID | None = None
    if include_grant or include_emulation:
        grant_id = sid(f"{slug}/grant")
        await _ignore_existing(
            create_grant(
                conn,
                session_id=session_id,
                profiles_id=profile_id,
                id=grant_id,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )

    if include_emulation and grant_id is not None:
        await _ignore_existing(
            create_emulation(
                conn,
                grant_id=grant_id,
                session_id=session_id,
                profile_id=profile_id,
                id=sid(f"{slug}/emulation"),
            )
        )

    if include_problem:
        group_id = sid(f"{slug}/problem-group")
        run_id = sid(f"{slug}/problem-run")
        call_id = sid(f"{slug}/problem-call")
        await _ignore_existing(
            create_group(
                conn,
                session_id=session_id,
                artifact_type="activity",
                id=group_id,
            )
        )
        await _ignore_existing(
            create_group_name(
                conn,
                group_id=group_id,
                name=f"{label} issue",
                session_id=session_id,
                id=sid(f"{slug}/problem-group-name"),
                generated=True,
            )
        )
        await _ignore_existing(
            create_run(conn, group_id=group_id, session_id=session_id, id=run_id)
        )
        await _ignore_existing(
            create_call(conn, run_id=run_id, session_id=session_id, id=call_id)
        )
        await _ignore_existing(
            create_problem(
                conn,
                session_id=session_id,
                call_id=call_id,
                type="bug",
                artifact_type="activity",
                id=sid(f"{slug}/problem"),
                message=f"Seeded issue while reviewing {label}.",
                profile_id=profile_id,
            )
        )

    return SeedActivitySession(session_id=session_id)
