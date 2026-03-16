"""Output: test_run_done — call impl to transform to test_run_complete."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.test.workflows import test_run_done_impl
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


def _resolve_invocation_id(data: dict[str, Any]) -> UUID | None:
    raw = data.get("invocation_id") or data.get("chat_id")
    if not raw:
        return None
    return UUID(str(raw))


@internal_sio.on("test_run_done")  # type: ignore
async def test_run_done_output(data: dict[str, Any]) -> None:
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "test_run_done", data, UPLOAD_FOLDER)
    await test_run_done_impl(
        data,
        emit=wrap_emit_with_stream_bridge(
            artifact="test",
            operation="run",
            emit=make_emit(),
            entity_id=_resolve_invocation_id(data),
        ),
    )
