"""Shared attempt workflow logic, transport-agnostic apart from emitted payload shape."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
from redis.asyncio import Redis

from app.infra.websocket.attempt_types import (
    AttemptAssistantProgressData,
    AttemptAudioEndedData,
    AttemptAudioReadyData,
    AttemptErrorData,
    AttemptProceedData,
    AttemptStoppedData,
    AttemptUserCompleteData,
    AttemptUserProgressData,
    AttemptUserReceivedCompleteData,
    AttemptUserReceivedProgressData,
    AttemptUserReceivedStartData,
    AttemptUserStartData,
    GenerateRequestData,
)
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.session_store import get_session_by_group_id
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ResolveProfileIdentityFn = Callable[..., Awaitable[Any]]

GENERATE_FLAG_TO_RESOURCE = {
    "generate_problem_statements": "problem_statements",
    "generate_objectives": "objectives",
    "generate_videos": "videos",
    "generate_images": "images",
    "generate_questions": "questions",
    "generate_names": "names",
    "generate_descriptions": "descriptions",
    "generate_personas": "personas",
    "generate_documents": "documents",
    "generate_options": "options",
    "generate_parameter_fields": "parameter_fields",
}

GENERATE_FLAG_TO_CONNECTION = {
    "generate_personas": "personas_ids",
    "generate_problem_statements": "problem_statements_ids",
    "generate_objectives": "objectives_ids",
    "generate_questions": "questions_ids",
    "generate_options": "options_ids",
    "generate_videos": "videos_ids",
    "generate_images": "images_ids",
    "generate_documents": "documents_ids",
    "generate_parameter_fields": "parameter_fields_ids",
}


async def user_progress_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Forward transcript progress to server/ layer."""
    sid = data.get("sid", "")
    chat_id = data.get("chat_id", "")
    if not sid or not chat_id:
        return

    await emit(
        [
            internal_event(
                "attempt_user_progress",
                AttemptUserProgressData(
                    sid=sid,
                    chat_id=chat_id,
                    item_id=data.get("item_id"),
                    transcript=data.get("transcript", ""),
                    rooms=data.get("rooms"),
                ).model_dump(mode="json"),
            )
        ]
    )


async def audio_session_start_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate generate_audio_session_start → attempt_audio_ready."""
    group_id = data.get("group_id")
    sid = data.get("sid")
    if not sid or not group_id:
        return
    session = get_session_by_group_id(group_id)
    chat_id = session.chat_id if session else group_id
    await emit(
        [
            internal_event(
                "attempt_audio_ready",
                AttemptAudioReadyData(
                    sid=sid,
                    chat_id=chat_id,
                    success=True,
                    message="Voice session ready",
                ).model_dump(mode="json"),
            )
        ]
    )


async def audio_delta_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate generate_audio_progress → attempt_assistant_progress(audio)."""
    group_id = data.get("group_id")
    if not group_id:
        return
    session = get_session_by_group_id(group_id)
    if not session:
        return
    audio_data = data.get("audio")
    if not audio_data:
        return
    await emit(
        [
            internal_event(
                "attempt_assistant_progress",
                AttemptAssistantProgressData(
                    sid=session.sid,
                    chat_id=session.chat_id,
                    content_type="audio",
                    audio=audio_data,
                ).model_dump(mode="json"),
            )
        ]
    )


async def audio_speech_start_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate generate_audio_user_speech_start → attempt_user_received_start."""
    group_id = data.get("group_id")
    if not group_id:
        return
    session = get_session_by_group_id(group_id)
    if not session:
        return
    item_id = data.get("item_id")
    if not item_id:
        return

    profile_id_str = await find_profile_by_socket(session.sid)
    session_id_str = await find_session_by_socket(session.sid)

    await emit(
        [
            internal_event(
                "attempt_user_received_start",
                AttemptUserReceivedStartData(
                    sid=session.sid,
                    chat_id=session.chat_id,
                    run_id=session.run_id,
                    profile_id=profile_id_str or "",
                    session_id=session_id_str,
                    item_id=item_id,
                ).model_dump(mode="json"),
            )
        ]
    )


async def audio_speech_delta_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate generate_audio_user_speech_delta → attempt_user_received_progress."""
    group_id = data.get("group_id")
    if not group_id:
        return
    session = get_session_by_group_id(group_id)
    if not session:
        return
    item_id = data.get("item_id")
    if not item_id:
        return

    await emit(
        [
            internal_event(
                "attempt_user_received_progress",
                AttemptUserReceivedProgressData(
                    sid=session.sid,
                    chat_id=session.chat_id,
                    item_id=item_id,
                    transcript=data.get("transcript", ""),
                ).model_dump(mode="json"),
            )
        ]
    )


