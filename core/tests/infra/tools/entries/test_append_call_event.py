"""Tests for append_call_event — appends events to call receipt JSON files."""

import json
from uuid import uuid4

import pytest

from app.infra.tools.entries.append_call_event import append_call_event

pytestmark = pytest.mark.asyncio


def _create_receipt(tmp_path, call_id, data=None):
    """Write a minimal call receipt JSON file and return the path."""
    call_dir = tmp_path / "call"
    call_dir.mkdir(parents=True, exist_ok=True)
    path = call_dir / f"{call_id}.json"
    receipt = data or {"call_id": str(call_id), "tool_id": "abc", "arguments": {}, "output": "ok"}
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


# -- appends event to existing receipt -----------------------------------------


async def test_appends_event_to_existing_receipt(tmp_path):
    """append_call_event adds an event with timestamp to the events array."""
    call_id = uuid4()
    path = _create_receipt(tmp_path, call_id)

    append_call_event(call_id, "completed", {"result": "success"}, tmp_path)

    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert "events" in receipt
    assert len(receipt["events"]) == 1

    event = receipt["events"][0]
    assert event["event"] == "completed"
    assert event["data"] == {"result": "success"}
    assert "timestamp" in event


async def test_appends_multiple_events_preserves_order(tmp_path):
    """Multiple calls append events in order."""
    call_id = uuid4()
    _create_receipt(tmp_path, call_id)

    append_call_event(call_id, "started", {"step": 1}, tmp_path)
    append_call_event(call_id, "progress", {"step": 2}, tmp_path)
    append_call_event(call_id, "completed", {"step": 3}, tmp_path)

    receipt = json.loads(
        (tmp_path / "call" / f"{call_id}.json").read_text(encoding="utf-8")
    )
    assert len(receipt["events"]) == 3
    assert receipt["events"][0]["event"] == "started"
    assert receipt["events"][1]["event"] == "progress"
    assert receipt["events"][2]["event"] == "completed"


# -- no-op when file does not exist -------------------------------------------


async def test_noop_when_file_does_not_exist(tmp_path):
    """When the receipt file does not exist, append_call_event is a no-op."""
    call_id = uuid4()

    # Should not raise, even though no file exists
    append_call_event(call_id, "completed", {"result": "ok"}, tmp_path)

    # No file should have been created
    assert not (tmp_path / "call" / f"{call_id}.json").exists()


# -- preserves existing receipt data -------------------------------------------


async def test_preserves_existing_receipt_fields(tmp_path):
    """Appending an event does not overwrite existing receipt fields."""
    call_id = uuid4()
    original = {
        "call_id": str(call_id),
        "tool_id": "my-tool",
        "arguments": {"name": "Dr. Smith"},
        "output": "Created successfully",
    }
    _create_receipt(tmp_path, call_id, data=original)

    append_call_event(call_id, "verified", {"check": True}, tmp_path)

    receipt = json.loads(
        (tmp_path / "call" / f"{call_id}.json").read_text(encoding="utf-8")
    )
    assert receipt["call_id"] == str(call_id)
    assert receipt["tool_id"] == "my-tool"
    assert receipt["arguments"] == {"name": "Dr. Smith"}
    assert receipt["output"] == "Created successfully"
    assert len(receipt["events"]) == 1
