"""Output: attempt.generate.text.complete"""

import logging
from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event

logger = logging.getLogger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.text.complete")  # type: ignore
async def attempt_generate_text_complete(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    logger.info(
        f"VOICE_TRACE[3] text.complete fwd: sid={sid!r} rooms={rooms} "
        f"group_id={data.get('group_id')} text={(data.get('text') or '')[:60]!r}"
    )
    if call_id:
        append_call_event(UUID(call_id), "attempt.generate.text.complete", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("attempt.generate.text.complete", data, room=room)
