"""Tests for validate_csv_format."""

from pathlib import Path

from app.utils.csv.validate_csv_format import validate_csv_format


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_validates_expected_headers_and_row_count(tmp_path):
    path = _write(
        tmp_path,
        "users.csv",
        "name,username\nAlice,alice_1\nBob,bob_2\n",
    )

    result = validate_csv_format(path)

    assert result["valid"] is True
    assert result["row_count"] == 2
    assert set(result["headers"]) == {"name", "username"}


def test_reports_missing_headers(tmp_path):
    path = _write(tmp_path, "users.csv", "name,email\nAlice,alice@example.com\n")

    result = validate_csv_format(path)

    assert result["valid"] is False
    assert "Missing required headers" in result["error"]
    assert set(result["actual_headers"]) == {"name", "email"}


def test_reports_read_errors(tmp_path):
    path = str(tmp_path / "missing.csv")

    result = validate_csv_format(path)

    assert result["valid"] is False
    assert "Failed to validate CSV file" in result["error"]
