"""Output: generate_run_complete

Broadcasts the event to clients AND triggers run_complete_impl to:
  - Persist assistant_output text to disk + DB
  - Save token counts
  - Handle multi-agent coordination (triage, promote, grade)
"""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.run_complete_impl import run_complete_impl
from app.infra.websocket.socket_event import make_emit
from app.utils.logging.db_logger import get_logger

internal_sio = get_internal_sio()
logger = get_logger(__name__)


@internal_sio.on("generate_run_complete")  # type: ignore
async def generate_run_complete_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "generate_run_complete", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("generate_run_complete", data, room=room)

    # Persist assistant text, token counts, and handle multi-agent coordination
    try:
        pool = get_pool()
        redis = get_redis_client()
        async with pool.acquire() as conn:
            await run_complete_impl(
                data,
                emit=make_emit(),
                conn=conn,
                redis=redis,
                upload_folder=UPLOAD_FOLDER,
            )
    except Exception as e:
        logger.exception(f"run_complete_impl failed: {e}")
