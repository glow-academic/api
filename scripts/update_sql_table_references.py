#!/usr/bin/env python3
"""
Script to update all SQL file references from artifact/resource table names
to their new suffixed versions (_artifact and _resource).

After migrations 248 and 249:
- Artifact tables: singular names → {name}_artifact (e.g., agent → agent_artifact)
- Resource tables: plural names → {name}_resource (e.g., agents → agents_resource)
- Special artifact tables: both singular and plural → plural (e.g., chat/chats → chats)
"""

import argparse
import re
from pathlib import Path

# Special plural artifact tables (both singular and plural map to plural)
# These were renamed from {name}_artifact to plural in migration 249
SPECIAL_PLURAL_ARTIFACTS: dict[str, str] = {
    "chat": "chats",
    "chats": "chats",  # Already correct, but include for completeness
    "grade": "grades",
    "grades": "grades",
    "run": "runs",
    "runs": "runs",
    "message": "messages",
    "messages": "messages",
    "key": "keys",
    "keys": "keys",
}

# Regular artifact tables (singular → {name}_artifact)
REGULAR_ARTIFACTS = [
    "agent",
    "auth",
    "cohort",
    "department",
    "document",
    "eval",
    "field",
    "model",
    "parameter",
    "persona",
    "profile",
    "provider",
    "rubric",
    "scenario",
    "setting",
    "simulation",
    "tool",
]

# Resource tables (plural → {name}_resource)
# Get full list from database enum, but include common ones here
RESOURCES = [
    "agents",
    "analyses",
    "audios",
    "auths",
    "cohorts",
    "colors",
    "conditional_parameters",
    "conversations",
    "debug_info",
    "departments",
    "descriptions",
    "documents",
    "emails",
    "endpoints",
    "eval_rubric_grade_agents",
    "evals",
    "examples",
    "feedbacks",
    "fields",
    "flags",
    "hints",
    "html",
    "icons",
    "images",
    "improvements",
    "instructions",
    "items",
    "keys",
    "models",
    "names",
    "objectives",
    "options",
    "parameters",
    "personas",
    "points",
    "problem_statements",
    "profiles",
    "prompts",
    "protocols",
    "providers",
    "questions",
    "reasoning_levels",
    "request_limits",
    "responses",
    "rubrics",
    "scenario_positions",
    "scenario_rubric_grade_agents",
    "scenarios",
    "schema_field_items",
    "schema_fields",
    "schemas",
    "settings",
    "simulation_scenario_flags",
    "simulations",
    "slugs",
    "standard_groups",
    "strengths",
    "temperature_levels",
    "template_array_items",
    "template_values",
    "templates",
    "texts",
    "thresholds",
    "times",
    "tools",
    "videos",
    "voices",
    "content",  # Added from database enum
]

# SQL patterns to replace - order matters (more specific patterns first)
# Use word boundaries to avoid partial matches
PATTERNS = [
    # Schema-qualified names (more specific, handle first)
    (r"\bFROM\s+public\.({})\b", "FROM public.{}"),
    (r"\bJOIN\s+public\.({})\b", "JOIN public.{}"),
    (r"\bLEFT\s+JOIN\s+public\.({})\b", "LEFT JOIN public.{}"),
    (r"\bRIGHT\s+JOIN\s+public\.({})\b", "RIGHT JOIN public.{}"),
    (r"\bINNER\s+JOIN\s+public\.({})\b", "INNER JOIN public.{}"),
    (r"\bFULL\s+JOIN\s+public\.({})\b", "FULL JOIN public.{}"),
    (r"\bUPDATE\s+public\.({})\b", "UPDATE public.{}"),
    (r"\bINSERT\s+INTO\s+public\.({})\b", "INSERT INTO public.{}"),
    (r"\bDELETE\s+FROM\s+public\.({})\b", "DELETE FROM public.{}"),
    (r"\bTABLE\s+public\.({})\b", "TABLE public.{}"),
    (r"\bREFERENCES\s+public\.({})\b", "REFERENCES public.{}"),
    (r"\bINTO\s+public\.({})\b", "INTO public.{}"),
    # Regular table references (with word boundaries)
    (r"\bFROM\s+({})\b", "FROM {}"),
    (r"\bJOIN\s+({})\b", "JOIN {}"),
    (r"\bLEFT\s+JOIN\s+({})\b", "LEFT JOIN {}"),
    (r"\bRIGHT\s+JOIN\s+({})\b", "RIGHT JOIN {}"),
    (r"\bINNER\s+JOIN\s+({})\b", "INNER JOIN {}"),
    (r"\bFULL\s+JOIN\s+({})\b", "FULL JOIN {}"),
    (r"\bUPDATE\s+({})\b", "UPDATE {}"),
    (r"\bINSERT\s+INTO\s+({})\b", "INSERT INTO {}"),
    (r"\bDELETE\s+FROM\s+({})\b", "DELETE FROM {}"),
    (r"\bTABLE\s+({})\b", "TABLE {}"),
    (r"\bREFERENCES\s+({})\b", "REFERENCES {}"),
    (r"\bINTO\s+({})\b", "INTO {}"),
]


