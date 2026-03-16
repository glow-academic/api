"""Shared audio session lifecycle — adapter singleton + cleanup.

Used by generate.py (session creation), audio_session.py (stop),
disconnect.py (cleanup on disconnect), and the stale session reaper.
"""

import logging

from app.infra.globals import (
    _voice_message_ids,
    _voice_message_ids_lock,
)
from app.infra.websocket.adapters.audio.realtime import RealtimeAudioAdapter
from app.infra.websocket.session_store import AudioSession, remove_session

logger = logging.getLogger(__name__)

_audio_adapter: RealtimeAudioAdapter | None = None


def get_audio_adapter(
    *,
    adapter_factory: type[RealtimeAudioAdapter] | None = None,
    emitter: object | None = None,
) -> RealtimeAudioAdapter:
    """Get or create the audio adapter singleton."""
    global _audio_adapter
    if _audio_adapter is None:
        if emitter is None:
            from app.infra.websocket.attempt.audio_events import (
                get_audio_emitter,
            )

            emitter = get_audio_emitter()
        _audio_adapter = (adapter_factory or RealtimeAudioAdapter)(emitter=emitter)
    return _audio_adapter


async def cleanup_audio_session(
    session: AudioSession,
    *,
    adapter: RealtimeAudioAdapter | None = None,
) -> None:
    """Stop adapter tasks + remove session from store. Idempotent."""
    group_id = session.group_id
    try:
        active_adapter = adapter or get_audio_adapter()
        try:
            await active_adapter.stop_session(session)
        except Exception as e:
            logger.warning(f"Error stopping audio adapter during cleanup: {e}")

        remove_session(group_id)

        async with _voice_message_ids_lock:
            _voice_message_ids.pop(group_id, None)

        logger.info(f"Audio session cleaned up - group_id={group_id}")
    except Exception as e:
        logger.exception(f"Error during audio session cleanup: {e}")
