"""Canonical per-artifact stream impl — test."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.infra.stream.sse import build_artifact_stream_impl


async def stream_test_impl(
    *, profile_id: str, group_id: UUID | None = None,
    run_id: UUID | None = None,
) -> StreamingResponse:
    if group_id is None:
        raise HTTPException(
            status_code=400,
            detail="group_id query param required for /test/stream",
        )
    return await build_artifact_stream_impl(group_id=group_id, run_id=run_id, artifact="test")
