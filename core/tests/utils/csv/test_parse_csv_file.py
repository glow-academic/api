"""Tests for parse_csv_file."""

from pathlib import Path

from app.utils.csv.parse_csv_file import parse_csv_file


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_parses_valid_rows_and_collects_row_numbers(tmp_path):
    path = _write(
        tmp_path,
        "users.csv",
        "name,username\nAlice,alice_1\nBob,bob_2\n",
    )

    result = parse_csv_file(path)

    assert result["success"] is True
    assert result["errors"] == []
    assert result["users"] == [
        {"name": "Alice", "username": "alice_1", "row_num": 2},
        {"name": "Bob", "username": "bob_2", "row_num": 3},
    ]


def test_skips_invalid_rows_and_reports_errors(tmp_path):
    path = _write(
        tmp_path,
        "users.csv",
        "name,username\nAlice,alice_1\nMissing Username,\n,missing_name\n",
    )

    result = parse_csv_file(path)

    assert result["success"] is True
    assert result["users"] == [{"name": "Alice", "username": "alice_1", "row_num": 2}]
    assert result["errors"] == [
        "Row 3: Missing required fields (name, username)",
        "Row 4: Missing required fields (name, username)",
    ]


def test_returns_error_when_required_headers_are_missing(tmp_path):
    path = _write(tmp_path, "users.csv", "name,email\nAlice,alice@example.com\n")

    result = parse_csv_file(path)

    assert result["success"] is False
    assert "Missing required headers" in result["error"]
    assert result["users"] == []
