"""Cancel the current realtime turn without tearing down the session.

Sends ``response.cancel`` to the provider WS so the model stops emitting
audio/text/tool-call output for the active turn. The WebSocket stays
open; client can issue another ``/attempt/generate`` to start the next
turn.

Looks up the session by ``group_id`` (the internal handle the pipeline
uses for the current run). Noop if no live realtime session exists.
"""

from __future__ import annotations

import json
import logging

from app.infra.websocket.session_store import get_session_by_group_id

logger = logging.getLogger(__name__)


async def cancel_realtime_turn(group_id: str) -> bool:
    """Send ``response.cancel`` to the provider WS for ``group_id``.

    Returns ``True`` if a cancel was sent, ``False`` if there was no
    session or no live WS.
    """
    session = get_session_by_group_id(group_id)
    if session is None:
        return False
    ws = session.oa_ws_connection
    if ws is None:
        return False
    try:
        await ws.send(json.dumps({"type": "response.cancel"}))
    except Exception as exc:
        logger.warning(
            f"Failed to send response.cancel for group_id={group_id}: {exc}"
        )
        return False

    # Drop the per-turn assistant buffer so the next turn starts clean.
    session.assistant_audio_buffer = bytearray()
    logger.info(f"Sent response.cancel to realtime provider - group_id={group_id}")
    return True
