#!/usr/bin/env python3
"""
Migrate SQL files to remove view_user_profile_context dependency.

Strategy for user_profile CTE:
- "Simple" files (no up.role/up.actor_name in logic): remove CTE entirely
- "Complex" files (up.role used in WHERE/CASE): replace CTE with junction table query

Also handles:
- RETURNS TABLE field removal (actor_name, user_role, user_department_ids)
- SELECT output field removal
- CROSS JOIN removal
- user_departments CTE removal (when output-only)
- PL/pgSQL SELECT INTO patterns
- Duplicate check file rewrites
- GROUP BY cleanup
"""

import re
from pathlib import Path

BASE = Path("/Users/ashoksaravanan/Coding/glow/server/app/sql/v4/queries")

stats = {"modified": 0, "skipped": 0, "errors": [], "complex": [], "simple": []}


# ── CTE Removal ──────────────────────────────────────────────────────────


def find_cte_range(lines: list[str], cte_name: str) -> tuple[int, int] | None:
    """Find the line range [start, end] of a named CTE (inclusive).

    Returns (start_line, end_line) or None if not found.
    start_line includes any comment line directly above the CTE.
    end_line is the line containing the matching close paren.
    """
    cte_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match CTE definition: `cte_name AS (` or `WITH cte_name AS (` possibly with leading whitespace
        if re.match(rf"(?:WITH\s+)?{cte_name}\s+AS\s*\(", stripped, re.IGNORECASE):
            cte_start = i
            # Include comment line above if it exists and describes this CTE
            if i > 0 and lines[i - 1].strip().startswith("--"):
                cte_start = i - 1
            break

    if cte_start is None:
        return None

    # Find the matching close paren by tracking depth
    depth = 0
    started = False
    for i in range(cte_start, len(lines)):
        for ch in lines[i]:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                depth -= 1
                if started and depth == 0:
                    return (cte_start, i)

    return None


def remove_cte(lines: list[str], cte_name: str) -> tuple[list[str], bool]:
    """Remove a named CTE from content lines, handling commas properly.

    Returns (new_lines, was_removed).
    """
    rng = find_cte_range(lines, cte_name)
    if rng is None:
        return lines, False

    start, end = rng
    end_line = lines[end]
    has_trailing_comma = end_line.rstrip().endswith("),")

    new_lines = list(lines)  # copy

    # Check if this is the first CTE (starts with WITH)
    cte_def_line = lines[start]
    for li in range(start, end + 1):
        if re.match(
            r"\s*(?:WITH\s+)?" + cte_name + r"\s+AS\s*\(", lines[li], re.IGNORECASE
        ):
            cte_def_line = lines[li]
            break
    is_first_cte = bool(re.match(r"\s*WITH\s+", cte_def_line, re.IGNORECASE))

    if has_trailing_comma:
        # Middle or first CTE: remove lines [start..end] inclusive
        del new_lines[start : end + 1]
        # If this was the first CTE (WITH keyword), prepend WITH to next CTE
        if is_first_cte and start < len(new_lines):
            next_line = new_lines[start]
            # The next line should be the next CTE name
            next_stripped = next_line.lstrip()
            if next_stripped and not next_stripped.startswith("WITH"):
                indent = re.match(r"^(\s*)", next_line).group(1)
                new_lines[start] = indent + "WITH " + next_stripped
    else:
        # Last CTE: remove lines [start..end] and fix comma on previous CTE
        del new_lines[start : end + 1]
        # Remove trailing comma from the line above
        if start > 0 and start - 1 < len(new_lines):
            prev = new_lines[start - 1]
            if prev.rstrip().endswith(","):
                new_lines[start - 1] = prev.rstrip()[:-1] + "\n"

    # Clean up any resulting double blank lines
    cleaned = []
    prev_blank = False
    for line in new_lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    return cleaned, True


