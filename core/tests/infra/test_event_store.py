"""Tests for the naive call-receipt event store helpers."""

from datetime import datetime
from uuid import uuid4

from app.infra.events.store import _project_call_receipt, build_event_cursor


def test_project_call_receipt_emits_domain_and_lifecycle_events() -> None:
    call_id = uuid4()
    tool_id = uuid4()
    entity_id = uuid4()
    created_at = datetime(2026, 3, 10, 12, 0, 0)

    events = _project_call_receipt(
        artifact="persona",
        operation="get",
        entity_id=entity_id,
        created_at=created_at,
        call_id=call_id,
        tool_id=tool_id,
        receipt={
            "arguments": {"persona_id": str(entity_id)},
            "output": {"success": True, "results": []},
        },
    )

    assert [event.event_type for event in events] == [
        "artifacts.persona.get.started",
        "artifacts.persona.get.completed",
        "artifacts.persona.viewed",
    ]
    assert events[-1].entity_id == entity_id
    assert build_event_cursor(events[-1]).startswith(created_at.isoformat())


def test_project_call_receipt_skips_domain_events_on_failure() -> None:
    events = _project_call_receipt(
        artifact="persona",
        operation="update",
        entity_id=uuid4(),
        created_at=datetime(2026, 3, 10, 12, 0, 0),
        call_id=uuid4(),
        tool_id=uuid4(),
        receipt={
            "arguments": {},
            "output": {"success": False, "message": "bad"},
        },
    )

    assert [event.event_type for event in events] == [
        "artifacts.persona.update.started",
        "artifacts.persona.update.failed",
    ]


def test_project_call_receipt_emits_bulk_persona_events_per_result_id() -> None:
    first_id = uuid4()
    second_id = uuid4()
    events = _project_call_receipt(
        artifact="persona",
        operation="create",
        entity_id=None,
        created_at=datetime(2026, 3, 10, 12, 0, 0),
        call_id=uuid4(),
        tool_id=uuid4(),
        receipt={
            "arguments": {"personas": [{"name": "One"}, {"name": "Two"}]},
            "output": {
                "success": True,
                "results": [
                    {"success": True, "persona_id": str(first_id), "message": "ok"},
                    {"success": True, "persona_id": str(second_id), "message": "ok"},
                ],
            },
        },
    )

    domain_events = [
        event for event in events if event.event_type == "artifacts.persona.created"
    ]
    assert [event.entity_id for event in domain_events] == [first_id, second_id]


def test_project_call_receipt_skips_multi_domain_workflow_projection() -> None:
    attempt_id = uuid4()
    events = _project_call_receipt(
        artifact="attempt",
        operation="grade",
        entity_id=attempt_id,
        created_at=datetime(2026, 3, 10, 12, 0, 0),
        call_id=uuid4(),
        tool_id=uuid4(),
        receipt={
            "arguments": {"attempt_id": str(attempt_id)},
            "output": {
                "success": True,
                "chat_id": str(uuid4()),
                "grade_id": str(uuid4()),
            },
        },
    )

    assert [event.event_type for event in events] == [
        "artifacts.attempt.grade.started",
        "artifacts.attempt.grade.completed",
    ]


def test_project_call_receipt_attaches_attempt_start_entity_to_lifecycle() -> None:
    attempt_id = uuid4()
    events = _project_call_receipt(
        artifact="attempt",
        operation="start",
        entity_id=None,
        created_at=datetime(2026, 3, 10, 12, 0, 0),
        call_id=uuid4(),
        tool_id=uuid4(),
        receipt={
            "arguments": {"home_id": str(uuid4()), "infinite_mode": False},
            "output": {
                "attempt_id": str(attempt_id),
                "chat_entry_id": None,
                "attempt_chat_id": None,
            },
        },
    )

    assert [event.event_type for event in events] == [
        "artifacts.attempt.start.started",
        "artifacts.attempt.start.completed",
    ]
    assert events[0].entity_id == attempt_id
    assert events[1].entity_id == attempt_id


def test_project_call_receipt_skips_domain_projection_for_bridged_stop_workflow() -> None:
    invocation_id = uuid4()
    events = _project_call_receipt(
        artifact="test",
        operation="stop",
        entity_id=invocation_id,
        created_at=datetime(2026, 3, 10, 12, 0, 0),
        call_id=uuid4(),
        tool_id=uuid4(),
        receipt={
            "arguments": {"invocation_id": str(invocation_id)},
            "output": {
                "success": True,
                "invocation_id": str(invocation_id),
                "message": "stopped",
            },
        },
    )

    assert [event.event_type for event in events] == [
        "artifacts.test.stop.started",
        "artifacts.test.stop.completed",
    ]
