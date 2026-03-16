#!/usr/bin/env python3
"""
Migration script: Remove view_user_profile_context from all SQL files.

Handles these patterns:
A) CTE-based: user_profile AS (SELECT ... FROM view_user_profile_context ...)
B) CTE-based: user_departments AS (SELECT ... FROM profile_departments_junction ...)
C) PL/pgSQL: SELECT ... INTO v_actor_name FROM view_user_profile_context ...
D) RETURNS TABLE fields: actor_name text, user_role text, user_department_ids uuid[]
E) SELECT fields: up.actor_name, up.role, ud.department_ids
F) CROSS JOIN user_profile up, CROSS JOIN user_departments ud
G) FROM user_profile up (final select)
"""

import re
import sys
from pathlib import Path

BASE = (
    Path(__file__).resolve().parent.parent / "server" / "app" / "sql" / "v4" / "queries"
)

# Stats
stats = {"modified": 0, "skipped": 0, "errors": []}


def remove_cte_block(content: str, cte_name: str) -> str:
    """Remove a CTE block like 'cte_name AS (...),'.

    Handles nested parentheses. Removes trailing comma and leading comma.
    """
    # Find the CTE definition
    # Pattern: cte_name AS (\n...\n),
    # We need to handle nested parens

    # Try to find the CTE with possible comment line before it
    patterns = [
        # With comment line before
        rf"(?:--[^\n]*\n)?{cte_name}\s+AS\s*\(",
        # Without comment
        rf"{cte_name}\s+AS\s*\(",
    ]

    for pat in patterns:
        match = re.search(pat, content)
        if match:
            start = match.start()
            # Check if there's a comment line right before
            # Look backwards from start for a comment on the previous line
            before = content[:start]
            lines_before = before.rstrip().rsplit("\n", 1)
            if len(lines_before) > 1 and lines_before[-1].strip().startswith("--"):
                # Include the comment line
                start = (
                    before.rstrip().rfind(
                        "\n", 0, len(before.rstrip()) - len(lines_before[-1])
                    )
                    + 1
                )
                if start < 0:
                    start = 0

            # Find matching closing paren
            paren_start = content.index("(", match.start())
            depth = 0
            i = paren_start
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
                continue

            # Check for trailing comma
            rest = content[end:]
            if rest.lstrip().startswith(","):
                end = end + rest.index(",") + 1

            # Also remove any trailing blank line
            rest_after = content[end:]
            if rest_after.startswith("\n"):
                end += 1

            # Check for leading comma before the CTE (if it's not the first CTE)
            before_cte = content[:start]
            stripped_before = before_cte.rstrip()
            if stripped_before.endswith(","):
                start = len(stripped_before) - 1
                # Also eat the newline after the comma
                if start < len(content) and content[start] == ",":
                    start = start  # keep as is, we'll reconstruct

            content = content[:start] + content[end:]
            break

    return content