def replace_cte_with_junction(
    lines: list[str], cte_name: str, profile_id_expr: str
) -> tuple[list[str], bool]:
    """Replace a user_profile CTE (that queries the view) with a junction-table-based version.

    Keeps role and actor_name fields so all existing references still work.
    actor_name becomes '' (Python will provide the real value).
    """
    rng = find_cte_range(lines, cte_name)
    if rng is None:
        return lines, False

    start, end = rng
    end_line = lines[end]
    has_trailing_comma = end_line.rstrip().endswith("),")

    # Detect indentation and WITH prefix from the original CTE name line
    # Find the actual CTE definition line (not the comment)
    cte_def_line = start
    has_with_prefix = False
    for i in range(start, end + 1):
        if re.match(
            r"\s*(?:WITH\s+)?" + cte_name + r"\s+AS\s*\(", lines[i], re.IGNORECASE
        ):
            cte_def_line = i
            has_with_prefix = bool(re.match(r"\s*WITH\s+", lines[i], re.IGNORECASE))
            break
    indent = re.match(r"^(\s*)", lines[cte_def_line]).group(1)
    with_prefix = "WITH " if has_with_prefix else ""

    # Build replacement CTE
    comma = "," if has_trailing_comma else ""
    replacement = [
        f"{indent}-- User context: actor_name comes from get_profile_context_internal() in Python\n",
        f"{indent}{with_prefix}{cte_name} AS (\n",
        f"{indent}    SELECT COALESCE(r.role, 'member'::profile_type) as role,\n",
        f"{indent}           ''::text as actor_name\n",
        f"{indent}    FROM profile_roles_junction prj\n",
        f"{indent}    JOIN roles_resource r ON prj.role_id = r.id\n",
        f"{indent}    WHERE prj.profile_id = {profile_id_expr}\n",
        f"{indent}    LIMIT 1\n",
        f"{indent}){comma}\n",
    ]

    new_lines = list(lines)
    new_lines[start : end + 1] = replacement
    return new_lines, True


# ── Helpers ──────────────────────────────────────────────────────────────


def has_up_role_in_logic(content: str) -> bool:
    """Check if up.role is used in WHERE/CASE/HAVING/GROUP BY (not just output)."""
    # Remove comments
    no_comments = re.sub(r"--[^\n]*", "", content)
    # Check for up.role in non-output contexts
    # Output patterns: `up.role::text as user_role` or `up.role AS user_role`
    output_pattern = re.compile(
        r"up\.role\s*(?:::text\s+)?(?:AS\s+)?user_role", re.IGNORECASE
    )
    # All up.role references
    all_refs = list(re.finditer(r"up\.role", no_comments))
    # Non-output references
    for ref in all_refs:
        # Check context around this reference
        before = no_comments[max(0, ref.start() - 100) : ref.start()]
        after = no_comments[ref.end() : ref.end() + 100]
        # If it's an output reference, skip
        if output_pattern.match(no_comments[ref.start() : ref.end() + 50]):
            continue
        # If it's in GROUP BY, skip (we'll handle that)
        if "GROUP BY" in before[-30:]:
            continue
        # Otherwise it's logic usage
        return True
    return False


def has_up_actor_name_in_logic(content: str) -> bool:
    """Check if up.actor_name is used outside of simple output (in composite tuples, GROUP BY, etc.)."""
    no_comments = re.sub(r"--[^\n]*", "", content)
    # Simple output patterns
    output_pattern = re.compile(
        r"up\.actor_name\s*(?:::text\s+)?(?:as\s+)?actor_name\s*[,\n]", re.IGNORECASE
    )
    all_refs = list(re.finditer(r"up\.actor_name", no_comments))
    for ref in all_refs:
        ctx = no_comments[ref.start() : ref.end() + 60]
        if output_pattern.match(ctx):
            continue
        # It's used in a non-simple-output context (composite tuple, GROUP BY, etc.)
        return True
    return False


