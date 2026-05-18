"""Test text download endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.test.media_types import TextDownloadTestApiRequest
from app.infra.test.text_download import text_download_test_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/text_download")
async def test_text_download(
    request: TextDownloadTestApiRequest,
    http_request: Request,
):
    """Download text content for a test."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID required.")

        result = await text_download_test_impl(
            get_pool(), get_redis_client(),
            profile_id=profile_id,
            text_id=request.text_id,
            session_id=session_id,
        )

        return FileResponse(
            path=result.file_path,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'inline; filename="{result.filename}"',
                "Cache-Control": "private, max-age=0, must-revalidate",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e, route_path=http_request.url.path,
            operation="test_text_download", sql_query=None,
            sql_params=None, request=http_request,
        )