async def audio_error_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate generate_audio_error → attempt_error."""
    group_id = data.get("group_id")
    if not group_id:
        return
    session = get_session_by_group_id(group_id)
    if not session:
        return
    await emit(
        [
            internal_event(
                "attempt_error",
                AttemptErrorData(
                    sid=session.sid,
                    error_type="audio",
                    message=data.get("error_message", "Unknown audio error"),
                    chat_id=session.chat_id,
                ).model_dump(mode="json"),
            )
        ]
    )


async def attempt_next_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    attempt_id: str,
    draft_id: str | None,
    profile_id: str,
    session_id: str,
    pool: asyncpg.Pool,
    redis: Redis | None = None,
    resolve_profile_identity_fn: ResolveProfileIdentityFn | None = None,
) -> None:
    """Delegate attempt_next → attempt_proceed with force_proceed=True."""
    from app.infra.profile_identity_context import resolve_profile_identity_context

    sid = data.get("sid", "")
    if not sid:
        return

    try:
        resolve_profile_identity_fn = (
            resolve_profile_identity_fn or resolve_profile_identity_context
        )
        identity = await resolve_profile_identity_fn(
            pool,
            uuid.UUID(profile_id),
            redis or Redis(),
            session_id=uuid.UUID(session_id),
            attempt_id=uuid.UUID(attempt_id),
        )
        group_id = identity.group_id if identity else None
        if group_id is None:
            raise ValueError(f"Group not found for attempt {attempt_id}")

        await emit(
            [
                internal_event(
                    "attempt_proceed",
                    AttemptProceedData(
                        sid=sid,
                        attempt_id=attempt_id,
                        group_id=str(group_id),
                        profile_id=profile_id,
                        session_id=session_id,
                        draft_id=draft_id,
                        force_proceed=True,
                    ).model_dump(mode="json"),
                )
            ]
        )
    except Exception as e:
        logger.exception(f"Error in attempt_next: {e}")
        await emit(
            [
                internal_event(
                    "attempt_error",
                    AttemptErrorData(
                        sid=sid,
                        error_type="next",
                        message=f"Failed to continue attempt: {e}",
                    ).model_dump(mode="json"),
                )
            ]
        )


async def user_start_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
) -> None:
    """Create user message shell and emit attempt_user_start."""
    sid = data.get("sid", "")
    chat_id = data.get("chat_id", "")
    run_id = data.get("run_id", "")
    session_id_str = data.get("session_id", "")
    if not chat_id or not run_id:
        return

    try:
        from app.tools.entries.attempt_message.create import (
            create_attempt_message,
        )
        from app.tools.entries.calls.create import create_call
        from app.tools.entries.messages.create import create_message

        run_id_uuid = uuid.UUID(run_id)
        session_id_uuid = uuid.UUID(session_id_str) if session_id_str else None

        async with pool.acquire() as conn:
            result = await create_message(
                conn,
                run_id=run_id_uuid,
                role="user",
            )
            call_result = await create_call(
                conn,
                run_id=run_id_uuid,
                session_id=session_id_uuid or uuid.UUID(int=0),
            )
            await create_attempt_message(
                conn,
                chat_id=uuid.UUID(chat_id),
                message_id=result.id,
                call_id=call_result.id,
            )

        await emit(
            [
                internal_event(
                    "attempt_user_start",
                    AttemptUserStartData(
                        sid=sid,
                        chat_id=chat_id,
                        message_id=str(result.id),
                        created_at=result.created_at.isoformat()
                        if result.created_at
                        else "",
                        item_id=data.get("item_id"),
                        rooms=data.get("rooms"),
                    ).model_dump(mode="json"),
                )
            ]
        )

    except Exception as e:
        logger.exception(f"Error in user_received_start: {e}")


async def audio_stop_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    cleanup_audio_session_fn: Callable[[Any], Awaitable[None]] | None = None,
) -> None:
    """Clean up audio session and emit attempt_audio_ended."""
    from app.infra.websocket.audio_lifecycle import cleanup_audio_session

    sid = data.get("sid")
    group_id = data.get("group_id")
    if not sid:
        return

    session = get_session_by_group_id(group_id) if group_id else None
    chat_id = session.chat_id if session else (group_id or "")
    if session:
        await (cleanup_audio_session_fn or cleanup_audio_session)(session)

    await emit(
        [
            internal_event(
                "attempt_audio_ended",
                AttemptAudioEndedData(
                    sid=sid,
                    chat_id=chat_id,
                    success=True,
                    message="Voice session stopped",
                ).model_dump(mode="json"),
            )
        ]
    )


async def audio_response_cancelled_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Handle barge-in cancellation: notify client + re-enter rate limit gate."""
    group_id = data.get("group_id")
    if not group_id:
        return
    session = get_session_by_group_id(group_id)
    if not session:
        return

    sid = session.sid
    chat_id = session.chat_id

    logger.info(f"Response cancelled (barge-in) - group_id={group_id}")

    await emit(
        [
            internal_event(
                "attempt_stopped",
                AttemptStoppedData(
                    sid=sid,
                    rooms=[sid, f"attempt_{chat_id}"],
                    chat_id=chat_id,
                    success=True,
                    message=None,
                ).model_dump(mode="json"),
            ),
            internal_event(
                "generate",
                {
                    "sid": sid,
                    "artifact_types": data.get("artifact_types")
                    or [{"name": data.get("artifact_type", ""), "operation": "get"}],
                    "group_id": group_id,
                    "metadata": data.get("metadata", {}),
                },
            ),
        ]
    )


