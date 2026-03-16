"""Output: test_start — call impl to create test and proceed."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.start import test_start_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_start")  # type: ignore
async def test_start_internal_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_start", data, UPLOAD_FOLDER)
    await test_start_internal_impl(data)