def get_profile_id_expr(content: str) -> str:
    """Extract the profile_id expression used in the user_profile CTE."""
    # Most common: (SELECT profile_id FROM params)
    m = re.search(
        r"user_profile\s+AS\s*\([^)]*WHERE\s+(?:view_user_profile_context\.)?profile_id\s*=\s*([^\n;]+)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        expr = m.group(1).strip()
        # Clean up trailing parts
        expr = re.sub(r"\s*LIMIT\s+\d+\s*$", "", expr, flags=re.IGNORECASE)
        return expr
    # Fallback
    return "(SELECT profile_id FROM params)"


def is_plpgsql(content: str) -> bool:
    """Check if the SQL file uses PL/pgSQL (LANGUAGE plpgsql)."""
    return bool(re.search(r"LANGUAGE\s+plpgsql", content, re.IGNORECASE))


def is_duplicate_check(filepath: Path) -> bool:
    """Check if this is a duplicate access check file."""
    return "check_" in filepath.name and "_duplicate_" in filepath.name


# ── Line-level transforms ───────────────────────────────────────────────


def remove_returns_table_fields(lines: list[str]) -> list[str]:
    """Remove actor_name, user_role, user_department_ids from RETURNS TABLE."""
    result = []
    in_returns = False
    paren_depth = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track RETURNS TABLE block
        if re.match(r"RETURNS\s+TABLE\s*\(", stripped, re.IGNORECASE):
            in_returns = True
            paren_depth = 0
            for ch in stripped:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
            result.append(line)
            continue

        if in_returns:
            for ch in stripped:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1

            if paren_depth <= 0:
                in_returns = False
                result.append(line)
                continue

            # Check if this line should be removed
            if re.match(r"(?:--\s*)?actor_name\s+text", stripped, re.IGNORECASE):
                continue
            if re.match(r"(?:--\s*)?user_role\s+text", stripped, re.IGNORECASE):
                continue
            if re.match(
                r"(?:--\s*)?user_department_ids\s+(?:uuid|text)\[\]",
                stripped,
                re.IGNORECASE,
            ):
                continue
            # Also remove comment lines about user context
            if stripped.startswith("-- User context") or stripped.startswith(
                "-- Basic metadata"
            ):
                continue

            result.append(line)
            continue

        result.append(line)

    # Fix trailing commas in RETURNS TABLE
    result = fix_trailing_commas_in_returns(result)
    return result


def fix_trailing_commas_in_returns(lines: list[str]) -> list[str]:
    """Fix trailing comma issues in RETURNS TABLE after field removal."""
    result = list(lines)
    in_returns = False
    paren_depth = 0
    returns_start = None
    returns_end = None

    for i, line in enumerate(result):
        stripped = line.strip()
        if re.match(r"RETURNS\s+TABLE\s*\(", stripped, re.IGNORECASE):
            in_returns = True
            returns_start = i
            paren_depth = 0
            for ch in stripped:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
            continue
        if in_returns:
            for ch in stripped:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
            if paren_depth <= 0:
                returns_end = i
                in_returns = False
                break

    if returns_start is None or returns_end is None:
        return result

    # Find the last field line before the closing paren
    for i in range(returns_end - 1, returns_start, -1):
        stripped = result[i].strip()
        if stripped and not stripped.startswith("--"):
            # This is the last field - ensure no trailing comma
            if stripped.endswith(","):
                result[i] = result[i].rstrip()
                if result[i].endswith(","):
                    result[i] = result[i][:-1]
                result[i] += "\n"
            break

    return result


def remove_select_output_fields(lines: list[str], is_complex: bool) -> list[str]:
    """Remove actor_name, user_role, user_department_ids from top-level SELECT output."""
    result = []
    for line in lines:
        stripped = line.strip()

        # Remove top-level actor_name output
        if re.match(
            r"up\.actor_name\s*(?:::text\s+)?(?:as\s+)?actor_name\s*[,]?\s*$",
            stripped,
            re.IGNORECASE,
        ):
            continue
        if re.match(
            r"\(SELECT\s+actor_name\s+FROM\s+user_profile(?:\s+LIMIT\s+1)?\)\s*(?:::text\s+)?(?:as\s+)?actor_name\s*[,]?\s*$",
            stripped,
            re.IGNORECASE,
        ):
            continue
        if re.match(
            r"COALESCE\s*\(\s*up\.actor_name\s*,\s*'System'\s*\)\s*(?:::text\s+)?(?:as\s+)?actor_name\s*[,]?\s*$",
            stripped,
            re.IGNORECASE,
        ):
            continue

        # Remove user_role output
        if re.match(
            r"up\.role\s*(?:::text\s+)?(?:as\s+)?user_role\s*[,]?\s*$",
            stripped,
            re.IGNORECASE,
        ):
            continue
        if re.match(r"up\.role\s+AS\s+user_role\s*[,]?\s*$", stripped, re.IGNORECASE):
            continue

        # Remove user_department_ids output
        if re.match(
            r"ud\.department_ids\s+(?:as\s+)?user_department_ids\s*[,]?\s*$",
            stripped,
            re.IGNORECASE,
        ):
            continue
        if re.match(
            r"\(SELECT\s+department_ids\s+FROM\s+user_departments\)\s*(?:as\s+)?user_department_ids\s*[,]?\s*$",
            stripped,
            re.IGNORECASE,
        ):
            continue

        result.append(line)

    return result


def remove_cross_joins(lines: list[str], is_complex: bool) -> list[str]:
    """Remove CROSS JOIN to user_profile and user_departments."""
    result = []
    for line in lines:
        stripped = line.strip()

        # Remove CROSS JOIN user_profile up (only for simple files)
        if not is_complex and re.match(
            r"CROSS\s+JOIN\s+user_profile\s+up\s*[;]?\s*$", stripped, re.IGNORECASE
        ):
            continue

        # Remove CROSS JOIN user_departments ud
        if re.match(
            r"CROSS\s+JOIN\s+user_departments\s+ud\s*[;]?\s*$", stripped, re.IGNORECASE
        ):
            continue

        # Remove CROSS JOIN actor_profile ap
        if re.match(
            r"CROSS\s+JOIN\s+actor_profile\s+ap\s*[;]?\s*$", stripped, re.IGNORECASE
        ):
            continue

        result.append(line)

    return result


def remove_from_user_profile(lines: list[str]) -> list[str]:
    """Remove 'FROM user_profile up' when it's the source table (not CROSS JOIN)."""
    result = []
    for line in lines:
        stripped = line.strip()
        # Don't remove FROM user_profile if it's in a CROSS JOIN context
        if re.match(r"FROM\s+user_profile\s+up\s*[;]?\s*$", stripped, re.IGNORECASE):
            # Replace with empty - the SELECT will need adjustment
            # Actually, this case means the query is `SELECT ... FROM user_profile up`
            # We need to keep a FROM clause. Skip for now - handle manually.
            pass
        result.append(line)
    return result


def clean_group_by(lines: list[str]) -> list[str]:
    """Remove up.actor_name and up.role from GROUP BY clauses."""
    result = []
    for line in lines:
        stripped = line.strip()
        if "GROUP BY" in line.upper():
            # Remove up.actor_name and up.role from GROUP BY
            new_line = re.sub(
                r",?\s*up\.actor_name\s*,?",
                lambda m: (
                    "," if m.group().startswith(",") and m.group().endswith(",") else ""
                ),
                line,
            )
            new_line = re.sub(
                r",?\s*up\.role\s*,?",
                lambda m: (
                    "," if m.group().startswith(",") and m.group().endswith(",") else ""
                ),
                new_line,
            )
            # Clean up double commas and leading/trailing commas
            new_line = re.sub(r",\s*,", ",", new_line)
            new_line = re.sub(
                r"GROUP\s+BY\s*,", "GROUP BY ", new_line, flags=re.IGNORECASE
            )
            new_line = re.sub(r",\s*$", "", new_line.rstrip()) + "\n"
            # If GROUP BY is now empty, remove the line
            if re.match(r"\s*GROUP\s+BY\s*$", new_line.strip(), re.IGNORECASE):
                continue
            result.append(new_line)
        else:
            result.append(line)
    return result


def fix_select_commas(lines: list[str]) -> list[str]:
    """Fix comma issues in SELECT after removing fields.

    Handles cases where removing a field leaves a dangling comma.
    """
    result = list(lines)

    # Find SELECT blocks and fix commas
    i = 0
    while i < len(result):
        stripped = result[i].strip().upper()
        if stripped.startswith("SELECT") or stripped.startswith("RETURN QUERY SELECT"):
            # Found a SELECT, scan forward to find the FROM/end
            select_start = i
            # Find the extent of the SELECT clause
            j = i + 1
            while j < len(result):
                s = result[j].strip().upper()
                if (
                    s.startswith("FROM")
                    or s.startswith("WHERE")
                    or s.startswith("$$")
                    or s.startswith("END")
                ):
                    break
                j += 1

            # Now check for trailing comma on the line before FROM
            if j > select_start + 1:
                prev = j - 1
                while prev > select_start and result[prev].strip() == "":
                    prev -= 1
                if prev > select_start:
                    line = result[prev].rstrip()
                    if line.endswith(","):
                        result[prev] = line[:-1] + "\n"
        i += 1

    return result


# ── PL/pgSQL handlers ───────────────────────────────────────────────────


def remove_plpgsql_select_into(lines: list[str]) -> list[str]:
    """Remove SELECT ... INTO v_actor_name FROM view_user_profile_context blocks."""
    result = []
    skip_until_semicolon = False

    for line in lines:
        if skip_until_semicolon:
            if ";" in line:
                skip_until_semicolon = False
            continue

        # Detect SELECT INTO from the view
        if "view_user_profile_context" in line and (
            "INTO" in line.upper() or "SELECT" in line.upper()
        ):
            # This is part of a SELECT INTO block
            if ";" in line:
                # Single-line statement, skip it
                continue
            else:
                # Multi-line, skip until semicolon
                skip_until_semicolon = True
                continue

        # Also handle multi-line SELECT INTO that starts on previous line
        # Pattern: "SELECT actor_name\n    INTO v_actor_name\n    FROM view_user_profile_context"
        # This is trickier - look for the view reference

        result.append(line)

    return result


def remove_plpgsql_view_block(lines: list[str]) -> list[str]:
    """Remove entire SELECT...INTO...FROM view_user_profile_context blocks in PL/pgSQL."""
    result = []
    i = 0
    while i < len(lines):
        # Look ahead for view reference in a multi-line SELECT INTO block
        # The block might be:
        #   SELECT actor_name
        #   INTO v_actor_name
        #   FROM view_user_profile_context
        #   WHERE ...;
        # Or:
        #   SELECT COALESCE(NULLIF(actor_name, ''), 'System')
        #   INTO v_actor_name
        #   FROM view_user_profile_context
        #   WHERE ... LIMIT 1;

        # Check if any line in a 6-line window contains view_user_profile_context
        window = "".join(lines[i : min(i + 8, len(lines))])
        if "view_user_profile_context" in window:
            # Find the start of this block (SELECT keyword)
            block_start = i
            for j in range(max(0, i - 3), i + 1):
                if re.match(r"\s*SELECT\s", lines[j], re.IGNORECASE):
                    block_start = j
                    break

            # Find the end (semicolon)
            block_end = i
            for j in range(i, min(i + 8, len(lines))):
                if ";" in lines[j]:
                    block_end = j
                    break

            # Skip this block
            # Also skip any blank line after
            i = block_end + 1
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            continue

        result.append(lines[i])
        i += 1

    return result


def fix_return_query(lines: list[str]) -> list[str]:
    """Fix RETURN QUERY SELECT to remove v_actor_name."""
    result = []
    for line in lines:
        if "RETURN QUERY SELECT" in line.upper():
            # Remove v_actor_name from the return
            new_line = re.sub(r",\s*v_actor_name", "", line)
            new_line = re.sub(r"v_actor_name\s*,\s*", "", new_line)
            new_line = re.sub(
                r",\s*COALESCE\s*\(\s*v_actor_name\s*,\s*\'[^\']*\'\s*\)", "", new_line
            )
            result.append(new_line)
        else:
            result.append(line)
    return result


def remove_declare_actor_name(lines: list[str]) -> list[str]:
    """Remove v_actor_name and v_user_role declarations from DECLARE block."""
    result = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"v_actor_name\s+text\s*;", stripped, re.IGNORECASE):
            continue
        if re.match(r"v_user_role\s+text\s*;", stripped, re.IGNORECASE):
            continue
        result.append(line)
    return result


