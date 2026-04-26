"""Output: test.trace.failed — forward audit-emitted failure to the client room."""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("test.trace.failed")  # type: ignore
async def trace_failed(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("test.trace.failed", data, room=room)


# Legacy ".error" alias — some emit sites still use this naming.
@internal_sio.on("test.trace.error")  # type: ignore
async def trace_error(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("test.trace.error", data, room=room)
