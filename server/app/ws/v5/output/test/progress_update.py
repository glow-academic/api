"""Output: test_progress_update — call impl to transform to test_grade_start."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.test.workflows import test_progress_impl
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


def _resolve_invocation_id(data: dict[str, Any]) -> UUID | None:
    raw = data.get("invocation_id") or data.get("chat_id")
    if not raw:
        return None
    return UUID(str(raw))


@internal_sio.on("test_progress_update")  # type: ignore
async def test_progress_update_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_progress_update", data, UPLOAD_FOLDER)
    await test_progress_impl(
        data,
        emit=wrap_emit_with_stream_bridge(
            artifact="test",
            operation="run",
            emit=make_emit(),
            entity_id=_resolve_invocation_id(data),
        ),
    )
