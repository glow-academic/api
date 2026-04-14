"""Resolve group_id — composes canonical entry black boxes.

Priority order:
  1. attempt_id → active attempt chat → group_id + controls
  2. test_id → latest test invocation → group_id + controls
  3. fallback → create fresh session + group
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from app.infra.auth.types import ResolveGroupApiResponse

# Canonical entry black boxes — attempts
from app.tools.entries.attempt.get import get_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_message.search import search_attempt_messages

# Canonical entry black boxes — groups
from app.tools.entries.groups.create import create_group

# Canonical entry black boxes — tests
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_groups.search import (
    search_test_invocation_groups,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)


async def resolve_group(
    conn: asyncpg.Connection,
    profiles_id: UUID | None,
    session_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    artifact_type: str | None = None,
) -> ResolveGroupApiResponse:
    """Resolve a group_id from attempt, test, or create fresh.

    Composes canonical entry black boxes — no inline SQL.
    """
    # Priority 1: attempt_id
    if attempt_id is not None:
        result = await _resolve_from_attempt(conn, attempt_id, profiles_id)
        if result is not None:
            return result

    # Priority 2: test_id
    if test_id is not None:
        result = await _resolve_from_test(conn, test_id)
        if result is not None:
            return result

    # Priority 3: fresh group
    return await _create_fresh_group(conn, profiles_id, session_id, artifact_type)


# ---------------------------------------------------------------------------
# Priority 1: Attempt resolution
# ---------------------------------------------------------------------------


async def _resolve_from_attempt(
    conn: asyncpg.Connection,
    attempt_id: UUID,
    profiles_id: UUID | None,
) -> ResolveGroupApiResponse | None:
    """Attempt → ownership check → chat state → group_id from current chat."""
    attempts = await get_attempts(conn, [attempt_id])
    chats, _total_count = await search_attempt_chats(
        conn,
        attempt_ids=[attempt_id],
        limit=1000,
    )

    if not attempts:
        return None

    attempt = attempts[0]

    # Ownership check
    if (
        profiles_id is None
        or attempt.profile_id is None
        or attempt.profile_id != profiles_id
    ):
        return None

    # Compute control state from chats
    all_chats_completed = all(c.completed for c in chats) if chats else False

    time_limit_seconds = sum(c.time_limit_seconds or 0 for c in chats)
    elapsed_seconds = 0
    now = datetime.now(UTC)
    for chat in chats:
        if chat.grade_time_taken is not None:
            elapsed_seconds += chat.grade_time_taken
        elif chat.chat_created_at and not chat.completed:
            created = chat.chat_created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            elapsed_seconds += max(int((now - created).total_seconds()), 0)

    is_active = True
    if time_limit_seconds > 0:
        infinite_mode = attempt.infinite_mode or False
        if infinite_mode:
            is_active = (time_limit_seconds - elapsed_seconds) > 0
        else:
            is_active = elapsed_seconds <= time_limit_seconds

    show_controls = is_active and not all_chats_completed
    if not show_controls:
        return None

    # Current chat (first incomplete, or last)
    current_chat = None
    for chat in chats:
        if not chat.completed:
            current_chat = chat
            break
    if current_chat is None and chats:
        current_chat = chats[-1]

    if current_chat is None or current_chat.group_id is None:
        return None

    current_chat_id = str(current_chat.chat_id)

    # Check if current chat has messages
    has_messages = False
    messages, _total_count_msgs = await search_attempt_messages(
        conn, chat_ids=[current_chat.chat_id], limit=1
    )
    has_messages = len(messages) > 0

    return ResolveGroupApiResponse(
        group_id=str(current_chat.group_id),
        show_controls=True,
        attempt_id=str(attempt_id),
        current_chat_id=current_chat_id,
        has_messages=has_messages,
    )


# ---------------------------------------------------------------------------
# Priority 2: Test invocation resolution
# ---------------------------------------------------------------------------


async def _resolve_from_test(
    conn: asyncpg.Connection,
    test_id: UUID,
) -> ResolveGroupApiResponse | None:
    """Test → latest invocation → group_id + has_runs_or_groups check."""
    invocations, _total_count = await search_test_invocation_entries_internal(
        conn, test_ids=[test_id], limit=1
    )

    if not invocations:
        return None

    invocation = invocations[0]

    if invocation.group_id is None:
        return None

    # Check if invocation has runs or groups
    runs, _tc_runs = await search_test_invocation_runs(
        conn,
        test_invocation_ids=[invocation.invocation_id],
        limit=1,
    )
    groups, _tc_groups = await search_test_invocation_groups(
        conn,
        test_invocation_ids=[invocation.invocation_id],
        limit=1,
    )
    has_runs_or_groups = len(runs) > 0 or len(groups) > 0

    return ResolveGroupApiResponse(
        group_id=str(invocation.group_id),
        show_controls=True,
        test_id=str(test_id),
        current_invocation_id=str(invocation.invocation_id),
        has_runs_or_groups=has_runs_or_groups,
    )


# ---------------------------------------------------------------------------
# Priority 3: Fresh group creation
# ---------------------------------------------------------------------------


async def _create_fresh_group(
    conn: asyncpg.Connection,
    profiles_id: UUID | None,
    session_id: UUID | None,
    artifact_type: str | None = None,
) -> ResolveGroupApiResponse:
    """Create a fresh group + initial name entry via canonical black boxes.

    Requires the caller's session. Session ownership stays at the boundary
    layer instead of silently creating a second session.
    """
    if session_id is None:
        if profiles_id is None:
            raise ValueError("Cannot create fresh group without a profile")
        raise ValueError("session_id is required to create a fresh group")

    # TODO: fix logic — artifact_type should always be provided by caller
    effective_artifact_type = artifact_type or "persona"
    group = await create_group(conn, session_id=session_id, artifact_type=effective_artifact_type)

    # Create initial name entry
    name = f"{artifact_type.title()} Generation" if artifact_type else ""
    if name:
        from app.tools.entries.group_names.create import create_group_name
        await create_group_name(conn, group_id=group.id, name=name, session_id=session_id)

    return ResolveGroupApiResponse(group_id=str(group.id))
