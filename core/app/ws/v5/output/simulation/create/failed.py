"""Output: simulation.create.failed"""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event

internal_sio = get_internal_sio()


@internal_sio.on("simulation.create.failed")  # type: ignore
async def simulation_create_failed(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "simulation.create.failed", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("simulation.create.failed", data, room=room)
