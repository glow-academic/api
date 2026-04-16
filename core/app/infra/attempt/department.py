"""Department resolution for attempt chat creation.

Auto-resolves the department for an attempt chat by intersecting the user's
departments with the chat template's departments.
"""

from __future__ import annotations

from uuid import UUID


def resolve_attempt_department(
    user_department_ids: list[UUID],
    user_primary_department_id: UUID | None,
    chat_department_ids: list[UUID],
) -> UUID | None:
    """Pick the department for this attempt chat.

    1. Intersect user's departments with the chat template's departments
    2. If user's primary is in the intersection, use it
    3. Otherwise, use the first match from the intersection
    4. If no intersection, return None (user shouldn't have access)
    """
    chat_dept_set = set(chat_department_ids)
    intersection = [d for d in user_department_ids if d in chat_dept_set]
    if not intersection:
        return None
    if user_primary_department_id in intersection:
        return user_primary_department_id
    return intersection[0]
