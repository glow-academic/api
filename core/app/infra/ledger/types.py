"""Pydantic types for the usage ledger."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class LearnLoopCheckpoint(BaseModel):
    """Metadata returned by LearnLoop on a phone-home check."""

    authorized: bool
    num_left: int | None = None
    num_to_next_check: int = 10
    message: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class LedgerEntry(BaseModel):
    """A single entry in the usage ledger chain."""

    sequence: int
    previous_hash: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    attempt_id: str | None = None
    is_checkpoint: bool = False
    checkpoint: LearnLoopCheckpoint | None = None
    num_left: int | None = None
    num_to_next_check: int = 0
    hash: str = ""
