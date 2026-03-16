"""Output: test_end — call impl to end invocation, optionally grade."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.end import test_end_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_end")  # type: ignore
async def test_end_internal_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_end", data, UPLOAD_FOLDER)
    await test_end_internal_impl(data)
