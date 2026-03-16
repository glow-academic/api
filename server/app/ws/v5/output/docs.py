"""Output: docs — return documentation."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.routes.v5.docs import get_glow_docs

internal_sio = get_internal_sio()


@internal_sio.on("docs")  # type: ignore
async def docs_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "docs", data, UPLOAD_FOLDER)

    await sio.emit("docs_result", get_glow_docs(), room=sid)
