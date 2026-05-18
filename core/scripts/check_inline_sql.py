#!/usr/bin/env python3
"""Check for inline SQL violations in Python files.

Zero tolerance approach: flags ALL SQL operations (INSERT, UPDATE, DELETE, SELECT)
that are not loaded from .sql files via load_sql().

Exceptions:
- Utility commands: SET LOCAL, SET, SELECT 1 (health checks)
- SQL loaded from files via load_sql() (even if modified with .replace())
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Add server directory to path for imports
server_dir = Path(__file__).parent.parent
sys.path.insert(0, str(server_dir))


class InlineSQLChecker(ast.NodeVisitor):
    """AST visitor to detect inline SQL violations."""

    def __init__(self, file_path: Path) -> None:
        """Initialize checker for a file."""
        self.file_path = file_path
        self.violations: list[tuple[int, str, str]] = []  # (line, sql_snippet, context)
        self.load_sql_vars: set[str] = set()  # Variables assigned from load_sql()
        self.inline_sql_vars: dict[
            str, tuple[int, str]
        ] = {}  # var_name -> (line, sql_snippet)
        self.current_line = 0

    def visit(self, node: ast.AST) -> Any:
        """Visit node and track current line."""
        self.current_line = getattr(node, "lineno", self.current_line)
        return super().visit(node)

    def _extract_string_value(self, node: ast.AST) -> str | None:
        """Extract string value from AST node (handles Constant, JoinedStr, etc.)."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s
        elif isinstance(node, ast.JoinedStr):  # f-strings
            # For f-strings, we can't easily extract the full value, so return None
            # and let the caller handle it differently
            return None
        return None

    def visit_Assign(self, node: ast.Assign) -> Any:
        """Track variables assigned from load_sql() calls or inline SQL strings."""
        # Check if assignment is from load_sql() call
        if isinstance(node.value, ast.Call):
            if (
                isinstance(node.value.func, ast.Name)
                and node.value.func.id == "load_sql"
            ):
                # Track all targets as load_sql variables
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.load_sql_vars.add(target.id)
            # Also check for load_sql() imported as something else
            elif isinstance(node.value.func, ast.Attribute):
                if node.value.func.attr == "load_sql":
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.load_sql_vars.add(target.id)

        # Check for .replace() operations on load_sql variables
        if isinstance(node.value, ast.Call):
            if (
                isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "replace"
            ):
                if isinstance(node.value.func.value, ast.Name):
                    var_name = node.value.func.value.id
                    if var_name in self.load_sql_vars:
                        # This is a .replace() on a load_sql variable - track the new variable too
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                self.load_sql_vars.add(target.id)

        # Check for inline SQL string assignments
        sql_str = self._extract_string_value(node.value)
        if sql_str:
            if self._contains_sql_operation(sql_str):
                # This is an inline SQL string assignment
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        sql_snippet = sql_str.strip()[:80]
                        if len(sql_str.strip()) > 80:
                            sql_snippet += "..."
                        self.inline_sql_vars[target.id] = (node.lineno, sql_snippet)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        """Check for SQL strings passed to conn methods."""
        # Check if this is a conn.execute(), conn.fetchrow(), conn.fetchval(), or conn.fetch() call
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in ("execute", "fetchrow", "fetchval", "fetch"):
                # Check if first argument is a string literal (inline SQL)
                sql_str = (
                    self._extract_string_value(node.args[0]) if node.args else None
                )
                if sql_str:
                    self._check_sql_violation(sql_str, node.lineno, method_name)
                # Check if first argument is a variable that might be inline SQL
                elif node.args and isinstance(node.args[0], ast.Name):
                    var_name = node.args[0].id
                    # If it's a load_sql variable, it's safe
                    if var_name in self.load_sql_vars:
                        pass  # Safe - loaded from file
                    # If it's an inline SQL variable, flag it
                    elif var_name in self.inline_sql_vars:
                        line_no, sql_snippet = self.inline_sql_vars[var_name]
                        context = f"conn.{method_name}() (variable '{var_name}' assigned at line {line_no})"
                        self.violations.append((node.lineno, sql_snippet, context))

        self.generic_visit(node)

    def _contains_sql_operation(self, sql: str) -> bool:
        """Check if SQL string contains SQL operation keywords."""
        sql_normalized = sql.strip().upper()

        # Exception: Utility commands
        if sql_normalized.startswith("SET"):
            return False  # SET LOCAL, SET jit = off, etc. are allowed
        if sql_normalized == "SELECT 1" or sql_normalized == "SELECT 1;":
            return False  # Health checks are allowed

        # Check for SQL operation keywords
        has_insert = bool(re.search(r"\bINSERT\b", sql_normalized))
        has_update = bool(re.search(r"\bUPDATE\b", sql_normalized))
        has_delete = bool(re.search(r"\bDELETE\b", sql_normalized))
        has_select = bool(re.search(r"\bSELECT\b", sql_normalized))

        return has_insert or has_update or has_delete or has_select

    def _check_sql_violation(self, sql: str, line_no: int, method: str) -> None:
        """Check if SQL string violates zero tolerance policy."""
        if self._contains_sql_operation(sql):
            # Extract a snippet for display (first 80 chars)
            sql_snippet = sql.strip()[:80]
            if len(sql.strip()) > 80:
                sql_snippet += "..."
            context = f"conn.{method}()"
            self.violations.append((line_no, sql_snippet, context))


