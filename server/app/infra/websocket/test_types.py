"""Pydantic models for test-domain internal bus emits.

Canonical location — re-exported from routes/v5/socket/internal/test/types.py.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TestProgressData(BaseModel):
    sid: str | None = None
    rooms: list[str] = []
    invocation_id: str
    run_id: str | None = None
    current_run: int | None = None
    total_runs: int | None = None
    message: str | None = None


class TestRunCompleteData(BaseModel):
    sid: str | None = None
    rooms: list[str] = []
    invocation_id: str
    run_id: str | None = None
    original_run_resource_id: str | None = None
    tool_calls: Any | None = None
    current_run: int = 1
    total_runs: int = 1
    remaining_runs: int = 0


class TestGradedData(BaseModel):
    sid: str | None = None
    rooms: list[str] = []
    invocation_id: str
    grade_id: str | None = None
    score: int | None = None
    passed: bool | None = None
    feedback: str | None = None


class TestProceedData(BaseModel):
    """Internal bus payload for test_proceed — find next invocation to run."""

    sid: str
    test_id: str
    force_proceed: bool = False
    completed_invocation_id: str | None = None
    complete_all: bool = False


class TestErrorData(BaseModel):
    sid: str | None = None
    rooms: list[str] = []
    invocation_id: str | None = None
    run_id: str | None = None
    message: str
    error_type: str | None = None


class TestAllCompleteEvent(BaseModel):
    """Server-to-client event: test_all_complete.

    Emitted when all runs are complete.
    """

    invocation_id: str
    total_runs: int
    success: bool = True
