"""Output: test_stop — call impl to stop test execution."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.stop import test_stop_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_stop")  # type: ignore
async def test_stop_internal_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_stop", data, UPLOAD_FOLDER)
    await test_stop_internal_impl(data)
