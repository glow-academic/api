"""POST /document/csv — thin HTTP adapter over parse_document_csv_impl."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.infra.document.csv import (
    CsvParseError,
    ParseDocumentCsvApiResponse,
    parse_document_csv_impl,
)
from app.infra.globals import get_pool
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/csv", response_model=ParseDocumentCsvApiResponse)
async def parse_document_csv(
    file: UploadFile,
    http_request: Request,
) -> ParseDocumentCsvApiResponse:
    """Parse a CSV file and return mapped items for preview."""
    try:
        session_id = http_request.state.session_id
        file_bytes = await file.read()
        try:
            return await parse_document_csv_impl(
                get_pool(),
                session_id=session_id,
                file_bytes=file_bytes,
                file_name=file.filename or "file.csv",
                content_type=file.content_type or "text/csv",
            )
        except CsvParseError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="parse_document_csv",
            request=http_request,
        )