def process_sql_file(filepath: Path) -> bool:
    """Process a single SQL file to remove view_user_profile_context usage.

    Returns True if file was modified.
    """
    original = filepath.read_text()
    content = original

    if "view_user_profile_context" not in content:
        return False

    # ============================================================
    # PATTERN C: PL/pgSQL SELECT ... INTO v_actor_name (save files)
    # ============================================================
    # Pattern: SELECT up.actor_name INTO v_actor_name\n    FROM view_user_profile_context up\n    WHERE up.profile_id = ...;
    plpgsql_select_pattern = re.compile(
        r"\n\s*SELECT\s+(?:up\.)?actor_name\s+INTO\s+v_actor_name\s*\n"
        r"\s*FROM\s+view_user_profile_context\s+(?:up\s+)?"
        r"(?:WHERE\s+(?:up\.)?profile_id\s*=\s*[^;]+)?;",
        re.IGNORECASE,
    )
    content = plpgsql_select_pattern.sub("", content)

    # Also handle the simpler form: FROM view_user_profile_context up WHERE up.profile_id = api_save_*_v4.profile_id;
    plpgsql_select_pattern2 = re.compile(
        r"\n\s*SELECT\s+up\.actor_name\s+INTO\s+v_actor_name\s*\n"
        r"\s*FROM\s+view_user_profile_context\s+up\s*\n"
        r"\s*WHERE\s+up\.profile_id\s*=\s*[^;]+;",
        re.IGNORECASE,
    )
    content = plpgsql_select_pattern2.sub("", content)

    # Remove v_actor_name from DECLARE
    content = re.sub(r"\n\s*v_actor_name\s+text;\s*", "\n", content)

    # Remove actor_name from RETURNS TABLE for plpgsql functions
    # This handles: actor_name text, or actor_name text\n)
    content = re.sub(r",\s*\n\s*actor_name\s+text(?=\s*\n\s*\))", "", content)
    content = re.sub(r"actor_name\s+text\s*,\s*\n", "", content)

    # Replace v_actor_name references in SELECT within RETURN QUERY
    # Pattern: v_actor_name as actor_name or v_actor_name::text as actor_name
    content = re.sub(
        r",?\s*\n?\s*v_actor_name(?:::text)?\s+(?:as|AS)\s+actor_name\s*,?", "", content
    )
    # If it was the only/last field before FROM, clean up
    content = re.sub(r",\s*\n(\s*FROM\b)", r"\n\1", content)

    # ============================================================
    # PATTERN A: CTE user_profile AS (SELECT ... FROM view_user_profile_context ...)
    # ============================================================
    # Remove the user_profile CTE block
    # Pattern matches various forms:
    # user_profile AS (\n    SELECT role\n    FROM view_user_profile_context\n    WHERE ...\n),
    # user_profile AS (\n    SELECT role, actor_name\n    FROM view_user_profile_context\n    WHERE ...\n),
    # user_profile AS (\n    SELECT vupc.actor_name, vupc.role\n    FROM view_user_profile_context vupc\n    JOIN params p ON ...\n    LIMIT 1\n),

    # Generic approach: find and remove the entire CTE block
    user_profile_cte = re.compile(
        r"(?:--[^\n]*\n)?"  # optional comment line
        r"user_profile\s+AS\s*\("
        r"[^)]*?"  # CTE body (non-greedy, no nested parens expected)
        r"\)",
        re.DOTALL | re.IGNORECASE,
    )

    # Use a more robust approach: find user_profile CTE and remove it with its comma
    def remove_user_profile_cte(text):
        # Find the CTE
        match = re.search(
            r"(--[^\n]*\n\s*)?user_profile\s+AS\s*\(", text, re.IGNORECASE
        )
        if not match:
            return text

        # Get the start (including comment if present)
        start = match.start()

        # Find matching closing paren
        paren_pos = text.index(
            "(", match.start() + (len(match.group(1)) if match.group(1) else 0)
        )
        depth = 0
        i = paren_pos
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        else:
            return text

        # Check for trailing comma + whitespace
        rest = text[end:]
        comma_match = re.match(r"\s*,", rest)
        if comma_match:
            end += comma_match.end()

        # Check for trailing newline
        if end < len(text) and text[end] == "\n":
            end += 1

        # Check if we need to remove a leading comma instead
        before = text[:start].rstrip()
        if before.endswith(","):
            # Remove trailing comma from previous CTE
            start = len(before) - 1
            # Also eat whitespace/newline between comma and CTE comment/name
            while start > 0 and text[start - 1] in " \t":
                start -= 1

        return text[:start] + text[end:]

    content = remove_user_profile_cte(content)

    # ============================================================
    # PATTERN B: CTE user_departments AS (...)
    # ============================================================
    def remove_user_departments_cte(text):
        match = re.search(
            r"(--[^\n]*\n\s*)?user_departments\s+AS\s*\(", text, re.IGNORECASE
        )
        if not match:
            return text

        start = match.start()

        paren_pos = text.index(
            "(", match.start() + (len(match.group(1)) if match.group(1) else 0)
        )
        depth = 0
        i = paren_pos
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        else:
            return text

        rest = text[end:]
        comma_match = re.match(r"\s*,", rest)
        if comma_match:
            end += comma_match.end()

        if end < len(text) and text[end] == "\n":
            end += 1

        before = text[:start].rstrip()
        if before.endswith(","):
            start = len(before) - 1
            while start > 0 and text[start - 1] in " \t":
                start -= 1

        return text[:start] + text[end:]

    content = remove_user_departments_cte(content)

    # Also remove actor_profile CTE if present
    def remove_actor_profile_cte(text):
        match = re.search(
            r"(--[^\n]*\n\s*)?actor_profile\s+AS\s*\(", text, re.IGNORECASE
        )
        if not match:
            return text

        start = match.start()
        paren_pos = text.index(
            "(", match.start() + (len(match.group(1)) if match.group(1) else 0)
        )
        depth = 0
        i = paren_pos
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        else:
            return text

        rest = text[end:]
        comma_match = re.match(r"\s*,", rest)
        if comma_match:
            end += comma_match.end()
        if end < len(text) and text[end] == "\n":
            end += 1

        before = text[:start].rstrip()
        if before.endswith(","):
            start = len(before) - 1
            while start > 0 and text[start - 1] in " \t":
                start -= 1

        return text[:start] + text[end:]

    content = remove_actor_profile_cte(content)

    # ============================================================
    # PATTERN D: RETURNS TABLE fields
    # ============================================================
    # Remove actor_name text, user_role text, user_department_ids uuid[] from RETURNS TABLE
    # Handle various orderings - field could be first, middle, or last

    # Remove 'actor_name text,' (field with trailing comma)
    content = re.sub(r"\s*actor_name\s+text\s*,\s*\n", "\n", content)
    # Remove ',\n    actor_name text' (field with leading comma, before closing paren)
    content = re.sub(r",\s*\n(\s*)actor_name\s+text(?=\s*\n\s*\))", r"\n", content)

    # Remove 'user_role text,'
    content = re.sub(r"\s*user_role\s+text\s*,\s*\n", "\n", content)
    content = re.sub(r",\s*\n(\s*)user_role\s+text(?=\s*\n\s*\))", r"\n", content)

    # Remove 'user_department_ids uuid[],'
    content = re.sub(r"\s*user_department_ids\s+uuid\[\]\s*,\s*\n", "\n", content)
    content = re.sub(
        r",\s*\n(\s*)user_department_ids\s+uuid\[\](?=\s*\n\s*\))", r"\n", content
    )

    # ============================================================
    # PATTERN E: SELECT fields
    # ============================================================
    # Remove up.actor_name::text as actor_name (with optional comma)
    content = re.sub(
        r",?\s*\n\s*up\.actor_name(?:::text)?\s+(?:as|AS)\s+actor_name\s*(?:,(?=\s*\n))?",
        "",
        content,
    )
    content = re.sub(
        r",?\s*\n\s*COALESCE\(up\.actor_name,\s*\'System\'\)(?:::text)?\s+(?:as|AS)\s+actor_name\s*(?:,(?=\s*\n))?",
        "",
        content,
    )

    # Remove up.role::text as user_role
    content = re.sub(
        r",?\s*\n\s*up\.role(?:::text)?\s+(?:as|AS)\s+user_role\s*(?:,(?=\s*\n))?",
        "",
        content,
    )

    # Remove ud.department_ids as user_department_ids
    content = re.sub(
        r",?\s*\n\s*ud\.department_ids\s+(?:as|AS)\s+user_department_ids\s*(?:,(?=\s*\n))?",
        "",
        content,
    )

    # Remove ap.actor_name AS actor_name
    content = re.sub(
        r",?\s*\n\s*ap\.actor_name(?:::text)?\s+(?:as|AS)\s+actor_name\s*(?:,(?=\s*\n))?",
        "",
        content,
    )

    # Handle "up.actor_name," on its own line (not as last field)
    content = re.sub(r"\s*up\.actor_name\s*,\s*\n", "\n", content)

    # ============================================================
    # PATTERN F: CROSS JOIN removal
    # ============================================================
    content = re.sub(
        r"\s*CROSS\s+JOIN\s+user_profile\s+up\s*\n", "\n", content, flags=re.IGNORECASE
    )
    content = re.sub(
        r"\s*CROSS\s+JOIN\s+user_departments\s+ud\s*\n",
        "\n",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"\s*CROSS\s+JOIN\s+actor_profile\s+ap\s*\n", "\n", content, flags=re.IGNORECASE
    )

    # Also handle CROSS JOIN at end of query (before semicolon)
    content = re.sub(
        r"\s*CROSS\s+JOIN\s+user_profile\s+up\s*(?=;|\$)",
        "\n",
        content,
        flags=re.IGNORECASE,
    )

    # ============================================================
    # PATTERN G: FROM user_profile up (final select without CROSS JOIN)
    # ============================================================
    # Pattern: FROM user_profile up (standalone, for final select that only reads from user_profile)
    # Be careful not to remove legitimate FROM clauses
    # This typically appears as the only FROM in a final SELECT
    content = re.sub(r"\nFROM\s+user_profile\s+up\s*\n", "\n", content)

    # ============================================================
    # Clean up any remaining artifacts
    # ============================================================
    # Fix double commas that might result from removing middle fields
    content = re.sub(r",\s*,", ",", content)

    # Fix trailing comma before FROM
    content = re.sub(r",\s*\n(\s*FROM\b)", r"\n\1", content)

    # Fix empty SELECT (shouldn't happen but just in case)
    # Fix lines with only whitespace
    content = re.sub(r"\n\n\n+", "\n\n", content)

    # Fix trailing comma before closing paren in RETURNS TABLE
    content = re.sub(r",\s*\n(\s*\)\s*\n)", r"\n\1", content)

    # ============================================================
    # Add comment about user context coming from Python
    # ============================================================
    if "User context" not in content and "user context" not in content:
        # Add comment after the function signature (after AS $$ or AS $$\n)
        # Try to add after the first comment block or function definition
        if "-- User context" not in content:
            # Add a comment near the top of the function body
            comment = "-- User context (role, actor_name, department_ids) comes from get_profile_context_internal()\n"
            # Insert after CREATE OR REPLACE FUNCTION ... AS $$ line
            as_match = re.search(r"AS\s+\$\$\s*\n", content)
            if as_match:
                insert_pos = as_match.end()
                content = content[:insert_pos] + comment + content[insert_pos:]

    if content != original:
        filepath.write_text(content)
        return True
    return False


