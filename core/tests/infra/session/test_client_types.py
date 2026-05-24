"""Tests for session client_types."""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="session")

async def test_session_types_module_exists():
    import app.infra.session.types as m
    assert m.__file__.endswith("types.py")

async def test_session_response_type():
    from app.infra.session.types import GetSessionDetailResponse
    assert GetSessionDetailResponse is not None

async def test_session_internal_data():
    from app.infra.session.types import SessionInternalData
    assert SessionInternalData is not None
