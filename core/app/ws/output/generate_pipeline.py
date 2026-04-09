"""Output: generate — forwards to client AND kicks off rate limit gate."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.generate_new_impl import generate_new_impl
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("generate")  # type: ignore
async def generate_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "generate", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("generate", data, room=room)

    # Kick off the generation pipeline: rate limit → prepare → artifact
    pool = get_pool()
    await generate_new_impl(data, emit=make_emit(), pool=pool)
