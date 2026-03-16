"""Resolve group_id — composes canonical entry black boxes.

Priority order:
  1. attempt_id → active attempt chat → group_id + controls
  2. test_id → latest test invocation → group_id + controls
  3. draft_id → draft entry → group_id
  4. fallback → create fresh session + group
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from app.infra.auth.types import ResolveGroupApiResponse

# Canonical entry black boxes — drafts
from app.tools.entries.agent_drafts.get import get_agent_drafts

# Canonical entry black boxes — attempts
from app.tools.entries.attempt.get import get_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_message.search import search_attempt_messages
from app.tools.entries.auth_drafts.get import get_auth_drafts
from app.tools.entries.chat_drafts.get import get_chat_drafts
from app.tools.entries.cohort_drafts.get import get_cohort_drafts
from app.tools.entries.department_drafts.get import get_department_drafts
from app.tools.entries.document_drafts.get import get_document_drafts
from app.tools.entries.eval_drafts.get import get_eval_drafts
from app.tools.entries.field_drafts.get import get_field_drafts

# Canonical entry black boxes — groups
from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation_drafts.get import get_invocation_drafts
from app.tools.entries.model_drafts.get import get_model_drafts
from app.tools.entries.parameter_drafts.get import get_parameter_drafts
from app.tools.entries.persona_drafts.get import get_persona_drafts
from app.tools.entries.profile_drafts.get import get_profile_drafts
from app.tools.entries.provider_drafts.get import get_provider_drafts
from app.tools.entries.rubric_drafts.get import get_rubric_drafts
from app.tools.entries.scenario_drafts.get import get_scenario_drafts
from app.tools.entries.setting_drafts.get import get_setting_drafts
from app.tools.entries.simulation_drafts.get import get_simulation_drafts

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
from app.tools.entries.tool_drafts.get import get_tool_drafts

# Draft function dispatch map: artifact_type → get_X_drafts(conn, ids)
_DRAFT_FN_MAP: dict[
    str,
    Callable[[asyncpg.Connection, list[UUID]], Coroutine],
] = {
    "agent": get_agent_drafts,
    "auth": get_auth_drafts,
    "chat": get_chat_drafts,
    "cohort": get_cohort_drafts,
    "department": get_department_drafts,
    "document": get_document_drafts,
    "eval": get_eval_drafts,
    "field": get_field_drafts,
    "invocation": get_invocation_drafts,
    "model": get_model_drafts,
    "parameter": get_parameter_drafts,
    "persona": get_persona_drafts,
    "profile": get_profile_drafts,
    "provider": get_provider_drafts,
    "rubric": get_rubric_drafts,
    "scenario": get_scenario_drafts,
    "setting": get_setting_drafts,
    "simulation": get_simulation_drafts,
    "tool": get_tool_drafts,
}


async def resolve_group(
    conn: asyncpg.Connection,
    profiles_id: UUID | None,
    session_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    draft_id: UUID | None = None,
    artifact_type: str | None = None,
) -> ResolveGroupApiResponse:
    """Resolve a group_id from attempt, test, draft, or create fresh.

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

    # Priority 3: draft_id
    if draft_id is not None:
        result = await _resolve_from_draft(conn, draft_id, artifact_type)
        if result is not None:
            return result

    # Priority 4: fresh group
    return await _create_fresh_group(conn, profiles_id, session_id)


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
# Priority 3: Draft resolution
# ---------------------------------------------------------------------------


async def _resolve_from_draft(
    conn: asyncpg.Connection,
    draft_id: UUID,
    artifact_type: str | None,
) -> ResolveGroupApiResponse | None:
    """Draft → look up group_id via the canonical draft get function."""
    if artifact_type and artifact_type in _DRAFT_FN_MAP:
        # Known type — dispatch directly
        draft_fn = _DRAFT_FN_MAP[artifact_type]
        drafts = await draft_fn(conn, [draft_id])
        if drafts:
            return ResolveGroupApiResponse(group_id=str(drafts[0].group_id))
    else:
        # Unknown type — try all draft functions until we find a match
        for draft_fn in _DRAFT_FN_MAP.values():
            drafts = await draft_fn(conn, [draft_id])
            if drafts:
                return ResolveGroupApiResponse(group_id=str(drafts[0].group_id))

    return None


# ---------------------------------------------------------------------------
# Priority 4: Fresh group creation
# ---------------------------------------------------------------------------


async def _create_fresh_group(
    conn: asyncpg.Connection,
    profiles_id: UUID | None,
    session_id: UUID | None,
) -> ResolveGroupApiResponse:
    """Create a fresh group via canonical black boxes.

    Requires the caller's session. Session ownership stays at the boundary
    layer instead of silently creating a second session.
    """
    if session_id is None:
        if profiles_id is None:
            raise ValueError("Cannot create fresh group without a profile")
        raise ValueError("session_id is required to create a fresh group")

    group = await create_group(conn, session_id=session_id)
    return ResolveGroupApiResponse(group_id=str(group.id))