async def user_complete_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
) -> None:
    """Write content to open user message and emit attempt_user_complete."""
    from app.tools.entries.attempt.search import search_attempts
    from app.tools.entries.attempt_content.create import (
        create_attempt_content as create_attempt_content_entry_internal,
    )
    from app.tools.entries.attempt_message.search import (
        search_attempt_messages,
    )
    from app.tools.entries.attempt_message_completion.create import (
        create_attempt_message_completion,
    )

    sid = data.get("sid", "")
    chat_id = data.get("chat_id", "")
    run_id = data.get("run_id", "")
    session_id_str = data.get("session_id", "")
    content = data.get("content", "")
    if not chat_id or not run_id or not content:
        return

    try:
        from app.tools.entries.calls.create import create_call

        run_id_uuid = uuid.UUID(run_id)
        session_id_uuid = uuid.UUID(session_id_str) if session_id_str else None

        async with pool.acquire() as conn:
            messages, _ = await search_attempt_messages(
                conn,
                chat_ids=[uuid.UUID(chat_id)],
                bypass_mv=True,
                limit=1000,
            )

            open_user_messages = [
                m for m in messages if m.type == "query" and not m.completed
            ]

            if not open_user_messages:
                logger.warning(f"No open user message found for chat={chat_id}")
                return

            message = open_user_messages[0]
            message_id = message.message_id
            created_at = message.created_at
            attempts, _ = await search_attempts(
                conn,
                attempt_ids=[message.attempt_id],
                bypass_mv=True,
                limit=1,
            )
            if not attempts:
                logger.warning(f"No attempt found for chat={chat_id}")
                return

            user_persona_id = attempts[0].user_persona_id

            content_call = await create_call(
                conn,
                run_id=run_id_uuid,
                session_id=session_id_uuid or uuid.UUID(int=0),
            )

            await create_attempt_content_entry_internal(
                conn,
                message_id=message_id,
                call_id=content_call.id,
                content=content,
                persona_id=user_persona_id,
            )

            call_result = await create_call(
                conn,
                run_id=run_id_uuid,
                session_id=session_id_uuid or uuid.UUID(int=0),
            )
            await create_attempt_message_completion(
                conn,
                attempt_message_id=message_id,
                call_id=call_result.id,
            )

        await emit(
            [
                internal_event(
                    "attempt_user_complete",
                    AttemptUserCompleteData(
                        sid=sid,
                        chat_id=chat_id,
                        message_id=str(message_id),
                        content=content,
                        created_at=created_at.isoformat() if created_at else "",
                        item_id=data.get("item_id"),
                        rooms=data.get("rooms"),
                    ).model_dump(mode="json"),
                )
            ]
        )

    except Exception as e:
        logger.exception(f"Error in user_received_complete: {e}")


async def attempt_message_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    redis: Redis | None = None,
    profile_id: str,
    session_id: str,
) -> None:
    """Persist a user attempt message and kick off generation when possible.

    This is intentionally simple for now:
    - always create/finalize the user-side message
    - if a socket-backed chat context exists, kick the generate pipeline
    - otherwise stop after the persisted user message
    """
    from app.infra.profile_identity_context import resolve_profile_identity_context
    from app.tools.entries.attempt_chat.search import search_attempt_chats
    from app.tools.entries.runs.create import create_run

    sid = data.get("sid", "")
    attempt_id = data.get("attempt_id")
    chat_id = data.get("chat_id")
    message = (data.get("message") or "").strip()
    if not attempt_id or not chat_id or not message:
        return

    profile_id_uuid = uuid.UUID(profile_id)
    session_id_uuid = uuid.UUID(session_id)
    attempt_chat_id = uuid.UUID(str(chat_id))
    attempt_id_uuid = uuid.UUID(str(attempt_id))

    identity = await resolve_profile_identity_context(
        pool,
        profile_id_uuid,
        redis or Redis(),
        session_id=session_id_uuid,
        attempt_id=attempt_id_uuid,
    )
    profiles_id = identity.profiles_id if identity else None
    group_id = identity.group_id if identity else None

    run_id = data.get("run_id")
    if run_id is None:
        if group_id is None:
            raise ValueError(f"Group not found for attempt {attempt_id}")
        async with pool.acquire() as conn:
            run = await create_run(
                conn,
                group_id=group_id,
                session_id=session_id_uuid,
                profiles_id=profiles_id,
            )
        run_id = str(run.id)

    await user_start_impl(
        {
            "sid": sid,
            "chat_id": str(attempt_chat_id),
            "run_id": run_id,
            "session_id": str(session_id_uuid),
            "item_id": data.get("item_id"),
            "rooms": data.get("rooms")
            or ([sid, f"attempt_{attempt_chat_id}"] if sid else []),
        },
        emit=emit,
        pool=pool,
    )
    await user_complete_impl(
        {
            "sid": sid,
            "chat_id": str(attempt_chat_id),
            "run_id": run_id,
            "session_id": str(session_id_uuid),
            "item_id": data.get("item_id"),
            "rooms": data.get("rooms")
            or ([sid, f"attempt_{attempt_chat_id}"] if sid else []),
            "content": message,
        },
        emit=emit,
        pool=pool,
    )

    async with pool.acquire() as conn:
        attempt_chats, _ = await search_attempt_chats(
            conn,
            attempt_chat_ids=[attempt_chat_id],
            bypass_mv=True,
            limit=1,
        )

    if not attempt_chats:
        return

    attempt_chat = attempt_chats[0]
    if not attempt_chat.chat_entry_id or not attempt_chat.department_id:
        return

    await emit_chat_generate_impl(
        emit=emit,
        pool=pool,
        sid=sid,
        profile_id=profile_id_uuid,
        profiles_id=profiles_id,
        session_id=session_id_uuid,
        attempt_id=attempt_id_uuid,
        chat_entry_id=attempt_chat.chat_entry_id,
        department_id=attempt_chat.department_id,
        attempt_chat_id=attempt_chat.chat_id,
        user_instructions=[message],
    )


