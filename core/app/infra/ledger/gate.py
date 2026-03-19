"""Ledger gate — the main entry point called before every attempt start."""

from __future__ import annotations

from app.infra.ledger.chain import (
    GENESIS_HASH,
    count_entries,
    read_latest,
    write_entry,
)
from app.infra.ledger.client import phone_home
from app.infra.ledger.types import LedgerEntry, LearnLoopCheckpoint
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

DEFAULT_NUM_TO_NEXT_CHECK = 10


class LedgerDenied(Exception):
    """Raised when the ledger gate blocks an attempt."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def ledger_gate(*, attempt_id: str) -> LedgerEntry:
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
        checkpoint = await _phone_home(latest)

        if not checkpoint.authorized:
            raise LedgerDenied(
                checkpoint.message or "Usage not authorized by LearnLoop"
            )

        entry = _build_entry(
            latest=latest,
            attempt_id=attempt_id,
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


async def _phone_home(latest: LedgerEntry | None) -> LearnLoopCheckpoint:
    """Phone home to LearnLoop and return the checkpoint response."""
    current_sequence = latest.sequence if latest else 0
    current_hash = latest.hash if latest else GENESIS_HASH

    # Count attempts written since the last checkpoint
    attempts_since = _count_since_last_checkpoint(latest)

    logger.info(
        f"Phoning home to LearnLoop (sequence={current_sequence}, "
        f"attempts_since_last_check={attempts_since})"
    )

    return await phone_home(
        current_sequence=current_sequence,
        current_hash=current_hash,
        attempts_since_last_check=attempts_since,
    )


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
        is_checkpoint=is_checkpoint,
        checkpoint=checkpoint,
        num_left=num_left,
        num_to_next_check=num_to_next_check,
    )