def main():
    """Process all SQL files that use view_user_profile_context."""
    if not BASE.exists():
        print(f"Error: {BASE} not found")
        sys.exit(1)

    # Find all SQL files with view_user_profile_context
    sql_files = []
    for sql_file in sorted(BASE.rglob("*.sql")):
        text = sql_file.read_text()
        if "view_user_profile_context" in text:
            sql_files.append(sql_file)

    print(f"Found {len(sql_files)} SQL files to process\n")

    for filepath in sql_files:
        rel_path = filepath.relative_to(BASE)
        try:
            modified = process_sql_file(filepath)
            if modified:
                stats["modified"] += 1
                print(f"  MODIFIED: {rel_path}")
            else:
                stats["skipped"] += 1
                print(f"  SKIPPED:  {rel_path}")
        except Exception as e:
            stats["errors"].append((rel_path, str(e)))
            print(f"  ERROR:    {rel_path}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Modified: {stats['modified']}")
    print(f"Skipped:  {stats['skipped']}")
    print(f"Errors:   {len(stats['errors'])}")

    if stats["errors"]:
        print("\nErrors:")
        for path, err in stats["errors"]:
            print(f"  {path}: {err}")

    # Verify: check if any files still reference the view
    remaining = []
    for sql_file in sorted(BASE.rglob("*.sql")):
        text = sql_file.read_text()
        if "view_user_profile_context" in text:
            remaining.append(sql_file.relative_to(BASE))

    if remaining:
        print(f"\n⚠️  {len(remaining)} files still reference view_user_profile_context:")
        for p in remaining:
            print(f"  {p}")
    else:
        print("\n✅ No files reference view_user_profile_context anymore!")


if __name__ == "__main__":
    main()
