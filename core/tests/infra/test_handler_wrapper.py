"""Tests for pure payload shaping in handler wrapper."""

from pydantic import BaseModel

from app.infra.websocket.handler_wrapper import build_validation_payload


class RequestWithoutTransportFields(BaseModel):
    value: str


class RequestWithSid(BaseModel):
    sid: str
    value: str


class RequestWithGroupId(BaseModel):
    group_id: str
    value: str


def test_build_validation_payload_strips_sid_and_group_id_by_default():
    payload = build_validation_payload(
        {"sid": "sid-1", "group_id": "group-1", "value": "ok"},
        RequestWithoutTransportFields,
    )

    assert payload == {"value": "ok"}


def test_build_validation_payload_preserves_declared_sid():
    payload = build_validation_payload(
        {"sid": "sid-1", "group_id": "group-1", "value": "ok"},
        RequestWithSid,
    )

    assert payload == {"sid": "sid-1", "value": "ok"}


def test_build_validation_payload_preserves_declared_group_id():
    payload = build_validation_payload(
        {"sid": "sid-1", "group_id": "group-1", "value": "ok"},
        RequestWithGroupId,
    )

    assert payload == {"group_id": "group-1", "value": "ok"}
