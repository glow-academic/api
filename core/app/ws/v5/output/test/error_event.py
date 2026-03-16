"""Output: test_error_event — call impl to transform to test_error."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.test.workflows import test_error_impl
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("test_error_event")  # type: ignore
async def test_error_event_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_error_event", data, UPLOAD_FOLDER)
    await test_error_impl(data, emit=make_emit())
