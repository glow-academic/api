"""Output: test.group.started — forwards to client + runs orchestration."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, sio
from app.infra.test.workflows import test_group_impl
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("test.group.started")  # type: ignore
async def test_group_started(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test.group.started", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("test.group.started", data, room=room)

    # Orchestration: compose sequential test_runs in a group
    await test_group_impl(data, emit=make_emit(), pool=get_pool())
