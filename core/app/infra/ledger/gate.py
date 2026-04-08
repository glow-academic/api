"""Ledger gate — the main entry point called before every attempt start."""

from __future__ import annotations

from app.infra.ledger.chain import (
    GENESIS_HASH,
    count_entries,
    increment_counter,
    increment_user_counter,
    read_counters,
    read_latest,
    read_user_counters,
    reset_user_counters,
    write_entry,
)
from app.infra.ledger.client import phone_home
from app.infra.ledger.types import LedgerEntry, LearnLoopCheckpoint, UserUsage
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

DEFAULT_NUM_TO_NEXT_CHECK = 10


class LedgerDenied(Exception):
    """Raised when the ledger gate blocks an attempt."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def record_start(
    *,
    profile_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
    role: str | None = None,
) -> dict[str, int]:
    """Record an attempt start in the outcome counters."""
    if profile_id:
        increment_user_counter(profile_id, "started", email=email, name=name, role=role)
    return increment_counter("started")


def record_completion(
    *,
    passed: bool,
    profile_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
    role: str | None = None,
) -> dict[str, int]:
    """Record an attempt completion in the outcome counters.

    Call with passed=True if the attempt met the passing threshold.
    """
    if profile_id:
        increment_user_counter(profile_id, "completed", email=email, name=name, role=role)
        if passed:
            increment_user_counter(profile_id, "passed")
    counters = increment_counter("completed")
    if passed:
        counters = increment_counter("passed")
    return counters


async def ledger_gate(
    *,
    attempt_id: str,
    profile_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
) -> LedgerEntry:
    """Check the ledger, phone home if needed, and write the next entry.

    Returns the newly written LedgerEntry on success.
    Raises LedgerDenied if the attempt is not authorized.
    """
    latest = read_latest()

    # ------------------------------------------------------------------
    # Determine whether we need to phone home
    # ------------------------------------------------------------------
    needs_check = latest is None or latest.num_to_next_check <= 0

    if needs_check:
        checkpoint = await _phone_home(
            latest,
            profile_id=profile_id,
            email=email,
            name=name,
        )

        if not checkpoint.authorized:
            raise LedgerDenied(
                checkpoint.message or "Usage not authorized by LearnLoop"
            )

        entry = _build_entry(
            latest=latest,
            attempt_id=attempt_id,
            profile_id=profile_id,
            is_checkpoint=True,
            checkpoint=checkpoint,
            num_left=checkpoint.num_left,
            num_to_next_check=checkpoint.num_to_next_check,
        )
    else:
        # No phone-home needed — decrement counter locally
        entry = _build_entry(
            latest=latest,
            attempt_id=attempt_id,
            profile_id=profile_id,
            is_checkpoint=False,
            checkpoint=None,
            num_left=latest.num_left - 1 if latest.num_left is not None else None,
            num_to_next_check=latest.num_to_next_check - 1,
        )

    written = write_entry(entry)
    logger.info(
        f"Ledger entry #{written.sequence} written "
        f"(checkpoint={written.is_checkpoint}, "
        f"num_to_next_check={written.num_to_next_check})"
    )
    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _phone_home(
    latest: LedgerEntry | None,
    *,
    profile_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
) -> LearnLoopCheckpoint:
    """Phone home to LearnLoop and return the checkpoint response.

    Always sends running totals (started, completed, passed) so LearnLoop
    can diff against its last known state. Self-healing if phone-homes fail.
    Also sends per-user usage deltas since the last checkpoint.
    """
    current_sequence = latest.sequence if latest else 0
    current_hash = latest.hash if latest else GENESIS_HASH

    # Count attempts written since the last checkpoint
    attempts_since = _count_since_last_checkpoint(latest)

    # Read outcome counters (running totals)
    counters = read_counters()

    # Build per-user usage from accumulated counters
    user_counters = read_user_counters()
    user_usage = [
        UserUsage(
            profile_id=pid,
            email=data.get("email"),
            name=data.get("name"),
            role=data.get("role"),
            started=data.get("started", 0),
            completed=data.get("completed", 0),
            passed=data.get("passed", 0),
        )
        for pid, data in user_counters.items()
    ]

    logger.info(
        f"Phoning home to LearnLoop (sequence={current_sequence}, "
        f"attempts_since_last_check={attempts_since}, "
        f"started={counters['started']}, completed={counters['completed']}, "
        f"passed={counters['passed']}, users={len(user_usage)})"
    )

    checkpoint = await phone_home(
        current_sequence=current_sequence,
        current_hash=current_hash,
        attempts_since_last_check=attempts_since,
        started=counters["started"],
        completed=counters["completed"],
        passed=counters["passed"],
        user_usage=user_usage,
        current_profile_id=profile_id,
        current_email=email,
        current_name=name,
    )

    # Reset per-user counters after successful phone-home (deltas reported)
    reset_user_counters()

    return checkpoint


def _count_since_last_checkpoint(latest: LedgerEntry | None) -> int:
    """Count entries written since the last checkpoint."""
    if latest is None:
        return 0
    # Walk backwards from latest. The simplest approach: total entries minus
    # the sequence of the last checkpoint. But since we only have the latest
    # entry, we use the num_to_next_check that was set at the last checkpoint
    # vs what it is now to infer the delta.
    total = count_entries()
    if latest.is_checkpoint:
        return 0
    # If current num_to_next_check is N, and the checkpoint set it to M,
    # then attempts since = M - N. But we don't store M on non-checkpoint
    # entries. Simplest: just report total entries since we track everything.
    return total


def _build_entry(
    *,
    latest: LedgerEntry | None,
    attempt_id: str,
    profile_id: str | None = None,
    is_checkpoint: bool,
    checkpoint: LearnLoopCheckpoint | None,
    num_left: int | None,
    num_to_next_check: int,
) -> LedgerEntry:
    """Construct a new LedgerEntry chained to the latest."""
    return LedgerEntry(
        sequence=(latest.sequence + 1) if latest else 1,
        previous_hash=latest.hash if latest else GENESIS_HASH,
        attempt_id=attempt_id,
        profile_id=profile_id,
        is_checkpoint=is_checkpoint,
        checkpoint=checkpoint,
        num_left=num_left,
        num_to_next_check=num_to_next_check,
    )
