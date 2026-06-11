"""Input: test.next — drive the next pending invocation in a test.

Wires the client-emitted ``test.next`` event to the existing
``test_next_impl`` orchestration (``infra/test/workflows.py``), which finds
the next incomplete invocation and drives its group run (emitting
``test_run`` / ``test_all_complete`` / ``test.next.error`` to the caller's
room). Fire-and-forget like the other workflow triggers — the handler
returns once the orchestration is kicked off, and python-socketio's ack
resolves the client's WS command promise (no more 30s hang).

The orchestration is emit-driven, so we build a production ``EmitFn`` via
``make_emit()`` exactly as ``test_start_internal_impl`` does.
"""

from typing import Any

from app.infra.globals import get_pool, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.workflows import test_next_impl
from app.infra.websocket.socket_event import make_emit


@sio.on("test.next")  # type: ignore
async def test_next(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    test_id = data.get("test_id")
    if not test_id:
        return

    runner_data: dict[str, Any] = {
        "sid": sid,
        "profile_id": str(identity.profile_id),
        "session_id": str(identity.session_id),
        "test_id": str(test_id),
    }

    await test_next_impl(runner_data, emit=make_emit(), pool=get_pool())
