"""Pydantic types for the usage ledger."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class UserUsage(BaseModel):
    """Per-user usage counters for phone-home reporting."""

    profile_id: str
    email: str | None = None
    name: str | None = None
    role: str | None = None
    started: int = 0
    completed: int = 0
    passed: int = 0
    simulations: dict[str, dict[str, Any]] | None = None
    # simulations: {sim_id: {name, started, completed, passed}}


class AttemptContext(BaseModel):
    """Context about the current attempt being authorized.

    Sent to LearnLoop so it can make per-user, per-simulation decisions.

    NOTE on scoring model (as of v2.12):
    - Glow uses mastery-based scoring: a student is proficient once they
      reach the passing score on ANY attempt (best score counts).
    - The simulation score is the average of per-scenario scores.
    - The simulation score is implicitly computed, not explicitly stored
      as a single field — it's derived from scenario attempt grades.
    - passing_threshold comes from the rubric (pass_points / total_points),
      configured by the instance admin, not per-simulation.
    - There is currently no configurable "scoring metric" on the simulation
      (e.g., best-of-N, average-of-N, most-recent). It's always mastery
      (reach the bar once → proficient).
    - Future: the scoring metric could become configurable per-simulation,
      which would change what "passed" means and how scores are aggregated.
    """

    simulation_id: str | None = None
    simulation_name: str | None = None
    passing_threshold: float | None = None  # 0-1, from rubric pass_pct / 100


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
    profile_id: str | None = None
    is_checkpoint: bool = False
    checkpoint: LearnLoopCheckpoint | None = None
    num_left: int | None = None
    num_to_next_check: int = 0
    hash: str = ""
