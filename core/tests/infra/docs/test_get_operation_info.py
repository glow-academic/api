"""Tests for get_operation_info."""

from uuid import UUID

import asyncpg  # type: ignore
from pydantic import BaseModel

from app.infra.docs.get_operation_info import get_operation_info


class _MockResponse(BaseModel):
    id: UUID


async def _sample_func(
    conn: asyncpg.Connection,
    profile_id: UUID,
    active: bool = True,
) -> _MockResponse:
    """Sample function for testing."""
    ...


def test_extracts_function_name():
    result = get_operation_info(_sample_func, description="Test op")

    assert result.name == "_sample_func"


def test_extracts_description():
    result = get_operation_info(_sample_func, description="Test op")

    assert result.description == "Test op"


def test_skips_conn_param():
    result = get_operation_info(_sample_func, description="Test op")

    param_names = [p.name for p in result.params]
    assert "conn" not in param_names


def test_extracts_required_param():
    result = get_operation_info(_sample_func, description="Test op")

    profile_param = next(p for p in result.params if p.name == "profile_id")
    assert profile_param.required is True
    assert "UUID" in profile_param.type


def test_extracts_optional_param_with_default():
    result = get_operation_info(_sample_func, description="Test op")

    active_param = next(p for p in result.params if p.name == "active")
    assert active_param.required is False
    assert active_param.default is True


def test_extracts_return_schema():
    result = get_operation_info(_sample_func, description="Test op")

    assert result.returns is not None
    assert result.returns["type"] == "_MockResponse"
    assert "schema" in result.returns
    assert "properties" in result.returns["schema"]


async def _no_return_func(conn: asyncpg.Connection) -> None: ...


def test_handles_none_return():
    result = get_operation_info(_no_return_func, description="No return")

    assert result.returns is not None
    assert "None" in result.returns["type"]
