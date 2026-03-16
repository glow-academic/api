#!/usr/bin/env python3
"""
Restore user_departments CTE blocks that were incorrectly removed.

The user_departments CTE queries profile_departments_junction (NOT the view)
and is used for internal filtering. It should NOT have been removed.

This script:
1. Finds files that reference user_departments but don't define the CTE
2. Extracts the original CTE from git HEAD
3. Re-inserts it in the correct position
"""

import re
import subprocess
from pathlib import Path

BASE = Path("/Users/ashoksaravanan/Coding/glow/server/app/sql/v4/queries")
REPO_ROOT = Path("/Users/ashoksaravanan/Coding/glow")

stats = {"restored": 0, "skipped": 0, "errors": []}


def get_git_content(filepath: Path) -> str:
    """Get file content from git HEAD."""
    rel_path = filepath.relative_to(REPO_ROOT)
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"HEAD:{rel_path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show failed for {rel_path}: {result.stderr}")
    return result.stdout


def extract_user_departments_cte(content: str) -> str | None:
    """Extract the user_departments CTE block from content."""
    # Find the CTE definition
    match = re.search(
        r"(--[^\n]*\n\s*)?user_departments\s+AS\s*\(", content, re.IGNORECASE
    )
    if not match:
        return None

    start = match.start()

    # Find matching closing paren
    paren_pos = content.index(
        "(", match.start() + (len(match.group(1)) if match.group(1) else 0)
    )
    depth = 0
    i = paren_pos
    while i < len(content):
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        return None

    return content[start:end]


def find_insertion_point(content: str) -> int | None:
    """Find where to insert the user_departments CTE.

    It should go after user_profile CTE (if it exists) or after the first CTE.
    Since user_profile was already removed, insert after the params CTE.
    """
    # Look for the end of the params CTE (most common first CTE)
    # Pattern: params AS (\n...\n),
    match = re.search(r"params\s+AS\s*\(", content, re.IGNORECASE)
    if not match:
        return None

    # Find matching closing paren
    paren_pos = content.index("(", match.start())
    depth = 0
    i = paren_pos
    while i < len(content):
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
            if depth == 0:
                # Found end of params CTE
                end = i + 1
                # Skip the trailing comma
                rest = content[end:]
                comma_match = re.match(r"\s*,", rest)
                if comma_match:
                    end += comma_match.end()
                return end
        i += 1

    return None


def process_file(filepath: Path) -> bool:
    """Restore user_departments CTE in a single file."""
    current = filepath.read_text()

    # Check if CTE already exists
    if re.search(r"user_departments\s+AS\s*\(", current, re.IGNORECASE):
        return False

    # Check if file references user_departments
    if "user_departments" not in current:
        return False

    # Get original from git
    try:
        original = get_git_content(filepath)
    except RuntimeError as e:
        stats["errors"].append((filepath.relative_to(BASE), str(e)))
        return False

    # Extract the CTE from original
    cte_block = extract_user_departments_cte(original)
    if not cte_block:
        stats["errors"].append(
            (filepath.relative_to(BASE), "No user_departments CTE found in git HEAD")
        )
        return False

    # Find insertion point in current file
    insert_pos = find_insertion_point(current)
    if insert_pos is None:
        stats["errors"].append(
            (filepath.relative_to(BASE), "Could not find insertion point (params CTE)")
        )
        return False

    # Insert the CTE
    new_content = current[:insert_pos] + "\n" + cte_block + "," + current[insert_pos:]

    filepath.write_text(new_content)
    return True


def main():
    # Find all broken files
    broken_files = []
    for sql_file in sorted(BASE.rglob("*.sql")):
        content = sql_file.read_text()
        has_cte = bool(re.search(r"user_departments\s+AS\s*\(", content, re.IGNORECASE))
        has_ref = "user_departments" in content
        if has_ref and not has_cte:
            broken_files.append(sql_file)

    print(f"Found {len(broken_files)} broken files to restore\n")

    for filepath in broken_files:
        rel_path = filepath.relative_to(BASE)
        try:
            restored = process_file(filepath)
            if restored:
                stats["restored"] += 1
                print(f"  RESTORED: {rel_path}")
            else:
                stats["skipped"] += 1
                print(f"  SKIPPED:  {rel_path}")
        except Exception as e:
            stats["errors"].append((rel_path, str(e)))
            print(f"  ERROR:    {rel_path}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Restored: {stats['restored']}")
    print(f"Skipped:  {stats['skipped']}")
    print(f"Errors:   {len(stats['errors'])}")

    if stats["errors"]:
        print("\nErrors:")
        for path, err in stats["errors"]:
            print(f"  {path}: {err}")

    # Verify
    remaining = []
    for sql_file in sorted(BASE.rglob("*.sql")):
        content = sql_file.read_text()
        has_cte = bool(re.search(r"user_departments\s+AS\s*\(", content, re.IGNORECASE))
        has_ref = "user_departments" in content
        if has_ref and not has_cte:
            remaining.append(sql_file.relative_to(BASE))

    if remaining:
        print(f"\n⚠️  {len(remaining)} files still broken:")
        for p in remaining:
            print(f"  {p}")
    else:
        print("\n✅ All user_departments CTEs restored!")


if __name__ == "__main__":
    main()
