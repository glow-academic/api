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
    # Only match numbered entry files (000000.json, 000001.json, etc.)
    files = sorted(LEDGER_DIR.glob("[0-9]*.json"))
    if not files:
        return None
    data = json.loads(files[-1].read_text())
    return LedgerEntry(**data)


def count_entries() -> int:
    """Count total ledger entries."""
    _ensure_dir()
    return len(list(LEDGER_DIR.glob("[0-9]*.json")))


# ---------------------------------------------------------------------------
# Outcome counters (running totals alongside the chain)
# ---------------------------------------------------------------------------

_COUNTERS_PATH = LEDGER_DIR / "_counters.json"
_USER_COUNTERS_PATH = LEDGER_DIR / "_user_counters.json"


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
# Per-user counters
# ---------------------------------------------------------------------------

def read_user_counters() -> dict[str, dict[str, Any]]:
    """Read per-user outcome counters. Keyed by profile_id.

    Returns: {"profile_id": {"email": "...", "name": "...", "role": "...", "started": N, ...}}
    """
    _ensure_dir()
    if _USER_COUNTERS_PATH.exists():
        return json.loads(_USER_COUNTERS_PATH.read_text())
    return {}


def increment_user_counter(
    profile_id: str,
    field: str,
    *,
    email: str | None = None,
    name: str | None = None,
    role: str | None = None,
    simulation_id: str | None = None,
    simulation_name: str | None = None,
    count: int = 1,
) -> dict[str, dict[str, Any]]:
    """Increment a per-user counter and update user metadata.

    Also tracks per-simulation counters within each user entry.
    """
    users = read_user_counters()
    if profile_id not in users:
        users[profile_id] = {"started": 0, "completed": 0, "passed": 0}
    users[profile_id][field] = users[profile_id].get(field, 0) + count
    # Update metadata on every call (in case name/email changed)
    if email:
        users[profile_id]["email"] = email
    if name:
        users[profile_id]["name"] = name
    if role:
        users[profile_id]["role"] = role
    # Track per-simulation within this user
    if simulation_id:
        sims = users[profile_id].setdefault("simulations", {})
        if simulation_id not in sims:
            sims[simulation_id] = {"started": 0, "completed": 0, "passed": 0}
        sims[simulation_id][field] = sims[simulation_id].get(field, 0) + count
        if simulation_name:
            sims[simulation_id]["name"] = simulation_name
    _ensure_dir()
    _USER_COUNTERS_PATH.write_text(json.dumps(users, indent=2) + "\n")
    return users


def reset_user_counters() -> None:
    """Reset per-user counters after a successful phone-home."""
    _ensure_dir()
    if _USER_COUNTERS_PATH.exists():
        _USER_COUNTERS_PATH.write_text("{}\n")


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
