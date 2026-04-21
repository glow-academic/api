"""Output: test.run.triggered — forwards to client + runs one invocation."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.test.run import test_run_internal_impl
from app.infra.tools.entries.append_call_event import append_call_event

internal_sio = get_internal_sio()


@internal_sio.on("test.run.triggered")  # type: ignore
async def run_triggered(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test.run.triggered", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("test.run.triggered", data, room=room)

    # Execute one invocation (copy messages, generate)
    await test_run_internal_impl(data)
