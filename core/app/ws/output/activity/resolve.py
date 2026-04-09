"""Output: activity.resolve — resolve a problem entry."""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("activity.resolve")  # type: ignore
async def activity_resolve_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "activity.resolve", data, UPLOAD_FOLDER)

    session_id_str = data.get("session_id")
    if not session_id_str:
        await sio.emit("activity.resolve.failed", {"message": "Missing session"}, room=sid)
        return

    try:
        pool = get_pool()
        redis = get_redis_client()
        session_id = UUID(session_id_str)
        problem_id = UUID(data["problem_id"])
        resolved = data.get("resolved", True)

        async with pool.acquire() as conn:
            group_result = await create_group(conn, session_id=session_id)
            run_result = await create_run(conn, group_id=group_result.id, session_id=session_id)
            call_result = await create_call(conn, run_id=run_result.id, session_id=session_id)
            await create_resolve(
                conn, problem_id=problem_id, resolved=resolved, call_id=call_result.id,
            )

        await invalidate_tags(["problems", "views", "activity", "summary"], redis=redis)

        await sio.emit(
            "activity.resolve.completed",
            {
                "problem_id": str(problem_id),
                "resolved": resolved,
                "updated_at": datetime.now().isoformat(),
            },
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in activity.resolve output: {e}")
        await sio.emit("activity.resolve.failed", {"message": f"Failed to resolve: {e}"}, room=sid)
