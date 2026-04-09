"""Output: generate_artifact — forwards to client AND runs the LLM pipeline."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.generate_artifact_impl import generate_artifact_impl
from app.infra.websocket.generation_types import (
    GenerateArtifactPayload,
    GenerateErrorApiRequest,
)
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("generate_artifact")  # type: ignore
async def generate_artifact_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "generate_artifact", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("generate_artifact", data, room=room)

    # Run the LLM pipeline: call AI, execute tool calls
    try:
        payload = GenerateArtifactPayload(**data)
    except Exception as e:
        await internal_sio.emit(
            "generate_error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"Invalid generate_artifact payload: {str(e)}",
                artifact_type=data.get("artifact_type"),
                group_id=data.get("group_id"),
                resource_type=data.get("resource_type"),
            ).model_dump(),
        )
        return

    profile_id = data.get("profile_id")
    if profile_id is None and sid:
        profile_id = await find_profile_by_socket(sid)
    await generate_artifact_impl(
        payload,
        emit=make_emit(),
        sid=sid,
        profile_id=profile_id,
    )
