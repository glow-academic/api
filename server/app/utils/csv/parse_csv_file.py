"""Parse CSV file containing user data."""

import csv
import io
from typing import Any


def parse_csv_file(file_path: str) -> dict[str, Any]:
    """
    Parse a CSV file containing user data and return structured data.

    Expected CSV format:
    name,username
    John Doe,john_doe
    Jane Smith,jane_smith

    Args:
        file_path: Path to the CSV file

    Returns:
        Dictionary with parsing results:
        - success: bool - whether parsing was successful
        - users: List[Dict] - list of parsed user dictionaries
        - errors: List[str] - list of validation errors
        - error: str (optional) - error message if parsing failed
    """
    try:
        users = []
        errors = []

        with open(file_path, encoding="utf-8") as file:
            # Read the CSV content
            csv_content = file.read()

            # Use StringIO to create a file-like object
            csv_file = io.StringIO(csv_content)

            # Create CSV reader
            csv_reader = csv.DictReader(csv_file)

            # Validate headers
            expected_headers = {"name", "username"}
            actual_headers = set(csv_reader.fieldnames or [])

            if not expected_headers.issubset(actual_headers):
                missing_headers = expected_headers - actual_headers
                return {
                    "success": False,
                    "error": f"Missing required headers: {', '.join(missing_headers)}",
                    "users": [],
                    "errors": [],
                }

            # Process each row
            for row_num, row in enumerate(
                csv_reader, start=2
            ):  # Start at 2 because row 1 is headers
                # Extract and validate data
                name = row.get("name", "").strip()
                username = row.get("username", "").strip()

                if not name or not username:
                    errors.append(
                        f"Row {row_num}: Missing required fields (name, username)"
                    )
                    continue

                users.append({"name": name, "username": username, "row_num": row_num})

            return {
                "success": True,
                "users": users,
                "errors": errors,
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse CSV file: {str(e)}",
            "users": [],
            "errors": [],
        }