async def speech_complete_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    session_id: uuid.UUID | None = None,
    audio_folder: str | None = None,
) -> None:
    """Save audio, create upload record, emit attempt_user_received_complete."""
    from pathlib import Path

    from app.infra.globals import AUDIO_FOLDER
    from app.tools.entries.uploads.create import create_upload

    group_id = data.get("group_id")
    if not group_id:
        return
    session = get_session_by_group_id(group_id)
    if not session:
        return

    transcript = data.get("transcript", "")
    if not transcript or not transcript.strip():
        return

    audio: bytes | None = data.get("audio")
    audio_upload_id: str | None = None
    if audio:
        try:
            file_uuid = uuid.uuid4()
            filename = f"{file_uuid}.pcm16"
            file_path = Path(audio_folder or AUDIO_FOLDER) / filename
            file_path.write_bytes(audio)

            relative_path = f"audio/{filename}"
            async with pool.acquire() as conn:
                upload_result = await create_upload(
                    conn,
                    session_id=session_id or uuid.UUID(int=0),
                    file_path=relative_path,
                    mime_type="audio/pcm16",
                    size=len(audio),
                )
            audio_upload_id = str(upload_result.id)
        except Exception as e:
            logger.exception(f"Failed to save user speech audio: {e}")

    await emit(
        [
            internal_event(
                "attempt_user_received_complete",
                AttemptUserReceivedCompleteData(
                    sid=session.sid,
                    chat_id=session.chat_id,
                    run_id=session.run_id,
                    content=transcript.strip(),
                    session_id=str(session_id) if session_id else None,
                    item_id=data.get("item_id"),
                    audio_upload_id=audio_upload_id,
                ).model_dump(mode="json"),
            )
        ]
    )


