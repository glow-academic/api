"""Chat send — send a message in an attempt chat.

Was: POST /attempt/message
Now: POST /attempt/chat/send
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.message import attempt_message_internal_impl

router = APIRouter()


# ---------------------------------------------------------------------------
# Optional entry types (agent-provided, skip internal AI)
# ---------------------------------------------------------------------------


class HintEntry(BaseModel):
    """Agent-provided hint for a message."""

    hint: str
    message_id: UUID | None = None


class ContentEntry(BaseModel):
    """Agent-provided content entry for a message."""

    content: str
    persona_id: UUID | None = None


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


class ChatSendApiRequest(BaseModel):
    attempt_id: UUID
    chat_id: UUID
    message: str
    parent_message_id: UUID | None = None
    # Optional — agent can provide these, otherwise internal AI generates them
    assistant_content: str | None = None
    hints: list[HintEntry] | None = None
    contents: list[ContentEntry] | None = None


class ChatSendApiResponse(BaseModel):
    chat_id: str
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    assistant_content: str | None = None
    hints: list[dict[str, Any]] | None = None


@router.post("/send", response_model=ChatSendApiResponse)
async def chat_send(
    request: ChatSendApiRequest,
    http_request: Request,
) -> ChatSendApiResponse:
    """Send a message in an attempt chat.

    Browser client: sends message only, internal AI generates response + hints.
    Agent: can optionally provide assistant_content, hints, contents to skip AI.
    """
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await attempt_message_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatSendApiResponse.model_validate(result.model_dump(mode="json"))
