"""Shared helpers for attempt audio handlers.

The adapter singleton and cleanup logic live in audio_lifecycle.py.
The event contract lives in audio_events.py.
This module re-exports for backward compatibility and provides domain-specific
helpers used by translators (delta.py, speech_*.py, error.py).
"""

import logging
from typing import Any

from app.infra.websocket.audio_lifecycle import cleanup_audio_session
from app.infra.websocket.session_store import get_session_by_group_id

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
cleanup_voice_session = cleanup_audio_session


def get_session_for_group(group_id: str) -> Any:
    """Get the audio session for a group_id.

    Returns the AudioSession if one exists, None otherwise.
    """
    return get_session_by_group_id(group_id)
