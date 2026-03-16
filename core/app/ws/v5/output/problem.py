"""Output: problem — create a problem/bug report entry."""

import uuid
from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.entries.append_call_event import append_call_event
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem as create_problem_entry
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("problem")  # type: ignore
async def problem_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "problem", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    session_id_str = data.get("session_id")
    if not profile_id_str or not session_id_str:
        await sio.emit(
            "problem_error", {"message": "Missing profile or session"}, room=sid
        )
        return

    try:
        pool = get_pool()
        redis = get_redis_client()
        profile_id = UUID(profile_id_str)
        session_id = UUID(session_id_str)

        identity = await resolve_profile_identity_context(pool, profile_id, redis)
        if not identity or not identity.profiles_id:
            await sio.emit(
                "problem_error", {"message": "Profile not found"}, room=sid
            )
            return

        async with pool.acquire() as conn:
            group_result = await create_group(conn, session_id=session_id)
            run_result = await create_run(
                conn, group_id=group_result.id, session_id=session_id
            )
            call_result = await create_call(
                conn, run_id=run_result.id, session_id=session_id
            )
            problem_result = await create_problem_entry(
                conn,
                session_id=session_id,
                call_id=call_result.id,
                type=data["type"],
                message=data["message"],
                profile_id=identity.profiles_id,
            )

        await invalidate_tags(["problems", "views", "activity"], redis=redis)

        await sio.emit(
            "problem_result",
            {
                "problem_id": str(problem_result.id),
                "success": True,
                "message": "Problem created successfully",
            },
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in problem output: {e}")
        await sio.emit(
            "problem_error", {"message": f"Failed to create problem: {e}"}, room=sid
        )
