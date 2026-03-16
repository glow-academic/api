"""Output: test_group — compose sequential test_runs in a group."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.test.group import test_group_internal_impl

internal_sio = get_internal_sio()


@internal_sio.on("test_group")  # type: ignore
async def test_group_internal_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_group", data, UPLOAD_FOLDER)
    await test_group_internal_impl(data)
