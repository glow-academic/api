"""Output: generation_channel — chat/attempt post-processing.

Listens for generation_channel events where artifact_type is "chat" or "attempt".
Handles MV refresh, cache invalidation, and attempt lifecycle events
that were previously inline in run_complete_impl.

Separated so run_complete_impl stays generic.
"""

from typing import Any

from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.websocket.socket_event import make_emit, internal_event
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

internal_sio = get_internal_sio()
logger = get_logger(__name__)


@internal_sio.on("generation_channel")  # type: ignore
async def generation_channel_chat_handler(data: dict[str, Any]) -> None:
    """Handle chat/attempt post-processing after generation completes."""
    if data.get("type") != "complete":
        return

    artifact_type = data.get("artifact_type", "")
    metadata = data.get("metadata") or {}
    sid = data.get("sid", "")

    if artifact_type not in ("chat", "attempt"):
        return

    pool = get_pool()
    redis = get_redis_client()
    emit = make_emit()

    # Chat: refresh MVs + emit attempt_chat_started
    if artifact_type == "chat":
        attempt_id = metadata.get("attempt_id")
        attempt_chat_id = metadata.get("attempt_chat_id")

        if attempt_id and attempt_chat_id and not metadata.get("chat_started_emitted"):
            try:
                async with pool.acquire() as conn:
                    await refresh_attempt(conn)
                    await refresh_attempt_chat(conn)
                await invalidate_tags(["attempt", "attempts"], redis=redis)

                from app.infra.websocket.attempt_types import AttemptChatStartedData
                await emit([
                    internal_event(
                        "attempt_chat_started",
                        AttemptChatStartedData(
                            sid=sid,
                            attempt_id=attempt_id,
                            chat_id=attempt_chat_id,
                        ).model_dump(mode="json"),
                    )
                ])
            except Exception as e:
                logger.exception(f"Failed chat post-save: {e}")

    # Chat/attempt: emit attempt_grade_complete
    grade_id = metadata.get("grade_id")
    chat_id = metadata.get("chat_id")
    if grade_id and chat_id and not metadata.get("grade_complete_emitted"):
        try:
            from app.infra.websocket.attempt_types import AttemptGradeCompleteData
            await emit([
                internal_event(
                    "attempt_grade_complete",
                    AttemptGradeCompleteData(
                        sid=sid,
                        chat_id=chat_id,
                        grade_id=grade_id,
                    ).model_dump(mode="json"),
                )
            ])
        except Exception as e:
            logger.exception(f"Failed attempt grade completion emit: {e}")