# ── Duplicate check handler ─────────────────────────────────────────────


def rewrite_duplicate_check(content: str) -> str:
    """Rewrite a check_*_duplicate_access file to remove view dependency."""
    # Replace RETURNS TABLE
    content = re.sub(
        r"RETURNS\s+TABLE\s*\(\s*\n?\s*user_role\s+text\s*\n?\s*\)",
        "RETURNS TABLE (\n    -- User context (role, actor_name, department_ids) comes from get_profile_context_internal()\n    access_check boolean\n)",
        content,
        flags=re.IGNORECASE,
    )

    # Replace function body
    content = re.sub(
        r"SELECT\s+role\s*::text\s+as\s+user_role\s*\n\s*FROM\s+view_user_profile_context\s*\n\s*WHERE\s+profile_id\s*=\s*[^;]+;",
        "-- User context (role, actor_name, department_ids) comes from get_profile_context_internal()\nSELECT true::boolean as access_check;",
        content,
        flags=re.IGNORECASE,
    )

    return content


# ── Special file handlers ───────────────────────────────────────────────


def handle_from_user_profile_select(lines: list[str]) -> list[str]:
    """Handle queries that do SELECT ... FROM user_profile up (not CROSS JOIN).

    These are typically simple queries like:
    SELECT up.actor_name::text as actor_name, ... FROM user_profile up;

    After removing user_profile CTE, change FROM to use params or a literal.
    """
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # If the SELECT...FROM pattern is just FROM user_profile up with no other tables
        if re.match(r"FROM\s+user_profile\s+up\s*;?\s*$", stripped, re.IGNORECASE):
            # Check if there's a params CTE
            full_content = "\n".join(lines)
            if "params AS" in full_content:
                result.append(line.replace("user_profile up", "params"))
            else:
                # Replace with a dummy FROM
                result.append(
                    re.sub(
                        r"FROM\s+user_profile\s+up",
                        "FROM (SELECT 1) AS _dummy",
                        line,
                        flags=re.IGNORECASE,
                    )
                )
        else:
            result.append(line)
    return result


