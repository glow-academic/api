"""Validate CSV file format."""

import csv
import io
from typing import Any


def validate_csv_format(file_path: str) -> dict[str, Any]:
    """
    Validate CSV file format without processing it.

    Args:
        file_path: Path to the CSV file

    Returns:
        Dictionary with validation results
    """
    try:
        with open(file_path, encoding="utf-8") as file:
            csv_content = file.read()
            csv_file = io.StringIO(csv_content)
            csv_reader = csv.DictReader(csv_file)

            # Check headers
            expected_headers = {"name", "username"}
            actual_headers = set(csv_reader.fieldnames or [])

            if not expected_headers.issubset(actual_headers):
                missing_headers = expected_headers - actual_headers
                return {
                    "valid": False,
                    "error": f"Missing required headers: {', '.join(missing_headers)}",
                    "expected_headers": list(expected_headers),
                    "actual_headers": list(actual_headers),
                }

            # Count rows
            row_count = sum(1 for _ in csv_reader)

            return {
                "valid": True,
                "row_count": row_count,
                "headers": list(actual_headers),
            }

    except Exception as e:
        return {"valid": False, "error": f"Failed to validate CSV file: {str(e)}"}
