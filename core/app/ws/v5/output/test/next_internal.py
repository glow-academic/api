"""Output: test_next — call impl to find next pending invocation/run."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.next import test_next_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_next")  # type: ignore
async def test_next_internal_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_next", data, UPLOAD_FOLDER)
    await test_next_internal_impl(data)
