"""Canonical WS catch-all forwarder + SSE mirror.

Single chokepoint for everything ``internal_sio.emit(event, data)``
produces. Three things happen here, in this order:

  1. **Receipt stamp** — if ``data["call_id"]`` is present, the event
     joins the receipt's ``events[]`` at
     ``{UPLOAD_FOLDER}/call/{call_id}.json``.
  2. **WS fan-out** — emit to every room in ``data["rooms"]`` (or
     ``[data["sid"]]`` as a fallback). The client's WS subscribers
     pick events up here.
  3. **SSE mirror** — when ``data["group_id"]`` is present, publish
     an ``EventEnvelope`` to the in-process hub. SSE subscribers
     filtered to that group receive it.

The dot-segmented event name carries structure: ``persona.draft.completed``
→ ``artifact=persona, operation=draft``. We synthesize the envelope
from that convention; producers don't construct envelopes themselves.

This forwarder is the **only** place that bridges WS → SSE. Every
``internal_sio.emit`` is now automatically dual-transport — producers
call one primitive and reach both channels. Replaces:

  - the per-event ``ws/output/<artifact>/<op>/<phase>.py`` tree (1600+ files)
  - the parallel ``emit_artifact_operation_started/_finished/_failure``
    helpers in ``infra/stream/emitter.py``
  - the inline ``publish(EventEnvelope(...))`` mirrors in
    ``run_complete_impl`` and ``run_from_payload``
  - the ``wrap_emit_with_stream_bridge`` selective rename mechanism

Custom workflow logic that previously lived in a few output handlers
(audio session lifecycle, test grade bridge, test group orchestration)
is inlined at the emit sites — see ``infra/generation/audio.py``,
``infra/websocket/attempt/chat/silence.py``,
``infra/websocket/attempt/audio_events.py``, and
``infra/test/workflows.py``.

To trace every event in flight, drop a ``logger.debug`` line in
``_generic_forward`` below.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope
from app.infra.tools.entries.append_call_event import append_call_event

internal_sio = get_internal_sio()


@internal_sio.on("*")  # type: ignore
async def _generic_forward(event: str, data: dict[str, Any]) -> None:
    """Forward + SSE-mirror every ``internal_sio`` event.

    Producers emit once via ``internal_sio.emit(event, data)`` and reach
    both transports. The only structural filter is ``group_id`` — SSE
    routes by group, so an event without one has nothing to broadcast
    to (the hub would no-op anyway; we early-return to skip the
    envelope construction).
    """
    if not isinstance(data, dict):
        return

    # 1. Receipt stamp — every audited event lands on its own call_id's
    # receipt. For ack calls (where ``operation_key`` references a
    # different, earlier call), we ALSO append to the operation key's
    # receipt so the original soft call's events array accumulates the
    # full lifecycle (started→completed of the original, then later
    # started→completed of the ack with ``args.accept`` set). The UI
    # reads one file to determine "pending / accepted / rejected"
    # state, persisted indefinitely on disk.
    call_id = data.get("call_id")
    if call_id:
        try:
            append_call_event(UUID(str(call_id)), event, data, UPLOAD_FOLDER)
        except (ValueError, TypeError):
            # Malformed call_id is a logging concern, not a fatal one.
            pass

    operation_key = data.get("operation_key")
    if operation_key and operation_key != call_id:
        try:
            append_call_event(
                UUID(str(operation_key)), event, data, UPLOAD_FOLDER,
            )
        except (ValueError, TypeError):
            pass

    # 2. WS fan-out
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        if room:
            await sio.emit(event, data, room=room)

    # 3. SSE mirror — only when there's a group_id to route by.
    group_id = data.get("group_id")
    if not group_id:
        return
    try:
        gid = UUID(str(group_id))
    except (ValueError, TypeError):
        return
    parts = event.split(".")
    await publish(
        EventEnvelope(
            id=f"{uuid4()}:{event}",
            event_type=event,
            artifact=parts[0] if parts else event,
            operation=parts[1] if len(parts) >= 2 else "",
            created_at=datetime.now(UTC),
            group_id=gid,
            payload=data,
        )
    )
