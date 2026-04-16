"""Attempt chat create logic — creates an attempt_chat from a chat template.

Called by:
  - POST /attempt/chat/create (HTTP)
  - The model as a tool call during /attempt/generate

Flow:
  1. resolve_profile_identity_context -> role, permissions
  2. Permission check — attempt:start (reuse existing permission)
  3. Create run + call
  4. Call black-box create_attempt_chat
  5. Create attempt_chat_bridge
  6. Refresh MVs
  7. Return { attempt_chat_id }
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import create_attempt_chat_bridge
from app.tools.entries.attempt_chat_bridge.refresh import refresh_attempt_chat_bridge
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run


class CreateAttemptChatApiRequest(BaseModel):
    """Create an attempt_chat from a chat template + resource IDs."""

    # Required
    attempt_id: UUID
    chat_id: UUID

    # Config flags
    title: str = ""
    position: int = 0
    time_limit: int | None = None
    negative_time: bool = False
    audio_enabled: bool = False
    text_enabled: bool = True
    hints_enabled: bool = False
    copy_paste_allowed: bool = True
    show_images: bool = False
    show_objectives: bool = False
    show_problem_statement: bool = False
    analyses_enabled: bool = False
    improvements_enabled: bool = False
    replacements_enabled: bool = False
    strengths_enabled: bool = False
    use_custom: bool = False
    use_previous: bool = False
    problem_statement_enabled: bool = False
    objectives_enabled: bool = False
    video_enabled: bool = False
    images_enabled: bool = False
    questions_enabled: bool = False

    # Resource connection IDs
    assistant_persona_ids: list[UUID] | None = None
    rubrics_ids: list[UUID] | None = None
    standards_ids: list[UUID] | None = None
    standard_groups_ids: list[UUID] | None = None
    departments_ids: list[UUID] | None = None
    personas_ids: list[UUID] | None = None
    problem_statements_ids: list[UUID] | None = None
    objectives_ids: list[UUID] | None = None
    questions_ids: list[UUID] | None = None
    options_ids: list[UUID] | None = None
    videos_ids: list[UUID] | None = None
    images_ids: list[UUID] | None = None
    documents_ids: list[UUID] | None = None
    parameter_fields_ids: list[UUID] | None = None
    names_ids: list[UUID] | None = None
    descriptions_ids: list[UUID] | None = None
    parameters_ids: list[UUID] | None = None

    # Ack
    idempotency_key: UUID | None = None
    accept: bool = True


class CreateAttemptChatApiResponse(BaseModel):
    attempt_chat_id: UUID
    idempotency_key: UUID | None = None


async def create_attempt_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: CreateAttemptChatApiRequest,
    soft: bool = False,
    **_kwargs,
) -> CreateAttemptChatApiResponse:
    """Create an attempt_chat entry within an attempt."""

    # Step 1: Profile context
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # Step 2: Permission check
    if not has_permission(profile.role_permissions, "attempt", "start"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create attempt chats.",
        )

    # Steps 3-5: Create run, call, attempt_chat, bridge in a transaction
    async with pool.acquire() as conn:
        async with conn.transaction():
            run_result = await create_run(
                conn,
                session_id=session_id,
                group_id=profile.group_id,
            )

            call = await create_call(
                conn,
                run_id=run_result.id,
                session_id=session_id,
            )

            result = await create_attempt_chat(
                conn,
                call_id=call.id,
                chat_id=request.chat_id,
                title=request.title,
                position=request.position,
                time_limit=request.time_limit,
                negative_time=request.negative_time,
                audio_enabled=request.audio_enabled,
                text_enabled=request.text_enabled,
                hints_enabled=request.hints_enabled,
                copy_paste_allowed=request.copy_paste_allowed,
                show_images=request.show_images,
                show_objectives=request.show_objectives,
                show_problem_statement=request.show_problem_statement,
                analyses_enabled=request.analyses_enabled,
                improvements_enabled=request.improvements_enabled,
                replacements_enabled=request.replacements_enabled,
                strengths_enabled=request.strengths_enabled,
                use_custom=request.use_custom,
                use_previous=request.use_previous,
                problem_statement_enabled=request.problem_statement_enabled,
                objectives_enabled=request.objectives_enabled,
                video_enabled=request.video_enabled,
                images_enabled=request.images_enabled,
                questions_enabled=request.questions_enabled,
                assistant_persona_ids=request.assistant_persona_ids,
                rubrics_ids=request.rubrics_ids,
                standards_ids=request.standards_ids,
                standard_groups_ids=request.standard_groups_ids,
                departments_ids=request.departments_ids,
                personas_ids=request.personas_ids,
                problem_statements_ids=request.problem_statements_ids,
                objectives_ids=request.objectives_ids,
                questions_ids=request.questions_ids,
                options_ids=request.options_ids,
                videos_ids=request.videos_ids,
                images_ids=request.images_ids,
                documents_ids=request.documents_ids,
                parameter_fields_ids=request.parameter_fields_ids,
                names_ids=request.names_ids,
                descriptions_ids=request.descriptions_ids,
                parameters_ids=request.parameters_ids,
                soft=soft,
            )

            await create_attempt_chat_bridge(
                conn,
                attempt_id=request.attempt_id,
                attempt_chat_id=result.id,
                session_id=session_id,
                soft=soft,
            )

    # Step 6: Refresh MVs
    async with pool.acquire() as conn:
        await refresh_attempt_chat(conn)
        await refresh_attempt_chat_bridge(conn)

    # Step 7: Return
    return CreateAttemptChatApiResponse(
        attempt_chat_id=result.id,
        idempotency_key=request.idempotency_key,
    )
