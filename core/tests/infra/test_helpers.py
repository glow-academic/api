"""Tests for shared infra helpers."""

from dataclasses import dataclass
from uuid import uuid4

from app.infra.helpers import dedupe_by_id


@dataclass
class Item:
    id: object | None
    label: str


def test_dedupe_by_id_preserves_first_seen_order():
    shared = uuid4()
    other = uuid4()

    result = dedupe_by_id(
        [
            Item(shared, "first"),
            Item(shared, "duplicate"),
            Item(other, "second"),
        ]
    )

    assert [item.label for item in result] == ["first", "second"]


def test_dedupe_by_id_skips_missing_or_none_ids():
    result = dedupe_by_id(
        [
            Item(None, "skip-none"),
            object(),
            Item(uuid4(), "keep"),
        ]
    )

    assert len(result) == 1
    assert result[0].label == "keep"
