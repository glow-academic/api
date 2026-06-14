"""Tests for the formula-injection-safe CSV writer (G1).

CSV/spreadsheet formula injection: a cell whose text begins with ``=`` ``+`` ``-``
``@`` ``\\t`` ``\\r`` is interpreted as a live formula when the exported file is
opened in Excel / Google Sheets / LibreOffice. ``safe_csv_cell`` / ``FormulaSafeWriter``
neutralize this by prefixing such cells with a single-quote (OWASP guidance).
"""

import csv
import io

import pytest

from app.utils.csv.formula_safe import (
    FormulaSafeWriter,
    safe_csv_cell,
)

# The full OWASP trigger set this fix must neutralize.
TRIGGER_CHARS = ["=", "+", "-", "@", "\t", "\r"]

# Formula-*leader* chars (the non-whitespace subset). These are the triggers that
# can hide behind leading whitespace; ``\t``/``\r`` are themselves whitespace and
# are consumed by ``lstrip()``, so they only matter as the genuine first char.
FORMULA_LEADERS = ["=", "+", "-", "@"]


# ── safe_csv_cell: each trigger char is neutralized ───────────────────────────


@pytest.mark.parametrize("trigger", TRIGGER_CHARS)
def test_trigger_leading_value_is_prefixed(trigger: str) -> None:
    payload = f"{trigger}cmd|'/C calc'!A0"

    out = safe_csv_cell(payload)

    assert out == "'" + payload
    assert out[0] == "'"


@pytest.mark.parametrize("trigger", TRIGGER_CHARS)
def test_only_leading_trigger_matters(trigger: str) -> None:
    # A trigger char in the *middle* of the value is not a formula leader and
    # must be left untouched.
    value = f"safe{trigger}value"

    assert safe_csv_cell(value) == value


# ── safe_csv_cell: leading-whitespace-then-trigger (R10) ──────────────────────


@pytest.mark.parametrize("trigger", FORMULA_LEADERS)
def test_leading_space_then_trigger_is_prefixed(trigger: str) -> None:
    # R10: classic Excel treats a leading space as text, but Google Sheets / some
    # LibreOffice import paths strip leading whitespace before evaluating — so a
    # leading-space-then-trigger value is still a live formula and must be
    # neutralized.
    payload = f" {trigger}HYPERLINK('http://evil','x')"

    out = safe_csv_cell(payload)

    assert out == "'" + payload
    assert out[0] == "'"


@pytest.mark.parametrize("trigger", FORMULA_LEADERS)
def test_leading_newline_then_trigger_is_prefixed(trigger: str) -> None:
    # R10: a leading newline (or other whitespace) before the trigger is stripped
    # by some import paths too.
    payload = f"\n{trigger}cmd|'/C calc'!A0"

    out = safe_csv_cell(payload)

    assert out == "'" + payload
    assert out[0] == "'"


def test_whitespace_only_value_unchanged() -> None:
    # R10: lstrip() on a whitespace-only string yields "" (not a trigger), so it
    # must pass through untouched.
    assert safe_csv_cell("   ") == "   "


# ── safe_csv_cell: normal values round-trip ───────────────────────────────────


def test_plain_text_unchanged() -> None:
    assert safe_csv_cell("Alice Smith") == "Alice Smith"


def test_empty_string_unchanged() -> None:
    assert safe_csv_cell("") == ""


def test_non_string_values_passthrough() -> None:
    # ints / floats / None are handed to the csv writer untouched.
    assert safe_csv_cell(42) == 42
    assert safe_csv_cell(3.14) == 3.14
    assert safe_csv_cell(None) is None


def test_negative_number_string_is_prefixed_by_design() -> None:
    # DECISION (OWASP): a legitimate negative-number *string* leads with ``-`` and
    # is therefore prefixed. We accept this rather than try to distinguish "real"
    # numbers from a ``-2+3+cmd|...`` payload (that heuristic is a known bypass).
    assert safe_csv_cell("-12.5") == "'-12.5"


def test_numeric_negative_int_is_not_a_string_so_passthrough() -> None:
    # When a real number is passed as an int/float (not a str) it is untouched —
    # the spreadsheet still types it numerically.
    assert safe_csv_cell(-12) == -12
    assert safe_csv_cell(-3.5) == -3.5


# ── FormulaSafeWriter: end-to-end CSV output ──────────────────────────────────


def _render(rows: list) -> str:
    buf = io.StringIO()
    writer = FormulaSafeWriter(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


@pytest.mark.parametrize("trigger", TRIGGER_CHARS)
def test_writer_neutralizes_each_trigger_in_output(trigger: str) -> None:
    raw = f"{trigger}HYPERLINK(0)"
    output = _render([[raw]])

    # Re-parse the CSV and confirm the stored cell now begins with the safe prefix
    # (so the spreadsheet treats it as text, not a formula).
    parsed = next(csv.reader(io.StringIO(output)))
    assert parsed[0] == "'" + raw
    assert parsed[0][0] == "'"


def test_writer_roundtrips_normal_values() -> None:
    rows = [
        ["id", "name", "active"],
        ["1", "Alice Smith", "Yes"],
        ["2", "Bob Jones", "No"],
    ]

    output = _render(rows)

    assert list(csv.reader(io.StringIO(output))) == rows


def test_writer_header_row_sanitized_too() -> None:
    # Header cells go through the same path; harmless for code-defined headers.
    output = _render([["=weird_header", "name"]])
    parsed = next(csv.reader(io.StringIO(output)))
    assert parsed == ["'=weird_header", "name"]


def test_writerows_sanitizes_all_rows() -> None:
    buf = io.StringIO()
    writer = FormulaSafeWriter(buf)
    writer.writerows([["=a"], ["+b"], ["plain"]])

    parsed = list(csv.reader(io.StringIO(buf.getvalue())))
    assert parsed == [["'=a"], ["'+b"], ["plain"]]


def test_writer_preserves_csv_quoting_for_embedded_delimiters() -> None:
    # The neutralization must not break ordinary CSV grammar handling.
    output = _render([["has,comma", 'has"quote', "line\nbreak"]])
    parsed = list(csv.reader(io.StringIO(output)))
    assert parsed == [["has,comma", 'has"quote', "line\nbreak"]]


def test_writer_neutralizes_realistic_profile_name_payload() -> None:
    # Headline G1 scenario: a student names themselves a formula; the admin roster
    # export must not execute it on open.
    malicious_name = "=cmd|'/C calc'!A0"
    output = _render([["id", "name"], ["42", malicious_name]])
    rows = list(csv.reader(io.StringIO(output)))
    assert rows[1][1] == "'" + malicious_name
