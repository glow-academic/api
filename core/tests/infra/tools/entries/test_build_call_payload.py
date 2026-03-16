"""Tests for build_call_payload."""

from tests.helpers import nonexistent_id

from app.infra.tools.entries.build_call_payload import build_call_payload


def test_has_correct_keys():
    payload = build_call_payload(
        call_id=nonexistent_id(),
        tool_id=nonexistent_id(),
        arguments={"name": "Dr. Smith"},
        output={"success": True},
    )
    assert set(payload.keys()) == {"call_id", "tool_id", "arguments", "output"}


def test_serializes_uuids():
    call_id = nonexistent_id()
    tool_id = nonexistent_id()
    payload = build_call_payload(
        call_id=call_id,
        tool_id=tool_id,
        arguments={},
        output={},
    )
    assert payload["call_id"] == str(call_id)
    assert payload["tool_id"] == str(tool_id)


def test_preserves_arguments():
    args = {"name": "Dr. Smith", "department": "Cardiology", "count": 3}
    payload = build_call_payload(
        call_id=nonexistent_id(),
        tool_id=nonexistent_id(),
        arguments=args,
        output={},
    )
    assert payload["arguments"] == args


def test_preserves_output():
    output = {"success": True, "message": "Created", "entry_id": "123"}
    payload = build_call_payload(
        call_id=nonexistent_id(),
        tool_id=nonexistent_id(),
        arguments={},
        output=output,
    )
    assert payload["output"] == output
