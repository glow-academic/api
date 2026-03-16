"""Permission helpers for unified attempt detail API.

This module contains permission checking logic for the attempt detail endpoint.
Business logic for computing display values and derived fields is centralized here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.infra.attempt.types import (
    AvailableContinuationOptions,
    ChatData,
)
from app.tools.entries.attempt_chat.types import (
    GetAttemptChatResponse as ChatViewItem,
)

# Default styling for user messages
DEFAULT_USER_COLOR = "#6366f1"  # Indigo
DEFAULT_USER_ICON = "User"
DEFAULT_ASSISTANT_COLOR = "#06b6d4"  # Cyan
DEFAULT_ASSISTANT_ICON = "Bot"

ROLE_HIERARCHY: dict[str, int] = {
    "guest": 0,
    "member": 1,
    "instructional": 2,
    "admin": 3,
    "superadmin": 4,
}


def check_attempt_access(
    attempt_profile_id: UUID | None,
    request_profile_id: UUID,
    request_role: str | None = None,
    attempt_role: str | None = None,
) -> bool:
    """Check if the requesting user has access to the attempt.

    Access is granted if:
    1. The requesting user owns the attempt (profile IDs match), OR
    2. The requesting user's role is strictly higher than the attempt
       owner's role (instructional > member/guest, admin > instructional,
       superadmin > all). Guests and members can only see their own.

    Args:
        attempt_profile_id: The profile ID associated with the attempt.
        request_profile_id: The profile ID of the requesting user.
        request_role: The role of the requesting user.
        attempt_role: The role of the attempt owner.

    Returns:
        True if the user has access, False otherwise.
    """
    if attempt_profile_id is None:
        return False
    # Own attempt — always allowed
    if attempt_profile_id == request_profile_id:
        return True
    # Role-based access: higher roles can view lower-role attempts
    req_level = ROLE_HIERARCHY.get(request_role or "", 0)
    att_level = ROLE_HIERARCHY.get(attempt_role or "", 0)
    # guests and members (level <= 1) can only see their own
    if req_level <= 1:
        return False
    # superadmin can see everyone (including other superadmins)
    if req_level == ROLE_HIERARCHY["superadmin"]:
        return True
    return req_level > att_level


def compute_content_display(
    message_type: str | None,
    profile_name: str | None,
    persona_name: str | None,
    persona_color: str | None,
    persona_icon: str | None,
    is_own_attempt: bool = False,
) -> tuple[str | None, str, str]:
    """Compute display name, color, and icon for a content item.

    Business logic:
    - For 'query' (user) messages:
      - If viewing own attempt: show "You"
      - Otherwise: show profile_name
    - For 'response' (assistant) messages: use persona name/color/icon

    Args:
        message_type: 'query' or 'response'
        profile_name: The actor/user's name
        persona_name: The persona's name (for responses)
        persona_color: The persona's color (for responses)
        persona_icon: The persona's icon (for responses)
        is_own_attempt: True if the requesting user owns this attempt

    Returns:
        Tuple of (name, color, icon)
    """
    if message_type == "query":
        # Show "You" if viewing own attempt, otherwise show the profile name
        display_name = "You" if is_own_attempt else profile_name
        return (
            display_name,
            DEFAULT_USER_COLOR,
            DEFAULT_USER_ICON,
        )
    else:
        # Response message - use persona info
        return (
            persona_name,
            persona_color or DEFAULT_ASSISTANT_COLOR,
            persona_icon or DEFAULT_ASSISTANT_ICON,
        )


# =============================================================================
# Derived Field Computation (from chats)
# =============================================================================


def compute_chat_position_and_current(chats: list[ChatData]) -> None:
    """Compute position and is_current for each chat in-place.

    Position is the 0-based index in the list (ordered by created_at).
    is_current is True for the first incomplete chat, or the last chat if all complete.

    Args:
        chats: List of ChatData objects (mutated in-place)
    """
    current_found = False
    for i, chat in enumerate(chats):
        chat.position = i
        chat.is_current = False

    # Find first incomplete chat
    for chat in chats:
        if not chat.completed:
            chat.is_current = True
            current_found = True
            break

    # If all complete, mark last chat as current
    if not current_found and chats:
        chats[-1].is_current = True


def compute_attempt_aggregates(chats: list[ChatData]) -> dict:
    """Compute attempt-level aggregates from chats.

    Args:
        chats: List of ChatData objects

    Returns:
        Dict with: total_chats, completed_chats, total_score, all_passed, elapsed_seconds
    """
    total_chats = len(chats)
    completed_chats = sum(1 for c in chats if c.completed)

    # Sum scores from completed chats with grades
    total_score = 0.0
    all_passed = True
    elapsed_seconds = 0

    now = datetime.now(UTC)
    for chat in chats:
        if chat.grade and chat.grade.time_taken is not None:
            # Graded chat: use the recorded time_taken
            if chat.grade.score is not None:
                total_score += chat.grade.score
            if chat.grade.passed is False:
                all_passed = False
            elapsed_seconds += chat.grade.time_taken
        elif chat.created_at and not chat.completed:
            # Active ungraded chat: compute elapsed from created_at
            try:
                created = datetime.fromisoformat(chat.created_at)
                elapsed_seconds += max(int((now - created).total_seconds()), 0)
            except (ValueError, TypeError):
                pass
        elif chat.grade:
            # Graded but no time_taken recorded
            if chat.grade.score is not None:
                total_score += chat.grade.score
            if chat.grade.passed is False:
                all_passed = False

    # If no chats or no completed chats, all_passed is False
    if total_chats == 0 or completed_chats == 0:
        all_passed = False

    return {
        "total_chats": total_chats,
        "completed_chats": completed_chats,
        "total_score": total_score,
        "all_passed": all_passed,
        "elapsed_seconds": elapsed_seconds,
    }


def compute_total_possible_points(chats: list[ChatData]) -> float:
    """Compute total possible points from completed chats' grade total_points.

    Args:
        chats: List of ChatData objects

    Returns:
        Sum of rubric total_points for completed chats
    """
    total = 0.0
    for chat in chats:
        if chat.completed and chat.grade and chat.grade.total_points:
            total += chat.grade.total_points
    return total


def compute_percentage(total_score: float, total_possible: float) -> float:
    """Compute percentage score.

    Args:
        total_score: Total score achieved
        total_possible: Total possible points

    Returns:
        Percentage (0-100), or 0.0 if total_possible is 0
    """
    if total_possible > 0:
        return round((total_score / total_possible) * 100, 2)
    return 0.0


def compute_current_chat_index(chats: list[ChatData]) -> int:
    """Compute the current chat index (first incomplete, or last if all complete).

    Args:
        chats: List of ChatData objects

    Returns:
        Index of current chat
    """
    for i, chat in enumerate(chats):
        if not chat.completed:
            return i
    return len(chats) - 1 if chats else 0


def compute_total_time_limit(chats: list[ChatData]) -> int:
    """Compute total time limit from all chats' time_limit_seconds.

    Args:
        chats: List of ChatData objects (must have time_limit_seconds from view)

    Returns:
        Sum of time_limit_seconds for all chats (0 if no limit)
    """
    # Note: time_limit_seconds comes from ChatViewItem, not ChatData
    # This is called with the raw view items before transformation
    return 0  # Placeholder - actual sum done in get.py before transformation


def compute_achieved_standards(
    feedbacks: list[dict],
) -> list[dict]:
    """Derive achieved standards from feedbacks.

    A standard is "achieved" if it has feedback (i.e., was evaluated).

    Args:
        feedbacks: List of feedback dicts with 'standard_id' key

    Returns:
        List of dicts with 'standard_id' and 'achieved' keys
    """
    achieved = []
    for fb in feedbacks:
        standard_id = fb.get("standard_id")
        if standard_id:
            achieved.append(
                {
                    "standard_id": standard_id,
                    "achieved": True,
                }
            )
    return achieved


def compute_passed_standards(
    feedbacks: list[dict],
    standard_groups_meta: dict[UUID, dict],
    standards_meta: dict[UUID, dict],
) -> list[dict]:
    """Derive passed standards from feedbacks and standard_group pass_points.

    A standard is "passed" if its feedback total >= the standard_group's pass_points.

    Args:
        feedbacks: List of feedback dicts with 'standard_id' and 'total' keys
        standard_groups_meta: Dict mapping standard_group_id to metadata with 'pass_points'
        standards_meta: Dict mapping standard_id to metadata with 'standard_group_id'

    Returns:
        List of dicts with 'standard_id' and 'passed' keys
    """
    passed = []
    for fb in feedbacks:
        standard_id = fb.get("standard_id")
        total = fb.get("total") or 0.0

        if standard_id:
            # Look up standard_group_id from standards metadata
            std_meta = standards_meta.get(standard_id, {})
            sg_id = std_meta.get("standard_group_id")

            # Look up pass_points from standard_groups metadata
            pass_points = 0.0
            if sg_id:
                sg_meta = standard_groups_meta.get(sg_id, {})
                pass_points = sg_meta.get("pass_points") or 0.0

            passed.append(
                {
                    "standard_id": standard_id,
                    "passed": total >= pass_points,
                }
            )
    return passed


# =============================================================================
# Continuation Options (Use Previous)
# =============================================================================


def compute_continuation_options(
    current_chats: list[ChatViewItem],
    previous_chats: list[ChatViewItem],
    scenario_names: dict[str, str],
) -> AvailableContinuationOptions | None:
    """Compute available continuation options from previous attempt chats.

    Keyed by chat_entry_id (the parent template). For each chat_entry not yet
    completed in the current attempt, find the best graded attempt_chat from
    previous attempts to reuse via bridge.

    Algorithm:
    1. Build ordered chat_entry list from previous chats (preserves MV order)
    2. Filter out chat_entries already completed in current attempt
    3. For each remaining chat_entry, pick best graded chat (highest score)
    4. Build consecutive options: [first], [first, second], etc.
    5. Pareto filter dominated options

    Returns None if no options.
    """
    from app.infra.attempt.types import (
        AvailableContinuationOptions,
        ContinuationOption,
        PreviousChatOption,
    )

    # 1. Find completed chat_entry_ids in current attempt
    current_chat_entry_ids = {
        str(c.chat_entry_id) for c in current_chats if c.completed and c.chat_entry_id
    }

    # 2. Build ordered chat_entry list from previous chats, preserving MV order.
    #    Use first occurrence of each chat_entry_id to establish position.
    seen_entries: dict[str, int] = {}  # chat_entry_id -> position
    for chat in previous_chats:
        if not chat.chat_entry_id:
            continue
        ceid = str(chat.chat_entry_id)
        if ceid not in seen_entries:
            seen_entries[ceid] = len(seen_entries)

    # 3. Group previous graded chats by chat_entry_id (only remaining ones)
    prev_by_entry: dict[str, list[ChatViewItem]] = {}
    for chat in previous_chats:
        if not chat.chat_entry_id or chat.grade_score is None or not chat.completed:
            continue
        ceid = str(chat.chat_entry_id)
        if ceid in current_chat_entry_ids:
            continue
        prev_by_entry.setdefault(ceid, []).append(chat)

    if not prev_by_entry:
        return None

    # 4. Pick best per chat_entry (highest score, tiebreak: lowest time)
    best_per_entry: dict[str, ChatViewItem] = {}
    for ceid, chats_list in prev_by_entry.items():
        best = max(
            chats_list,
            key=lambda c: (
                c.grade_score if c.grade_score is not None else -1,
                -(c.grade_time_taken if c.grade_time_taken is not None else 999999),
            ),
        )
        best_per_entry[ceid] = best

    # 5. Order remaining entries by their position from the MV
    ordered_remaining = sorted(
        best_per_entry.items(),
        key=lambda pair: seen_entries.get(pair[0], 999),
    )

    # 6. Build PreviousChatOption list
    remaining_options: list[PreviousChatOption] = []
    for position, (ceid, chat) in enumerate(ordered_remaining):
        score = chat.grade_score
        time_taken = float(chat.grade_time_taken) if chat.grade_time_taken else 0.0
        # Use scenario_names keyed by scenario_id for display
        name = scenario_names.get(str(chat.scenario_id)) if chat.scenario_id else None

        remaining_options.append(
            PreviousChatOption(
                chat_entry_id=ceid,
                scenario_name=name,
                attempt_chat_id=str(chat.chat_id),
                score=score,
                percentage=None,
                time_taken=time_taken,
                position=position,
            )
        )

    if not remaining_options:
        return None

    # 7. Build sequential bundles: [0], [0,1], [0,1,2], ...
    options: list[ContinuationOption] = []
    for length in range(1, len(remaining_options) + 1):
        bundle = remaining_options[:length]
        total_score = sum(o.score or 0.0 for o in bundle)
        total_time = sum(o.time_taken or 0.0 for o in bundle)
        options.append(
            ContinuationOption(
                scenarios=bundle,
                total_score=total_score,
                total_percentage=None,
                total_time=total_time,
            )
        )

    # 8. Pareto filter: remove options dominated on both score AND time
    filtered: list[ContinuationOption] = []
    for opt in options:
        dominated = False
        for other in options:
            if other is opt:
                continue
            if (
                other.total_score >= opt.total_score
                and other.total_time <= opt.total_time
            ):
                if (
                    other.total_score > opt.total_score
                    or other.total_time < opt.total_time
                ):
                    dominated = True
                    break
        if not dominated:
            filtered.append(opt)

    if not filtered:
        return None

    return AvailableContinuationOptions(options=filtered)
