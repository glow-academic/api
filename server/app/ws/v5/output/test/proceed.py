"""Output: test_proceed — state machine, find next invocation."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.proceed import test_proceed_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_proceed")  # type: ignore
async def test_proceed_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_proceed", data, UPLOAD_FOLDER)
    await test_proceed_internal_impl(data)