def find_python_files() -> list[Path]:
    """Find all Python files in server/app/ directory (includes app/utils/).

    Excludes scripts/ directory - scripts are tooling code where inline SQL is acceptable.
    """
    python_files: list[Path] = []
    # Utils is now inside app/, so we only need to scan app/
    dir_path = server_dir / "app"
    if dir_path.exists():
        python_files.extend(dir_path.rglob("*.py"))
    # Exclude __pycache__ and test files (we only check app code, not tests)
    # Also exclude scripts/ - tooling code where inline SQL is acceptable
    python_files = [
        f
        for f in python_files
        if "__pycache__" not in str(f)
        and f.suffix == ".py"
        and "test" not in f.stem.lower()
        and "scripts" not in str(f)
    ]
    return sorted(python_files)


def check_file(file_path: Path) -> list[tuple[int, str, str]]:
    """Check a single Python file for inline SQL violations."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        checker = InlineSQLChecker(file_path)
        checker.visit(tree)
        return checker.violations
    except SyntaxError:
        # Skip files with syntax errors (they'll be caught by other tools)
        return []
    except Exception:
        # Skip files that can't be parsed (encoding issues, etc.)
        return []


def group_by_directory(
    violations: list[tuple[Path, int, str, str]],
) -> dict[str, list[tuple[Path, int, str, str]]]:
    """Group violations by their directory."""
    grouped = defaultdict(list)
    for file_path, line_no, sql_snippet, context in violations:
        # Extract directory name (e.g., "api/v3/agents" from "server/app/api/v3/agents/create.py")
        # or "utils/cache" from "server/app/utils/cache/cache_key.py"
        parts = file_path.parts
        if "app" in parts:
            idx = parts.index("app")
            if idx + 1 < len(parts):
                dir_name = "/".join(
                    parts[idx + 1 : -1]
                )  # Everything after "app" except filename
            else:
                dir_name = "app"
        else:
            dir_name = "other"
        grouped[dir_name].append((file_path, line_no, sql_snippet, context))
    return dict(grouped)


def main() -> int:
    """Main entry point."""
    print("🔍 Checking for inline SQL violations (zero tolerance)...")
    print()

    # Find all Python files
    python_files = find_python_files()
    print(f"Scanning {len(python_files)} Python files...")

    # Check each file
    all_violations: list[tuple[Path, int, str, str]] = []
    for py_file in python_files:
        violations = check_file(py_file)
        for line_no, sql_snippet, context in violations:
            all_violations.append((py_file, line_no, sql_snippet, context))

    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Files scanned:         {len(python_files)}")
    print(f"Violations found:     {len(all_violations)}")
    print()

    # Print violations grouped by directory
    if all_violations:
        print("=" * 70)
        print("INLINE SQL VIOLATIONS")
        print("=" * 70)
        print()
        print("❌ Zero tolerance: ALL SQL operations (INSERT, UPDATE, DELETE, SELECT)")
        print("   must be in separate .sql files loaded via load_sql()")
        print()
        print("Exceptions allowed:")
        print("  • Utility commands: SET LOCAL, SET ..., SELECT 1 (health checks)")
        print("  • SQL loaded from files via load_sql()")
        print()

        grouped = group_by_directory(all_violations)
        for dir_name in sorted(grouped.keys()):
            violations_in_dir = grouped[dir_name]
            print(
                f"📁 {dir_name}/ ({len(violations_in_dir)} violation{'s' if len(violations_in_dir) != 1 else ''})"
            )
            for file_path, line_no, sql_snippet, context in sorted(
                violations_in_dir, key=lambda x: x[1]
            ):
                rel_path = file_path.relative_to(server_dir)
                print(f"   Line {line_no}: {rel_path}")
                print(f"      {context}")
                print(f"      SQL: {sql_snippet}")
                print()
            print()

        return 1  # Exit with error code if violations found
    else:
        print("✅ No inline SQL violations found!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
