"""Tests for extracted error payload builders in handler wrapper."""

from app.infra.websocket.handler_wrapper import (
    build_client_error_payload,
    build_generate_error_forward_payload,
    build_generate_error_validation_payload,
    build_handler_error_message,
    is_generate_error_event,
)


def test_build_generate_error_forward_payload_preserves_transport_context():
    payload = build_generate_error_forward_payload(
        "sid-1",
        {
            "resource_id": "resource-1",
            "group_id": "group-1",
            "resource_type": "document",
            "ignored": "value",
        },
        "Profile lookup failed: boom",
    )

    assert payload == {
        "sid": "sid-1",
        "error_message": "Profile lookup failed: boom",
        "resource_id": "resource-1",
        "group_id": "group-1",
        "resource_type": "document",
    }


def test_build_generate_error_validation_payload_uses_client_message_shape():
    payload = build_generate_error_validation_payload(
        "sid-1",
        {
            "resource_id": "resource-1",
            "group_id": "group-1",
            "resource_type": "document",
        },
        "Invalid payload",
    )

    assert payload == {
        "sid": "sid-1",
        "success": False,
        "message": "Invalid payload",
        "resource_id": "resource-1",
        "group_id": "group-1",
    }


def test_build_client_error_payload_uses_standard_shape():
    assert build_client_error_payload("broken") == {
        "success": False,
        "message": "broken",
    }


def test_build_handler_error_message_is_generic_and_does_not_leak():
    # The raw exception text must NOT reach the WS client (info-disclosure,
    # same class as #208 on the HTTP path) — only a generic message.
    msg = build_handler_error_message(ValueError("bad input: table users col x"))
    assert "bad input" not in msg
    assert "users" not in msg
    assert msg == "Handler error. Please try again."


def test_is_generate_error_event_only_matches_generate_error():
    assert is_generate_error_event("generate_error") is True
    assert is_generate_error_event("other_error") is False
    assert is_generate_error_event(None) is False