# ── Main processing ─────────────────────────────────────────────────────


def add_migration_comment(content: str) -> str:
    """Add a comment about get_profile_context_internal() if not already present."""
    if "get_profile_context_internal()" in content:
        return content

    # Add after the function signature (after AS $$)
    m = re.search(r"(AS\s+\$\$\s*\n)", content)
    if m:
        comment = "-- User context (actor_name, user_role, department_ids) comes from get_profile_context_internal() in Python\n"
        # Don't add if this is a PL/pgSQL function (has DECLARE/BEGIN)
        after = content[m.end() : m.end() + 100]
        if re.match(r"\s*DECLARE\b", after, re.IGNORECASE) or re.match(
            r"\s*BEGIN\b", after, re.IGNORECASE
        ):
            return content  # PL/pgSQL functions - add comment differently
        return content[: m.end()] + comment + content[m.end() :]

    return content


def process_file(filepath: Path) -> bool:
    """Process a single SQL file."""
    content = filepath.read_text()
    original = content

    # Skip if doesn't reference the view
    if "view_user_profile_context" not in content:
        return False

    # ── Handle duplicate check files specially ──
    if is_duplicate_check(filepath):
        content = rewrite_duplicate_check(content)
        if content != original:
            filepath.write_text(content)
            return True
        return False

    lines = content.split("\n")
    # Ensure all lines end with \n for consistent processing
    lines = [l + "\n" if not l.endswith("\n") else l for l in lines]
    # The last line might have an extra \n
    if lines and lines[-1] == "\n" and len(lines) > 1:
        pass  # leave as is

    # ── Determine if this is a "complex" file ──
    is_complex = has_up_role_in_logic(content) or has_up_actor_name_in_logic(content)

    # ── Handle PL/pgSQL files ──
    if is_plpgsql(content):
        lines = remove_plpgsql_view_block(lines)
        lines = remove_declare_actor_name(lines)
        lines = fix_return_query(lines)
        # Also handle CTE-based patterns in PL/pgSQL
        if "user_profile AS" in "".join(lines).lower() or "user_profile as" in "".join(
            lines
        ):
            joined = "".join(lines)
            if has_up_role_in_logic(joined):
                profile_id_expr = get_profile_id_expr(content)
                lines, _ = replace_cte_with_junction(
                    lines, "user_profile", profile_id_expr
                )
                is_complex = True
            else:
                lines, _ = remove_cte(lines, "user_profile")
    else:
        # ── Handle user_profile CTE ──
        if is_complex:
            profile_id_expr = get_profile_id_expr(content)
            lines, _ = replace_cte_with_junction(lines, "user_profile", profile_id_expr)
            stats["complex"].append(filepath.relative_to(BASE))
        else:
            lines, _ = remove_cte(lines, "user_profile")
            stats["simple"].append(filepath.relative_to(BASE))

    # ── Remove actor_profile CTE (derived from user_profile) ──
    lines, _ = remove_cte(lines, "actor_profile")

    # ── Check if user_departments is only used for output ──
    joined = "".join(lines)
    # Check if user_departments is referenced in WHERE/IN/filtering (not just CROSS JOIN and output)
    ud_refs = [m for m in re.finditer(r"user_departments", joined)]
    ud_in_cte = bool(re.search(r"user_departments\s+AS\s*\(", joined, re.IGNORECASE))
    ud_in_cross_join = bool(
        re.search(r"CROSS\s+JOIN\s+user_departments", joined, re.IGNORECASE)
    )
    ud_in_output = bool(re.search(r"ud\.department_ids", joined, re.IGNORECASE))
    ud_in_where = bool(
        re.search(
            r"(?:IN|FROM)\s*\(\s*SELECT\s+[^)]*FROM\s+user_departments",
            joined,
            re.IGNORECASE,
        )
    )

    # If user_departments is NOT used in WHERE filtering, remove it
    if ud_in_cte and not ud_in_where:
        lines, _ = remove_cte(lines, "user_departments")

    # ── Remove RETURNS TABLE fields ──
    lines = remove_returns_table_fields(lines)

    # ── Remove SELECT output fields ──
    lines = remove_select_output_fields(lines, is_complex)

    # ── Remove CROSS JOINs ──
    lines = remove_cross_joins(lines, is_complex)

    # ── Handle FROM user_profile up (not CROSS JOIN) ──
    if not is_complex:
        lines = handle_from_user_profile_select(lines)

    # ── Clean up GROUP BY ──
    if not is_complex:
        lines = clean_group_by(lines)

    # ── Fix SELECT commas ──
    lines = fix_select_commas(lines)

    # ── Reassemble and add comment ──
    content = "".join(lines)
    content = add_migration_comment(content)

    if content != original:
        filepath.write_text(content)
        return True

    return False


