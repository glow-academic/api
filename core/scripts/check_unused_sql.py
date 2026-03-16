#!/usr/bin/env python3
"""Check for unused SQL files in the codebase.

Finds all SQL files in server/app/sql/ and checks if they're referenced
via load_sql() calls in Python files.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

# Add server directory to path for imports
server_dir = Path(__file__).parent.parent
sys.path.insert(0, str(server_dir))


def find_all_sql_files() -> list[Path]:
    """Find all SQL files in server/app/sql/."""
    sql_dir = server_dir / "app" / "sql"
    if not sql_dir.exists():
        print(f"❌ SQL directory not found: {sql_dir}")
        sys.exit(1)

    sql_files = list(sql_dir.rglob("*.sql"))
    return sorted(sql_files)


def sql_file_to_load_path(sql_file: Path) -> str:
    """Convert SQL file path to load_sql() format.

    Example:
        server/app/sql/queries/reports/reports_bundle.sql ->
        app/sql/queries/reports/reports_bundle.sql
    """
    # Get relative path from server directory
    relative = sql_file.relative_to(server_dir)
    return str(relative)


def find_python_files() -> list[Path]:
    """Find all Python files in server/ directory."""
    python_files = []
    for ext in ["*.py"]:
        python_files.extend(server_dir.rglob(ext))
    # Exclude __pycache__ and .pyc files
    python_files = [
        f for f in python_files if "__pycache__" not in str(f) and f.suffix == ".py"
    ]
    return sorted(python_files)


def extract_all_load_sql_paths(python_files: list[Path]) -> set[str]:
    """Extract all SQL file paths referenced in load_sql() calls.

    Reads all Python files once and extracts all load_sql() paths.
    Returns a set of all referenced SQL file paths in normalized format (app/sql/{VERSION}/...).

    Normalizes paths to standard format:
    - sql/{VERSION}/... -> app/sql/{VERSION}/... (legacy format, should be migrated)
    - app/sql/{VERSION}/... -> app/sql/{VERSION}/... (standard format)
    - Also checks for execute_sql_typed() calls with SQL paths
    - Also checks for SQL_PATH = "..." constant assignments
    - Also checks for load_sql_query() calls with string literals
    """
    referenced_paths = set()

    # Pattern to match load_sql("path") or load_sql('path')
    # Captures the path inside quotes
    load_sql_pattern = re.compile(r'load_sql\s*\(\s*["\']([^"\']+)["\']\s*\)')

    # Pattern to match execute_sql_typed(conn, "path", ...) or execute_sql_typed(conn, 'path', ...)
    execute_sql_pattern = re.compile(
        r'execute_sql_typed\s*\(\s*[^,]+,\s*["\']([^"\']+)["\']'
    )

    # Pattern to match load_sql_query("path") or load_sql_query('path')
    load_sql_query_pattern = re.compile(
        r'load_sql_query\s*\(\s*["\']([^"\']+)["\']\s*\)'
    )

    # Pattern to match SQL_PATH = "path" or SQL_PATH = 'path' (constant assignments)
    sql_path_pattern = re.compile(r'SQL_PATH\s*=\s*["\']([^"\']+)["\']')

    for py_file in python_files:
        try:
            content = py_file.read_text(encoding="utf-8")

            # Find load_sql() calls
            matches = load_sql_pattern.findall(content)
            for match in matches:
                # Normalize paths: sql/{VERSION}/... -> app/sql/{VERSION}/...
                normalized = match
                if match.startswith(f"sql/{VERSION}/"):
                    normalized = "app/" + match
                referenced_paths.add(normalized)

            # Find execute_sql_typed() calls
            execute_matches = execute_sql_pattern.findall(content)
            for match in execute_matches:
                # Normalize paths: sql/{VERSION}/... -> app/sql/{VERSION}/...
                normalized = match
                if match.startswith(f"sql/{VERSION}/"):
                    normalized = "app/" + match
                referenced_paths.add(normalized)

            # Find load_sql_query() calls
            load_sql_query_matches = load_sql_query_pattern.findall(content)
            for match in load_sql_query_matches:
                # Normalize paths: sql/{VERSION}/... -> app/sql/{VERSION}/...
                normalized = match
                if match.startswith(f"sql/{VERSION}/"):
                    normalized = "app/" + match
                referenced_paths.add(normalized)

            # Find SQL_PATH constant assignments
            sql_path_matches = sql_path_pattern.findall(content)
            for match in sql_path_matches:
                # Normalize paths: sql/{VERSION}/... -> app/sql/{VERSION}/...
                normalized = match
                if match.startswith(f"sql/{VERSION}/"):
                    normalized = "app/" + match
                referenced_paths.add(normalized)
        except Exception:
            # Skip files that can't be read (permissions, encoding issues, etc.)
            continue

    return referenced_paths


def get_types_registry_paths() -> set[str]:
    """Extract SQL file paths from the types.py registry.

    Returns a set of all SQL file paths that are registered in the types.py file.
    This indicates they are compiled and likely being used.
    """
    types_file = server_dir / "app" / "sql" / "types.py"
    if not types_file.exists():
        return set()

    referenced_paths = set()

    try:
        content = types_file.read_text(encoding="utf-8")

        # Pattern to match registry entries: "app/sql/...": (
        # This matches the _registry dictionary entries
        registry_pattern = re.compile(
            r'["\'](app/sql/' + VERSION + r'/[^"\']+)["\']\s*:'
        )

        matches = registry_pattern.findall(content)
        for match in matches:
            referenced_paths.add(match)
    except Exception:
        # Skip if file can't be read
        pass

    return referenced_paths


def group_by_directory(
    unused_files: list[tuple[str, Path]],
) -> dict[str, list[tuple[str, Path]]]:
    """Group unused files by their resource directory."""
    grouped = defaultdict(list)
    for load_path, file_path in unused_files:
        # Extract resource directory (e.g., "reports" from "app/sql/queries/reports/reports_bundle.sql")
        parts = load_path.split("/")
        if len(parts) >= 5 and parts[3] in ("queries", "views"):
            resource = parts[4] if parts[3] == "queries" else parts[3]
            grouped[resource].append((load_path, file_path))
        else:
            grouped["other"].append((load_path, file_path))
    return dict(grouped)


def main() -> int:
    """Main entry point."""
    print("🔍 Checking for unused SQL files...")
    print()

    # Find all SQL files
    sql_files = find_all_sql_files()
    print(f"Found {len(sql_files)} SQL files")

    # Find all Python files and extract referenced SQL paths
    python_files = find_python_files()
    print(f"Searching in {len(python_files)} Python files")
    print("Extracting load_sql() references...")

    referenced_paths = extract_all_load_sql_paths(python_files)
    print(f"Found {len(referenced_paths)} referenced SQL files from Python code")

    # Also check types.py registry
    types_registry_paths = get_types_registry_paths()
    print(f"Found {len(types_registry_paths)} SQL files in types.py registry")
    referenced_paths.update(types_registry_paths)
    print(f"Total unique referenced SQL files: {len(referenced_paths)}")
    print()

    # Check each SQL file against referenced paths
    used_files = []
    unused_files = []

    for sql_file in sql_files:
        load_path = sql_file_to_load_path(sql_file)
        if load_path in referenced_paths:
            used_files.append(sql_file)
        else:
            unused_files.append((load_path, sql_file))

    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total SQL files:     {len(sql_files)}")
    print(f"Used files:          {len(used_files)}")
    print(f"Unused files:        {len(unused_files)}")
    print()

    # Print unused files grouped by directory
    if unused_files:
        print("=" * 70)
        print("UNUSED SQL FILES")
        print("=" * 70)
        print()

        grouped = group_by_directory(unused_files)
        for resource in sorted(grouped.keys()):
            files = grouped[resource]
            print(f"📁 {resource}/ ({len(files)} file{'s' if len(files) != 1 else ''})")
            for load_path, _ in sorted(files):
                print(f"   • {load_path}")
            print()

        return 1  # Exit with error code if unused files found
    else:
        print("✅ All SQL files are in use!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
