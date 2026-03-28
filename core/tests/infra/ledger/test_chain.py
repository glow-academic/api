"""Tests for ledger chain — HMAC-chain read, write, verify."""

import json

import pytest

from app.infra.ledger.types import LedgerEntry

pytestmark = pytest.mark.asyncio


async def test_compute_hash_produces_hex_string(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    monkeypatch.setattr(chain_mod, "LEDGER_DIR", tmp_path / "ledger")

    entry = LedgerEntry(
        sequence=1,
        previous_hash="0" * 64,
        attempt_id="abc",
    )
    h = chain_mod.compute_hash(entry)
    assert isinstance(h, str)
    assert len(h) == 64  # SHA-256 hex digest


async def test_verify_hash_matches_computed(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    monkeypatch.setattr(chain_mod, "LEDGER_DIR", tmp_path / "ledger")

    entry = LedgerEntry(sequence=1, previous_hash="0" * 64)
    entry.hash = chain_mod.compute_hash(entry)
    assert chain_mod.verify_hash(entry) is True


async def test_verify_hash_fails_for_tampered_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    monkeypatch.setattr(chain_mod, "LEDGER_DIR", tmp_path / "ledger")

    entry = LedgerEntry(sequence=1, previous_hash="0" * 64)
    entry.hash = chain_mod.compute_hash(entry)
    entry.sequence = 999  # tamper
    assert chain_mod.verify_hash(entry) is False


async def test_write_and_read_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    entry = LedgerEntry(
        sequence=1,
        previous_hash=chain_mod.GENESIS_HASH,
        attempt_id="test-attempt",
    )
    written = chain_mod.write_entry(entry)
    assert written.hash != ""

    read_back = chain_mod.read_entry(1)
    assert read_back is not None
    assert read_back.sequence == 1
    assert read_back.attempt_id == "test-attempt"
    assert read_back.hash == written.hash


async def test_read_latest_returns_last_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    e1 = LedgerEntry(sequence=1, previous_hash=chain_mod.GENESIS_HASH, attempt_id="a1")
    w1 = chain_mod.write_entry(e1)

    e2 = LedgerEntry(sequence=2, previous_hash=w1.hash, attempt_id="a2")
    chain_mod.write_entry(e2)

    latest = chain_mod.read_latest()
    assert latest is not None
    assert latest.sequence == 2
    assert latest.attempt_id == "a2"


async def test_count_entries(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    assert chain_mod.count_entries() == 0

    e1 = LedgerEntry(sequence=1, previous_hash=chain_mod.GENESIS_HASH)
    chain_mod.write_entry(e1)
    assert chain_mod.count_entries() == 1


async def test_verify_chain_valid(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    e1 = LedgerEntry(sequence=1, previous_hash=chain_mod.GENESIS_HASH)
    w1 = chain_mod.write_entry(e1)

    e2 = LedgerEntry(sequence=2, previous_hash=w1.hash)
    chain_mod.write_entry(e2)

    valid, msg = chain_mod.verify_chain()
    assert valid is True
    assert "2 entries" in msg


async def test_verify_chain_detects_tampered_hash(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    e1 = LedgerEntry(sequence=1, previous_hash=chain_mod.GENESIS_HASH)
    w1 = chain_mod.write_entry(e1)

    # Write a second entry with correct previous_hash, then tamper the file
    e2 = LedgerEntry(sequence=2, previous_hash=w1.hash)
    chain_mod.write_entry(e2)

    # Tamper the second file
    path = ledger_dir / "000002.json"
    data = json.loads(path.read_text())
    data["attempt_id"] = "tampered"
    path.write_text(json.dumps(data))

    valid, msg = chain_mod.verify_chain()
    assert valid is False
    assert "sequence 2" in msg


async def test_verify_chain_empty_is_valid(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    valid, msg = chain_mod.verify_chain()
    assert valid is True
    assert "Empty" in msg


async def test_read_entry_returns_none_for_missing(monkeypatch, tmp_path):
    import app.infra.ledger.chain as chain_mod

    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(chain_mod, "LEDGER_DIR", ledger_dir)

    assert chain_mod.read_entry(999) is None


async def test_secret_key_required(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "")
    import app.infra.ledger.chain as chain_mod

    monkeypatch.setattr(chain_mod, "LEDGER_DIR", tmp_path / "ledger")

    entry = LedgerEntry(sequence=1, previous_hash="0" * 64)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        chain_mod.compute_hash(entry)
