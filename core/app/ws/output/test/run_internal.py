"""Output: test_run — execute one invocation (copy messages, generate)."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.run import test_run_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_run")  # type: ignore
async def test_run_internal_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_run", data, UPLOAD_FOLDER)
    await test_run_internal_impl(data)
