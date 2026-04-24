"""Canonical per-artifact stream impl — attempt.

Thin wrapper around `build_artifact_stream_impl` so attempt has a stable
named entry point (`stream_attempt_impl`) alongside every other artifact's
canonical impl set. Same shape as every other `infra/{artifact}/stream.py`.
"""

from __future__ import annotations

from fastapi.responses import StreamingResponse

from app.infra.stream.sse import build_artifact_stream_impl


async def stream_attempt_impl(*, profile_id: str) -> StreamingResponse:
    return await build_artifact_stream_impl(
        profile_id=profile_id, artifact="attempt"
    )
