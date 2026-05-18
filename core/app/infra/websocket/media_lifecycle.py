"""Shared media generation lifecycle — adapter singleton.

Mirrors audio_lifecycle.py pattern for image/video generation.
"""

from app.infra.websocket.adapters.media.litellm import LitellmMediaAdapter
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

_media_adapter: LitellmMediaAdapter | None = None


def get_media_adapter(
    *,
    adapter_factory: type[LitellmMediaAdapter] | None = None,
    emitter: object | None = None,
) -> LitellmMediaAdapter:
    """Get or create the media adapter singleton."""
    global _media_adapter
    if _media_adapter is None:
        if emitter is None:
            from app.infra.websocket.generation_media_events import (
                get_media_emitter,
            )

            emitter = get_media_emitter()
        _media_adapter = (adapter_factory or LitellmMediaAdapter)(emitter=emitter)
    return _media_adapter