def should_skip_replacement(content: str, match_start: int, match_end: int) -> bool:
    """
    Check if a replacement should be skipped (e.g., inside comments or strings).

    Args:
        content: Full file content
        match_start: Start position of match
        match_end: End position of match

    Returns:
        True if replacement should be skipped
    """
    # Check if we're inside a single-line comment (--)
    line_start = content.rfind("\n", 0, match_start) + 1
    line_content = content[line_start:match_end]
    if "--" in line_content[: line_content.rfind(content[line_start:match_start])]:
        return True

    # Check if we're inside a multi-line comment (/* */)
    before_match = content[:match_start]
    comment_start = before_match.rfind("/*")
    if comment_start != -1:
        comment_end = content.find("*/", comment_start)
        if comment_end == -1 or comment_end > match_start:
            return True

    # Check if we're inside a string literal (single or double quotes)
    # Simple heuristic: count quotes before match
    single_quotes_before = before_match.count("'") - before_match.count("''")
    if single_quotes_before % 2 == 1:
        # Inside single-quoted string
        return True

    double_quotes_before = before_match.count('"')
    if double_quotes_before % 2 == 1:
        # Inside double-quoted string
        return True

    return False


def update_file(
    file_path: Path, table_name: str, new_name: str, dry_run: bool = False
) -> tuple[bool, int]:
    """
    Update a single SQL file with table name replacements.

    Args:
        file_path: Path to SQL file
        table_name: Old table name to replace
        new_name: New table name
        dry_run: If True, don't write changes

    Returns:
        Tuple of (was_updated, replacement_count)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        replacement_count = 0

        # Apply all patterns
        for pattern_template, replacement_template in PATTERNS:
            pattern = pattern_template.format(re.escape(table_name))
            replacement = replacement_template.format(new_name)

            # Find all matches and check each one
            matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
            for match in reversed(matches):  # Process from end to preserve positions
                if not should_skip_replacement(content, match.start(), match.end()):
                    content = (
                        content[: match.start()] + replacement + content[match.end() :]
                    )
                    replacement_count += 1

        # Only write if content changed
        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding="utf-8")
            return True, replacement_count
        return False, 0
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False, 0


def main():
    parser = argparse.ArgumentParser(
        description="Update SQL file table references to new naming convention"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="server/app/sql",
        help="Directory to search for SQL files (default: server/app/sql)",
    )
    parser.add_argument(
        "--version", type=str, default="v4", help="SQL version directory (default: v4)"
    )
    args = parser.parse_args()

    # Find SQL files in specified directory
    sql_dir = Path(args.dir)
    if args.version:
        sql_dir = sql_dir / args.version
    sql_files = list(sql_dir.rglob("*.sql"))

    if not sql_files:
        print(f"No SQL files found in {sql_dir}")
        return

    print(f"Found {len(sql_files)} SQL files")
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified\n")

    total_updated = 0
    total_replacements = 0

    # Step 1: Handle special plural artifact tables FIRST
    # These take precedence because they map both singular and plural forms
    print("\n1. Updating special plural artifact tables...")
    for old_name, new_name in SPECIAL_PLURAL_ARTIFACTS.items():
        if old_name == new_name:
            continue  # Skip if already correct
        count = 0
        replacements = 0
        for sql_file in sql_files:
            updated, repl_count = update_file(
                sql_file, old_name, new_name, args.dry_run
            )
            if updated:
                count += 1
                replacements += repl_count
        if count > 0:
            print(
                f"  {old_name} → {new_name}: {count} files ({replacements} replacements)"
            )
            total_updated += count
            total_replacements += replacements

    # Step 2: Handle regular artifact tables (singular → {name}_artifact)
    # Exclude special ones that were already handled
    print("\n2. Updating regular artifact tables...")
    special_singulars = {"chat", "grade", "run", "message", "key"}
    for artifact in REGULAR_ARTIFACTS:
        if artifact in special_singulars:
            continue  # Already handled in step 1
        new_name = f"{artifact}_artifact"
        count = 0
        replacements = 0
        for sql_file in sql_files:
            updated, repl_count = update_file(
                sql_file, artifact, new_name, args.dry_run
            )
            if updated:
                count += 1
                replacements += repl_count
        if count > 0:
            print(
                f"  {artifact} → {new_name}: {count} files ({replacements} replacements)"
            )
            total_updated += count
            total_replacements += replacements

    # Step 3: Handle resource tables (plural → {name}_resource)
    # Exclude special plural artifacts that were already handled
    print("\n3. Updating resource tables...")
    special_plurals = {"chats", "grades", "runs", "messages", "keys"}
    for resource in RESOURCES:
        if resource in special_plurals:
            continue  # Already handled in step 1
        new_name = f"{resource}_resource"
        count = 0
        replacements = 0
        for sql_file in sql_files:
            updated, repl_count = update_file(
                sql_file, resource, new_name, args.dry_run
            )
            if updated:
                count += 1
                replacements += repl_count
        if count > 0:
            print(
                f"  {resource} → {new_name}: {count} files ({replacements} replacements)"
            )
            total_updated += count
            total_replacements += replacements

    print(f"\n{'Would update' if args.dry_run else 'Updated'}: {total_updated} files")
    print(f"Total replacements: {total_replacements}")


if __name__ == "__main__":
    main()
