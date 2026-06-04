"""Resource-exhaustion guard: CSV-import parse caps the row count.

Every artifact's CSV-import parse used to materialize the whole uploaded file
with ``all_rows = list(csv.reader(io.StringIO(content)))`` *before* any size
check. The mapped items it proposes are re-submitted through the bulk-create
endpoints, which are themselves capped at ``MAX_BULK_ITEMS`` (see
``test_bulk_items_cap``) — but that cap fires only *after* the full file has
already been read into memory, so a huge CSV could spike memory during parse
before being rejected. ``read_csv_rows_bounded`` closes that gap: it pulls rows
one at a time and aborts the moment the cap is crossed, so the oversized read
never completes.

This is a pure helper test — the file-like reader and the error factory are the
explicit deps, passed in via parametrize. No DB/redis.
"""

from __future__ import annotations

import io
from typing import Iterator

import pytest
from fastapi import HTTPException

from app.infra.shared_types import (
    MAX_BULK_ITEMS,
    MAX_CSV_ROWS,
    read_csv_rows_bounded,
)


class _CsvErr(ValueError):
    """Stand-in for an artifact's in-module ``CsvParseError`` (a ValueError)."""


def _make_csv(num_data_rows: int) -> str:
    """A header row plus ``num_data_rows`` single-column data rows."""
    lines = ["name"] + [f"row{i}" for i in range(num_data_rows)]
    return "\n".join(lines) + "\n"


# (label, error factory, expected exception type). The factory mirrors how each
# artifact wires its own client-CSV error: ValueError default, a CsvParseError
# subclass, and the HTTPException(422) lambda used by persona/scenario.
ERROR_FACTORIES = [
    ("default_valueerror", None, ValueError),
    ("csv_parse_error", _CsvErr, _CsvErr),
    (
        "http_exception",
        lambda msg: HTTPException(status_code=422, detail=msg),
        HTTPException,
    ),
]


def test_cap_is_tied_to_bulk_cap() -> None:
    """The row cap is the create cap plus the one mandatory header row, so a
    CSV that would overflow the create cap is rejected early."""
    assert MAX_CSV_ROWS == MAX_BULK_ITEMS + 1


@pytest.mark.parametrize("label, factory, exc_type", ERROR_FACTORIES)
def test_at_cap_accepted(label, factory, exc_type) -> None:
    """A header + MAX_BULK_ITEMS data rows (== MAX_CSV_ROWS lines) parses."""
    content = _make_csv(MAX_BULK_ITEMS)
    rows = read_csv_rows_bounded(io.StringIO(content), make_error=factory)
    assert len(rows) == MAX_CSV_ROWS
    assert rows[0] == ["name"]


@pytest.mark.parametrize("label, factory, exc_type", ERROR_FACTORIES)
def test_under_cap_accepted(label, factory, exc_type) -> None:
    """A small CSV (the common case) parses unchanged."""
    content = _make_csv(3)
    rows = read_csv_rows_bounded(io.StringIO(content), make_error=factory)
    assert len(rows) == 4  # header + 3


@pytest.mark.parametrize("label, factory, exc_type", ERROR_FACTORIES)
def test_over_cap_rejected(label, factory, exc_type) -> None:
    """One line past the cap is rejected with the artifact's own error type."""
    content = _make_csv(MAX_BULK_ITEMS + 1)  # MAX_CSV_ROWS + 1 lines total
    with pytest.raises(exc_type):
        read_csv_rows_bounded(io.StringIO(content), make_error=factory)


def test_rejects_before_full_materialization() -> None:
    """The read aborts *as soon as* the cap is crossed — it does not drain the
    whole file first. A reader that explodes once read past ``MAX_CSV_ROWS + 1``
    lines must still raise the clean cap error, proving the unbounded read never
    happens."""

    # The helper is allowed to pull at most MAX_CSV_ROWS + 1 lines (it reads one
    # past the cap to detect the overflow, then raises). If it ever read further
    # — i.e. drained the file before checking size — the explosion below would
    # surface instead of the clean cap error.
    read_budget = MAX_CSV_ROWS + 1

    def exploding_lines() -> Iterator[str]:
        for i in range(read_budget):
            yield f"row{i}\n"
        raise AssertionError("read past the cap — file was fully materialized")

    with pytest.raises(ValueError):
        read_csv_rows_bounded(exploding_lines())
