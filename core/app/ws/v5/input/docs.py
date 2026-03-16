"""Input: docs — request documentation."""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def docs(sid: str, data: dict[str, Any]) -> None:
    try:
        await internal_sio.emit(
            "docs",
            {"sid": sid},
        )
    except Exception as e:
        logger.exception(f"Error in docs input: {e}")
        await sio.emit(
            "docs_error",
            {"message": f"Invalid request: {e}"},
            room=sid,
        )