async def attempt_start_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    redis: Redis | None = None,
    profile_id: str,
    session_id: str,
) -> None:
    """Create attempt via black boxes, then delegate to attempt_proceed."""
    from app.infra.profile_identity_context import resolve_profile_identity_context
    from app.infra.attempt.client_types import AttemptStartPayload
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_home.create import create_attempt_home
    from app.tools.entries.attempt_practice.create import (
        create_attempt_practice,
    )
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.home.get import get_homes
    from app.tools.entries.home_chat.search import search_home_chats
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.practice.get import get_practices
    from app.tools.entries.practice_chat.search import search_practice_chats
    from app.tools.entries.runs.create import create_run
    from app.tools.resources.profile_personas.search import (
        search_profile_personas,
    )
    from app.tools.resources.simulations.get import get_simulations

    sid = data.get("sid", "")

    try:
        profile_id_uuid = uuid.UUID(profile_id)
        session_id_uuid = uuid.UUID(session_id)
        payload = AttemptStartPayload(**data)
    except Exception as e:
        logger.exception(f"Invalid attempt_start payload: {e}")
        return

    is_practice = payload.practice_id is not None

    try:
        identity = await resolve_profile_identity_context(
            pool,
            profile_id_uuid,
            redis or Redis(),
            bypass_cache=True,
            session_id=session_id_uuid,
        )
        profiles_resource_id = identity.profiles_id if identity else None
        group_id = identity.group_id if identity else None
        if not profiles_resource_id:
            raise ValueError(f"Profile resource not found for profile_id {profile_id}")
        if not group_id:
            raise ValueError("Group could not be resolved for attempt start")

        parent_id = payload.practice_id if is_practice else payload.home_id
        if not parent_id:
            raise ValueError("Either practice_id or home_id is required")

        async with pool.acquire() as conn:
            if is_practice:
                entries = await get_practices(conn, [parent_id])
            else:
                entries = await get_homes(conn, [parent_id])

        if not entries:
            raise ValueError(f"Parent entry not found: {parent_id}")
        parent_entry = entries[0]

        profile_ids = parent_entry.profile_ids or []
        if not profile_ids:
            raise ValueError("No profile personas found in parent")

        async with pool.acquire() as conn:
            profile_personas = await search_profile_personas(
                conn,
                redis=redis or Redis(),
                profile_ids=profile_ids,
                bypass_cache=True,
            )

        persona_id = None
        for pp in profile_personas:
            if pp.profile_id == profiles_resource_id:
                persona_id = pp.persona_id
                break

        if not persona_id:
            raise ValueError("No profile persona found matching this profile")

        async with pool.acquire() as conn:
            if is_practice:
                chat_entries = await search_practice_chats(
                    conn,
                    practice_ids=[payload.practice_id],
                    limit=1000,
                    bypass_mv=True,
                )
            else:
                chat_entries = await search_home_chats(
                    conn,
                    home_ids=[payload.home_id],
                    limit=1000,
                    bypass_mv=True,
                )
        num_chats = max(len(chat_entries), 1)

        simulation_ids = parent_entry.simulation_ids or []
        sim_name = None
        sim_desc = None
        if simulation_ids:
            async with pool.acquire() as conn:
                simulations = await get_simulations(
                    conn,
                    simulation_ids[:1],
                    redis or Redis(),
                    bypass_cache=True,
                )
            if simulations:
                sim_name = simulations[0].name
                sim_desc = simulations[0].description

        async with pool.acquire() as conn:
            async with conn.transaction():
                run_result = await create_run(
                    conn,
                    session_id=session_id_uuid,
                    group_id=group_id,
                    profiles_id=profiles_resource_id,
                )
                run_id = run_result.id

                persona_result = await create_persona(conn, personas_id=persona_id)

                call = await create_call(
                    conn,
                    run_id=run_id,
                    session_id=session_id_uuid,
                )
                attempt_result = await create_attempt(
                    conn,
                    call_id=call.id,
                    user_persona_id=persona_result.id,
                    profiles_id=profiles_resource_id,
                    name=sim_name or "",
                    description=sim_desc or "",
                    infinite_mode=payload.infinite_mode,
                    num_chats=num_chats,
                    practice=is_practice,
                )
                attempt_id = attempt_result.id

                if is_practice:
                    await create_attempt_practice(
                        conn,
                        attempt_id=attempt_id,
                        practice_id=payload.practice_id,
                        session_id=session_id_uuid,
                    )
                else:
                    await create_attempt_home(
                        conn,
                        attempt_id=attempt_id,
                        home_id=payload.home_id,
                        session_id=session_id_uuid,
                    )

        async with pool.acquire() as conn:
            await refresh_attempt(conn)
            await refresh_attempt_chat(conn)

        await emit(
            [
                internal_event(
                    "attempt_proceed",
                    AttemptProceedData(
                        sid=sid,
                        attempt_id=str(attempt_id),
                        group_id=str(group_id),
                        profile_id=str(profile_id_uuid),
                        session_id=str(session_id_uuid),
                        force_proceed=False,
                    ).model_dump(mode="json"),
                )
            ]
        )

    except Exception as e:
        logger.exception(f"Error in attempt_start: {e}")
        await emit(
            [
                internal_event(
                    "attempt_error",
                    AttemptErrorData(
                        sid=sid,
                        error_type="start",
                        message=f"Failed to start attempt: {e}",
                    ).model_dump(mode="json"),
                )
            ]
        )


async def emit_chat_generate_impl(
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    sid: str,
    profile_id: uuid.UUID,
    profiles_id: uuid.UUID | None,
    session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    chat_entry_id: uuid.UUID,
    department_id: uuid.UUID,
    attempt_chat_id: uuid.UUID | None,
    draft_id: uuid.UUID | None = None,
    resource_types: list[str] | None = None,
    user_instructions: list[str] | None = None,
    save: bool = True,
    chat_started_emitted: bool = False,
) -> None:
    """Create group + run, then emit to generate pipeline."""
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.runs.create import create_run

    resolved_resource_types = resource_types or [
        "personas",
        "scenarios",
        "parameters",
        "fields",
    ]

    async with pool.acquire() as conn:
        group_result = await create_group(conn, session_id=session_id)
        group_id = group_result.id

        run_result = await create_run(
            conn,
            session_id=session_id,
            group_id=group_id,
            profiles_id=profiles_id,
        )
        run_id = run_result.id

    await emit(
        [
            internal_event(
                "generate",
                GenerateRequestData(
                    sid=sid,
                    profile_id=str(profile_id),
                    profiles_id=str(profiles_id) if profiles_id else None,
                    session_id=str(session_id),
                    artifact_types=[{"name": "chat", "operation": "get"}],
                    artifact_id=str(chat_entry_id),
                    draft_id=str(draft_id) if draft_id else None,
                    resource_types=resolved_resource_types,
                    user_instructions=user_instructions,
                    save=save,
                    run_id=str(run_id),
                    group_id=str(group_id),
                    metadata={
                        "attempt_id": str(attempt_id),
                        "attempt_chat_id": str(attempt_chat_id)
                        if attempt_chat_id
                        else None,
                        "chat_started_emitted": chat_started_emitted,
                    },
                ).model_dump(mode="json"),
            )
        ]
    )


