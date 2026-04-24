"""Attempt stream impl — joined-groups variant.

Attempt uses explicit /attempt/join to subscribe to many rooms, and its
events span multiple artifact types (persona, rubric, etc.) during a chat.
Unlike other artifacts, it does NOT resolve a single time-windowed group
via ``group_{artifact}_impl`` — it streams across every joined group with
no artifact filter.

This is the canonical named entry point for ``attempt`` streaming; routes
and tool-calling consumers import from here.
"""

from __future__ import annotations

from fastapi.responses import StreamingResponse

from app.infra.stream.sse import build_joined_stream_impl


async def stream_attempt_impl(*, profile_id: str) -> StreamingResponse:
    return await build_joined_stream_impl(profile_id=profile_id)
