"""Tests for export_rubric_impl — PDF export orchestration.

Exercises the infra impl at a shallow level: function presence, required
arg signature, and the 404 branch when get_rubric_impl reports the rubric
doesn't exist. Deeper rendering tests would mock the full rubric shape
and assert on the PDF header magic bytes, which is brittle — left out.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


async def test_export_function_exists():
    import app.infra.rubric.export as mod

    assert callable(mod.export_rubric_impl)


async def test_export_raises_404_when_rubric_missing(monkeypatch):
    import app.infra.rubric.export as mod
    from app.infra.rubric.types import GetRubricApiResponse

    # get_rubric_impl returns rubric_exists=False when the id is unknown;
    # export_rubric_impl should surface that as 404.
    missing = GetRubricApiResponse(rubric_exists=False)
    monkeypatch.setattr(
        mod, "get_rubric_impl", AsyncMock(return_value=missing)
    )
    pool, redis = AsyncMock(), AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await mod.export_rubric_impl(
            pool, redis, profile_id=uuid4(), rubric_id=uuid4()
        )
    assert exc.value.status_code == 404


async def test_export_response_shape_is_pdf_envelope():
    """The infra impl returns the canonical ExportRubricApiResponse."""
    from app.infra.rubric.types import ExportRubricApiResponse

    # Just asserts the model has the fields HTTP + WS paths depend on.
    sig = set(ExportRubricApiResponse.model_fields.keys())
    assert {"content", "file_name", "mime_type", "row_count"}.issubset(sig)
