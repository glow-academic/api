"""Ledger chain: read, write, and HMAC-chain ledger entries."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

from app.infra.globals import UPLOAD_FOLDER
from app.infra.ledger.types import LedgerEntry

# ---------------------------------------------------------------------------
# Ledger directory
# ---------------------------------------------------------------------------
LEDGER_DIR = UPLOAD_FOLDER / "ledger"

GENESIS_HASH = "0" * 64  # SHA-256 zero hash for the first entry


def _ensure_dir() -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY", "")
    if not key:
        raise RuntimeError("SECRET_KEY is required for ledger operations")
    return key


def _entry_path(sequence: int) -> Path:
    return LEDGER_DIR / f"{sequence:06d}.json"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def compute_hash(entry: LedgerEntry) -> str:
    """Compute HMAC-SHA256 over the entry payload (excluding the hash field)."""
    payload = entry.model_dump(mode="json", exclude={"hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        _secret_key().encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_hash(entry: LedgerEntry) -> bool:
    """Verify an entry's hash matches its contents."""
    return hmac.compare_digest(entry.hash, compute_hash(entry))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_entry(sequence: int) -> LedgerEntry | None:
    """Read a single ledger entry by sequence number."""
    path = _entry_path(sequence)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return LedgerEntry(**data)


def read_latest() -> LedgerEntry | None:
    """Read the most recent ledger entry."""
    _ensure_dir()
    files = sorted(LEDGER_DIR.glob("*.json"))
    if not files:
        return None
    data = json.loads(files[-1].read_text())
    return LedgerEntry(**data)


def count_entries() -> int:
    """Count total ledger entries."""
    _ensure_dir()
    return len(list(LEDGER_DIR.glob("*.json")))


# ---------------------------------------------------------------------------
# Outcome counters (running totals alongside the chain)
# ---------------------------------------------------------------------------

_COUNTERS_PATH = LEDGER_DIR / "_counters.json"


def read_counters() -> dict[str, int]:
    """Read outcome counters: started, completed, passed."""
    _ensure_dir()
    if _COUNTERS_PATH.exists():
        data = json.loads(_COUNTERS_PATH.read_text())
        return {
            "started": data.get("started", 0),
            "completed": data.get("completed", 0),
            "passed": data.get("passed", 0),
        }
    return {"started": 0, "completed": 0, "passed": 0}


def increment_counter(field: str, count: int = 1) -> dict[str, int]:
    """Increment a counter (started, completed, or passed) and return all counters."""
    counters = read_counters()
    counters[field] = counters.get(field, 0) + count
    _ensure_dir()
    _COUNTERS_PATH.write_text(json.dumps(counters, indent=2) + "\n")
    return counters


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_entry(entry: LedgerEntry) -> LedgerEntry:
    """Compute hash and persist a ledger entry to disk."""
    _ensure_dir()
    entry.hash = compute_hash(entry)
    path = _entry_path(entry.sequence)
    path.write_text(
        json.dumps(entry.model_dump(mode="json"), indent=2) + "\n"
    )
    return entry


# ---------------------------------------------------------------------------
# Chain integrity
# ---------------------------------------------------------------------------

def verify_chain() -> tuple[bool, str]:
    """Walk the full chain and verify every link.

    Returns (valid, message).
    """
    _ensure_dir()
    files = sorted(LEDGER_DIR.glob("*.json"))
    if not files:
        return True, "Empty ledger"

    prev_hash = GENESIS_HASH
    for path in files:
        data = json.loads(path.read_text())
        entry = LedgerEntry(**data)

        if entry.previous_hash != prev_hash:
            return False, f"Chain break at sequence {entry.sequence}: previous_hash mismatch"
        if not verify_hash(entry):
            return False, f"Hash mismatch at sequence {entry.sequence}"

        prev_hash = entry.hash

    return True, f"Chain valid ({len(files)} entries)"
