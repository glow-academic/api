"""Tests for export_rubric_impl — PDF export orchestration.

Exercises the infra impl at a shallow level: function presence, required
arg signature, and the 404 branch when get_rubric_impl reports the rubric
doesn't exist. Deeper rendering tests would mock the full rubric shape
and assert on the PDF header magic bytes, which is brittle — left out.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


def _async_pool_with_conn(conn: object) -> MagicMock:
    """Build a pool mock whose `pool.acquire()` yields `conn` via the
    async-context-manager protocol. Regular AsyncMock doesn't model
    ``async with pool.acquire() as conn:`` correctly.
    """
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool


async def test_export_function_exists():
    import app.infra.rubric.export as mod

    assert callable(mod.export_rubric_impl)


async def test_export_raises_404_when_rubric_missing(monkeypatch):
    import app.infra.rubric.export as mod

    # The impl composes tool-layer black boxes directly. An empty
    # `get_rubrics` result for the supplied id should surface as 404
    # before we ever attempt resource hydration.
    monkeypatch.setattr(
        mod,
        "resolve_profile_identity_context",
        AsyncMock(return_value=object()),  # any truthy profile
    )
    monkeypatch.setattr(
        mod, "get_rubrics_resource", AsyncMock(return_value=[])
    )

    pool = _async_pool_with_conn(MagicMock())
    redis = AsyncMock()

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
    assert {"file_id", "file_name", "idempotency_key", "row_count"}.issubset(sig)