def main():
    # Find all SQL files referencing the view
    target_files = []
    for sql_file in sorted(BASE.rglob("*.sql")):
        content = sql_file.read_text()
        if "view_user_profile_context" in content:
            target_files.append(sql_file)

    print(f"Found {len(target_files)} files referencing view_user_profile_context\n")

    for filepath in target_files:
        rel = filepath.relative_to(BASE)
        try:
            modified = process_file(filepath)
            if modified:
                stats["modified"] += 1
                print(f"  MODIFIED: {rel}")
            else:
                stats["skipped"] += 1
                print(f"  SKIPPED:  {rel}")
        except Exception as e:
            stats["errors"].append((rel, str(e)))
            print(f"  ERROR:    {rel}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Modified: {stats['modified']}")
    print(f"Skipped:  {stats['skipped']}")
    print(f"Errors:   {len(stats['errors'])}")
    print(f"Complex:  {len(stats['complex'])} (CTE replaced with junction table)")
    print(f"Simple:   {len(stats['simple'])} (CTE removed entirely)")

    if stats["errors"]:
        print("\nErrors:")
        for path, err in stats["errors"]:
            print(f"  {path}: {err}")

    if stats["complex"]:
        print("\nComplex files (CTE replaced, up.role still used in logic):")
        for path in stats["complex"]:
            print(f"  {path}")

    # Verify
    remaining = []
    for sql_file in sorted(BASE.rglob("*.sql")):
        if "view_user_profile_context" in sql_file.read_text():
            remaining.append(sql_file.relative_to(BASE))

    if remaining:
        print(f"\n⚠  {len(remaining)} files still reference the view:")
        for p in remaining:
            print(f"  {p}")
    else:
        print("\n✅ No files reference view_user_profile_context!")


if __name__ == "__main__":
    main()
