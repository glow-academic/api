"""Input: attempt.chat_speak — push audio bytes into a conversation buffer.

No audit, no DB. Just pushes bytes into the session's inbound queue.
Keyed on conversation_id (or chat_id to resolve it).

AUTHZ: ownership is enforced inside the shared ``chat_speak_impl`` (the W1
WS↔HTTP shared-impl fix) — only the authenticated owner of the live session may
push audio into it (#149). The HTTP twin (``routes/attempt/chat_speak.py``)
calls the same impl so the guard can never diverge.
"""

from typing import Any

from app.infra.attempt.speak import chat_speak_impl
from app.infra.globals import sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.chat_speak")  # type: ignore
async def attempt_chat_speak(sid: str, data: dict[str, Any]) -> None:
    # AUTHN: mirror every sibling realtime handler (audio_upload.py, etc.) —
    # reject sockets with no stored identity (#149).
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    audio = data.get("audio")
    if not audio:
        return

    # Push through the shared owner-guarded impl. Fire-and-forget over WS: a
    # missing session or a non-owner caller is silently dropped (denied/not_found
    # → no frame enqueued), matching the prior #149 fail-closed behavior.
    chat_speak_impl(
        profile_id=identity.profile_id,
        conversation_id=data.get("conversation_id"),
        chat_id=data.get("chat_id"),
        audio=audio,
    )