async def attempt_proceed_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    redis: Redis | None = None,
    profile_id: str,
    session_id: str,
    profiles_id: uuid.UUID | None = None,
) -> None:
    """Shared core: resolve context → check done → resolve chat → emit."""
    from app.infra.websocket.attempt_types import (
        AttemptEndedData,
        AttemptStartedData,
    )
    from app.tools.entries.attempt.get import get_attempts
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.create import create_attempt_chat
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat.search import search_attempt_chats
    from app.tools.entries.attempt_chat_bridge.create import (
        create_attempt_chat_bridge,
    )
    from app.tools.entries.attempt_chat_bridge.search import (
        search_attempt_chat_bridges,
    )
    from app.tools.entries.attempt_chat_completion.create import (
        create_attempt_chat_completion,
    )
    from app.tools.entries.attempt_home.search import search_attempt_homes
    from app.tools.entries.attempt_practice.search import (
        search_attempt_practice_entries,
    )
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.chat.get import get_chat_entries_internal
    from app.tools.entries.home_chat.search import search_home_chats
    from app.tools.entries.practice_chat.search import search_practice_chats
    from app.tools.entries.runs.create import create_run

    sid = data.get("sid", "")

    try:
        payload = AttemptProceedData(**data)
    except Exception as e:
        logger.exception(f"Invalid attempt_proceed payload: {e}")
        return

    try:
        profile_id_uuid = uuid.UUID(profile_id)
        attempt_id = uuid.UUID(payload.attempt_id)
        session_id_uuid = uuid.UUID(session_id)
        force_proceed = payload.force_proceed
        draft_id = uuid.UUID(payload.draft_id) if payload.draft_id else None
        completed_chat_id = (
            uuid.UUID(payload.completed_chat_id) if payload.completed_chat_id else None
        )
        complete_all = payload.complete_all

        async with pool.acquire() as conn:
            run_result = await create_run(
                conn,
                group_id=uuid.UUID(payload.group_id),
                session_id=session_id_uuid,
                profiles_id=profiles_id,
            )
            run_id = run_result.id

            call_result = await create_call(
                conn,
                run_id=run_id,
                session_id=session_id_uuid,
            )
            call_id = call_result.id

            if completed_chat_id:
                try:
                    await create_attempt_chat_completion(
                        conn,
                        chat_id=completed_chat_id,
                        call_id=call_id,
                    )
                except Exception:
                    logger.debug(f"Chat {completed_chat_id} already completed")

            if complete_all:
                bridges = await search_attempt_chat_bridges(
                    conn,
                    attempt_ids=[attempt_id],
                    limit=1000,
                    bypass_mv=True,
                )

                for bridge in bridges:
                    bridge_chat_id = bridge.attempt_chat_id
                    if bridge_chat_id:
                        try:
                            await create_attempt_chat_completion(
                                conn,
                                chat_id=bridge_chat_id,
                                call_id=call_id,
                            )
                        except Exception:
                            pass

                await refresh_attempt(conn)
                await refresh_attempt_chat(conn)

                await emit(
                    [
                        internal_event(
                            "attempt_ended",
                            AttemptEndedData(
                                sid=sid,
                                attempt_id=str(attempt_id),
                                success=True,
                                all_scenarios_complete=True,
                                message="All scenarios completed",
                            ).model_dump(mode="json"),
                        )
                    ]
                )
                return

        async with pool.acquire() as conn:
            attempt_entries = await get_attempts(conn, [attempt_id])
            if not attempt_entries:
                raise ValueError(f"Attempt not found: {attempt_id}")
            attempt_data = attempt_entries[0]

            num_chats = attempt_data.num_chats
            is_practice = attempt_data.practice
            attempt_department_id = attempt_data.department_id

            bridges = await search_attempt_chat_bridges(
                conn,
                attempt_ids=[attempt_id],
                limit=1000,
                bypass_mv=True,
            )
            completed_count = len(bridges)

            bridge_attempt_chat_ids = [b.attempt_chat_id for b in bridges]
            if bridge_attempt_chat_ids:
                attempt_chats, _ = await search_attempt_chats(
                    conn,
                    attempt_chat_ids=bridge_attempt_chat_ids,
                    bypass_mv=True,
                    limit=1000,
                )
                resolved_chat_ids = {ac.chat_entry_id for ac in attempt_chats}
            else:
                resolved_chat_ids = set()

            if is_practice:
                practice_entries = await search_attempt_practice_entries(
                    conn, attempt_ids=[attempt_id], bypass_mv=True
                )
                if not practice_entries:
                    raise ValueError("No practice link for this attempt")
                practice_id = practice_entries[0].practice_id
                parent_chat_links = await search_practice_chats(
                    conn, practice_ids=[practice_id], limit=1000, bypass_mv=True
                )
            else:
                home_entries = await search_attempt_homes(
                    conn, attempt_ids=[attempt_id], bypass_mv=True
                )
                if not home_entries:
                    raise ValueError("No home link for this attempt")
                home_id = home_entries[0].home_id
                parent_chat_links = await search_home_chats(
                    conn, home_ids=[home_id], limit=1000, bypass_mv=True
                )

            all_parent_chat_ids = [
                link.chat_id for link in parent_chat_links if link.chat_id
            ]

            all_chat_entries = await get_chat_entries_internal(
                conn,
                all_parent_chat_ids,
                bypass_cache=True,
            )

        remaining = [
            ce
            for ce in all_chat_entries
            if str(ce.get("chat_entry_id"))
            not in {str(rid) for rid in resolved_chat_ids}
        ]
        remaining.sort(
            key=lambda ce: (
                ce.get("position", 0) or 0,
                str(ce.get("created_at", "")),
            )
        )

        if not remaining or completed_count >= num_chats:
            await emit(
                [
                    internal_event(
                        "attempt_ended",
                        AttemptEndedData(
                            sid=sid,
                            attempt_id=str(attempt_id),
                            success=True,
                            all_scenarios_complete=True,
                            message="All scenarios completed",
                        ).model_dump(mode="json"),
                    )
                ]
            )
            return

        next_chat = remaining[0]
        chat_entry_id = uuid.UUID(str(next_chat.get("chat_entry_id")))

        chat_department_ids = next_chat.get("department_ids") or []
        if len(chat_department_ids) == 1:
            department_id = uuid.UUID(str(chat_department_ids[0]))
        elif attempt_department_id:
            department_id = uuid.UUID(str(attempt_department_id))
        else:
            await emit(
                [
                    internal_event(
                        "attempt_error",
                        AttemptErrorData(
                            sid=sid,
                            error_type="proceed",
                            message="No department could be resolved for this chat",
                        ).model_dump(mode="json"),
                    )
                ]
            )
            return

        resource_types_to_generate: list[str] = []
        for flag_name, resource_type in GENERATE_FLAG_TO_RESOURCE.items():
            if next_chat.get(flag_name, False):
                resource_types_to_generate.append(resource_type)

        needs_generation = len(resource_types_to_generate) > 0
        has_user_choice = bool(next_chat.get("use_custom")) or bool(
            next_chat.get("use_previous")
        )

        if has_user_choice and not force_proceed:
            await emit(
                [
                    internal_event(
                        "attempt_started",
                        AttemptStartedData(
                            sid=sid,
                            attempt_id=str(attempt_id),
                            chat_entry_id=str(chat_entry_id),
                        ).model_dump(mode="json"),
                    )
                ]
            )
            return

        request_dict: dict[str, Any] = {
            "chat_id": str(chat_entry_id),
            "title": next_chat.get("name") or "",
            "position": next_chat.get("position", 0),
            "time_limit": next_chat.get("time_limit"),
            "negative_time": next_chat.get("negative_time", False),
            "audio_enabled": next_chat.get("audio_enabled", True),
            "text_enabled": next_chat.get("text_enabled", True),
            "hints_enabled": next_chat.get("hints_enabled", False),
            "copy_paste_allowed": next_chat.get("copy_paste_allowed", True),
            "show_images": next_chat.get("show_images", True),
            "show_objectives": next_chat.get("show_objectives", True),
            "show_problem_statement": next_chat.get("show_problem_statement", True),
            "analyses_enabled": next_chat.get("analyses_enabled", True),
            "improvements_enabled": next_chat.get("improvements_enabled", True),
            "replacements_enabled": next_chat.get("replacements_enabled", True),
            "strengths_enabled": next_chat.get("strengths_enabled", True),
            "use_custom": next_chat.get("use_custom", False),
            "use_previous": next_chat.get("use_previous", False),
            "problem_statement_enabled": next_chat.get(
                "problem_statement_enabled", True
            ),
            "objectives_enabled": next_chat.get("objectives_enabled", True),
            "video_enabled": next_chat.get("video_enabled", False),
            "images_enabled": next_chat.get("images_enabled", False),
            "questions_enabled": next_chat.get("questions_enabled", False),
        }

        rubric_ids = next_chat.get("rubric_ids") or []
        if rubric_ids:
            request_dict["rubrics_ids"] = [str(rid) for rid in rubric_ids]

        standard_ids = next_chat.get("standard_ids") or []
        if standard_ids:
            request_dict["standards_ids"] = [str(sid_val) for sid_val in standard_ids]

        standard_group_ids = next_chat.get("standard_group_ids") or []
        if standard_group_ids:
            request_dict["standard_groups_ids"] = [
                str(sgid) for sgid in standard_group_ids
            ]

        department_ids_list = next_chat.get("department_ids") or []
        if department_ids_list:
            request_dict["departments_ids"] = [str(did) for did in department_ids_list]

        for gen_flag, conn_param in GENERATE_FLAG_TO_CONNECTION.items():
            if not next_chat.get(gen_flag, False):
                chat_mv_key = {
                    "personas_ids": "persona_ids",
                    "problem_statements_ids": "problem_statement_ids",
                    "objectives_ids": "objective_ids",
                    "questions_ids": "question_ids",
                    "options_ids": "option_ids",
                    "videos_ids": "video_ids",
                    "images_ids": "image_ids",
                    "documents_ids": "document_ids",
                    "parameter_fields_ids": "parameter_field_ids",
                }.get(conn_param, conn_param)

                ids_from_chat = next_chat.get(chat_mv_key) or []
                if ids_from_chat:
                    request_dict[conn_param] = [str(cid) for cid in ids_from_chat]

        group_id = uuid.UUID(payload.group_id)

        def _uuids(key: str) -> list[uuid.UUID] | None:
            vals = request_dict.get(key)
            return [uuid.UUID(v) for v in vals] if vals else None

        async with pool.acquire() as conn:
            async with conn.transaction():
                call = await create_call(
                    conn,
                    run_id=run_id,
                    session_id=session_id_uuid,
                )
                chat_result = await create_attempt_chat(
                    conn,
                    call_id=call.id,
                    group_id=group_id,
                    chat_id=chat_entry_id,
                    title=request_dict.get("title", ""),
                    position=request_dict.get("position", 0),
                    time_limit=request_dict.get("time_limit"),
                    negative_time=request_dict.get("negative_time", False),
                    audio_enabled=request_dict.get("audio_enabled", True),
                    text_enabled=request_dict.get("text_enabled", True),
                    hints_enabled=request_dict.get("hints_enabled", False),
                    copy_paste_allowed=request_dict.get("copy_paste_allowed", True),
                    show_images=request_dict.get("show_images", True),
                    show_objectives=request_dict.get("show_objectives", True),
                    show_problem_statement=request_dict.get(
                        "show_problem_statement", True
                    ),
                    analyses_enabled=request_dict.get("analyses_enabled", True),
                    improvements_enabled=request_dict.get("improvements_enabled", True),
                    replacements_enabled=request_dict.get("replacements_enabled", True),
                    strengths_enabled=request_dict.get("strengths_enabled", True),
                    use_custom=request_dict.get("use_custom", False),
                    use_previous=request_dict.get("use_previous", False),
                    problem_statement_enabled=request_dict.get(
                        "problem_statement_enabled", True
                    ),
                    objectives_enabled=request_dict.get("objectives_enabled", True),
                    video_enabled=request_dict.get("video_enabled", False),
                    images_enabled=request_dict.get("images_enabled", False),
                    questions_enabled=request_dict.get("questions_enabled", False),
                    rubrics_ids=_uuids("rubrics_ids"),
                    standards_ids=_uuids("standards_ids"),
                    standard_groups_ids=_uuids("standard_groups_ids"),
                    departments_ids=_uuids("departments_ids"),
                    personas_ids=_uuids("personas_ids"),
                    problem_statements_ids=_uuids("problem_statements_ids"),
                    objectives_ids=_uuids("objectives_ids"),
                    questions_ids=_uuids("questions_ids"),
                    options_ids=_uuids("options_ids"),
                    videos_ids=_uuids("videos_ids"),
                    images_ids=_uuids("images_ids"),
                    documents_ids=_uuids("documents_ids"),
                    parameter_fields_ids=_uuids("parameter_fields_ids"),
                )
                attempt_chat_id = chat_result.id

                await create_attempt_chat_bridge(
                    conn,
                    attempt_id=attempt_id,
                    attempt_chat_id=attempt_chat_id,
                    session_id=session_id_uuid,
                )

        await emit(
            [
                internal_event(
                    "attempt_chat_started",
                    {
                        "sid": sid,
                        "attempt_id": str(attempt_id),
                        "chat_id": str(attempt_chat_id),
                        "rooms": [sid, f"attempt_{attempt_chat_id}"] if sid else None,
                    },
                )
            ]
        )

        if needs_generation:
            await emit_chat_generate_impl(
                emit=emit,
                pool=pool,
                sid=sid,
                profile_id=profile_id_uuid,
                profiles_id=profiles_id,
                session_id=session_id_uuid,
                attempt_id=attempt_id,
                chat_entry_id=chat_entry_id,
                department_id=department_id,
                attempt_chat_id=attempt_chat_id,
                draft_id=draft_id,
                resource_types=resource_types_to_generate,
                chat_started_emitted=True,
            )
        else:
            async with pool.acquire() as conn:
                await refresh_attempt(conn)
                await refresh_attempt_chat(conn)

    except Exception as e:
        logger.exception(f"Error in attempt_proceed: {e}")
        await emit(
            [
                internal_event(
                    "attempt_error",
                    AttemptErrorData(
                        sid=sid,
                        error_type="proceed",
                        message=f"Failed to proceed: {e}",
                    ).model_dump(mode="json"),
                )
            ]
        )
