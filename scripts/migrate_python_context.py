#!/usr/bin/env python3
"""Migration script: Replace SQL-sourced user context fields with get_profile_context_internal().

The SQL migration removed actor_name, user_role, and user_department_ids from SQL results.
These fields now come from get_profile_context_internal() instead.

This script handles all ~80 affected Python files programmatically.
"""

import os
import re

BASE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "server", "app", "api", "v4", "artifacts"
)
BASE_DIR = os.path.abspath(BASE_DIR)

CONTEXT_IMPORT = "from app.api.v4.auth.context import get_profile_context_internal"
GET_POOL_IMPORT_FRAGMENT = "get_pool"

# The context fetch block to inject (indented with 8 spaces for inside try block)
CONTEXT_FETCH_BLOCK = """\
        # Fetch user context for permissions and audit logging
        pool = get_pool()
        if pool:
            async with pool.acquire() as context_conn:
                resolved_context = await get_profile_context_internal(
                    conn=context_conn,
                    profile_id=profile_id,
                    department_id_cookie=None,
                    bypass_cache=False,
                )
                actor_name = resolved_context.actor_name
                user_role = resolved_context.user_role
                user_department_ids = [
                    d.department_id for d in resolved_context.departments if d.department_id
                ]
        else:
            actor_name = None
            user_role = None
            user_department_ids = []

"""

# Variant for files that use current_profile_id instead of profile_id
CONTEXT_FETCH_BLOCK_CURRENT = CONTEXT_FETCH_BLOCK.replace(
    "profile_id=profile_id,", "profile_id=current_profile_id,"
)

# Minimal block for files that only need actor_name (no user_role/user_department_ids usage)
CONTEXT_FETCH_BLOCK_ACTOR_ONLY = """\
        # Fetch user context for audit logging
        pool = get_pool()
        if pool:
            async with pool.acquire() as context_conn:
                resolved_context = await get_profile_context_internal(
                    conn=context_conn,
                    profile_id=profile_id,
                    department_id_cookie=None,
                    bypass_cache=False,
                )
                actor_name = resolved_context.actor_name
        else:
            actor_name = None

"""

CONTEXT_FETCH_BLOCK_ACTOR_ONLY_CURRENT = CONTEXT_FETCH_BLOCK_ACTOR_ONLY.replace(
    "profile_id=profile_id,", "profile_id=current_profile_id,"
)


def has_import(content: str, import_str: str) -> bool:
    """Check if content already has a specific import."""
    return import_str in content


def add_context_import(content: str) -> str:
    """Add the get_profile_context_internal import if missing."""
    if has_import(content, CONTEXT_IMPORT):
        return content
    # Insert after the last import from app.api.v4.artifacts.* or before app.infra.*
    # Find a good insertion point - after permissions/types imports, before infra imports
    lines = content.split("\n")
    insert_idx = None
    for i, line in enumerate(lines):
        if line.startswith("from app.infra."):
            insert_idx = i
            break
        if line.startswith("from app.main"):
            insert_idx = i
            break
    if insert_idx is None:
        # Fallback: insert before first from app.sql or from app.utils
        for i, line in enumerate(lines):
            if line.startswith("from app.sql") or line.startswith("from app.utils"):
                insert_idx = i
                break
    if insert_idx is not None:
        lines.insert(insert_idx, CONTEXT_IMPORT)
        return "\n".join(lines)
    return content


def add_get_pool_import(content: str) -> str:
    """Add get_pool to imports if missing."""
    if GET_POOL_IMPORT_FRAGMENT in content:
        return content

    # Check if there's a "from app.main import get_db" line to extend
    pattern = r"from app\.main import get_db\b"
    match = re.search(pattern, content)
    if match:
        content = content.replace(
            match.group(0), "from app.main import get_db, get_pool"
        )
        return content

    # Check for "from app.main import get_db," (multiline or with other imports)
    pattern2 = r"from app\.main import ([^\n]+)"
    match2 = re.search(pattern2, content)
    if match2:
        imports = match2.group(1).strip()
        if "get_pool" not in imports:
            new_imports = imports.rstrip(")").rstrip() + ", get_pool"
            if imports.endswith(")"):
                new_imports += ")"
            content = content.replace(
                match2.group(0), f"from app.main import {new_imports}"
            )
        return content

    # No existing app.main import, add one
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("from app.sql") or line.startswith("from app.utils"):
            lines.insert(i, "from app.main import get_pool")
            return "\n".join(lines)

    return content


def find_profile_id_block_end(content: str) -> int | None:
    """Find the end of the 'if not profile_id:' block (the closing parenthesis line of HTTPException)."""
    lines = content.split("\n")
    in_profile_check = False
    paren_depth = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "if not profile_id:" in stripped or "if not current_profile_id:" in stripped:
            in_profile_check = True
            continue
        if in_profile_check:
            paren_depth += stripped.count("(") - stripped.count(")")
            if paren_depth <= 0 and (stripped == ")" or stripped.endswith(")")):
                # Found the closing of HTTPException block
                # Return the line after (skip blank line if present)
                next_idx = i + 1
                if next_idx < len(lines) and lines[next_idx].strip() == "":
                    return next_idx + 1
                return next_idx
    return None


def inject_context_block(
    content: str, uses_current_profile_id: bool = False, actor_only: bool = False
) -> str:
    """Inject the context fetch block after the profile_id validation block."""
    if "get_profile_context_internal(" in content and "pool = get_pool()" in content:
        # Already has context block
        return content

    idx = find_profile_id_block_end(content)
    if idx is None:
        print("  WARNING: Could not find profile_id check block end")
        return content

    lines = content.split("\n")

    if actor_only:
        block = (
            CONTEXT_FETCH_BLOCK_ACTOR_ONLY_CURRENT
            if uses_current_profile_id
            else CONTEXT_FETCH_BLOCK_ACTOR_ONLY
        )
    else:
        block = (
            CONTEXT_FETCH_BLOCK_CURRENT
            if uses_current_profile_id
            else CONTEXT_FETCH_BLOCK
        )

    block_lines = block.split("\n")
    # Remove trailing empty string from split
    if block_lines and block_lines[-1] == "":
        block_lines = block_lines[:-1]

    new_lines = lines[:idx] + block_lines + lines[idx:]
    return "\n".join(new_lines)


def replace_access_result_refs(content: str) -> str:
    """Replace access_result.user_role, access_result.actor_name, access_result.user_department_ids."""
    # Replace access_result.user_department_ids or [] -> user_department_ids
    content = re.sub(
        r"access_result\.user_department_ids\s+or\s+\[\]",
        "user_department_ids",
        content,
    )
    # Replace access_result.user_department_ids -> user_department_ids
    content = content.replace(
        "access_result.user_department_ids", "user_department_ids"
    )
    # Replace access_result.user_role -> user_role
    content = content.replace("access_result.user_role", "user_role")
    # Replace access_result.actor_name -> actor_name
    content = content.replace("access_result.actor_name", "actor_name")
    return content


def replace_result_actor_name(content: str) -> str:
    """Replace result.actor_name -> actor_name (for mutation result references)."""
    # Be careful not to replace access_result.actor_name (already handled)
    # Also don't replace bundle_result.actor_name or view_result.actor_name here
    # Use word boundary to avoid partial matches

    # Replace `result.actor_name` but NOT `access_result.actor_name`, `bundle_result.actor_name`, `view_result.actor_name`
    # Use negative lookbehind for common prefixes
    content = re.sub(
        r"(?<!access_)(?<!bundle_)(?<!view_)result\.actor_name",
        "actor_name",
        content,
    )
    return content


def replace_result_user_role(content: str) -> str:
    """Replace result.user_role -> user_role."""
    content = re.sub(
        r"(?<!access_)result\.user_role",
        "user_role",
        content,
    )
    return content


def replace_view_result_actor_name(content: str) -> str:
    """Replace view_result.actor_name -> actor_name."""
    content = content.replace("view_result.actor_name", "actor_name")
    return content


def replace_bundle_result_actor_name(content: str) -> str:
    """Replace bundle_result.actor_name -> actor_name."""
    content = content.replace("bundle_result.actor_name", "actor_name")
    return content


def needs_user_role(content: str) -> bool:
    """Check if the file uses user_role (from access_result or result)."""
    return "access_result.user_role" in content or "result.user_role" in content


def needs_user_department_ids(content: str) -> bool:
    """Check if the file uses user_department_ids."""
    return "access_result.user_department_ids" in content


def needs_actor_name_from_access(content: str) -> bool:
    """Check if the file uses actor_name from access_result."""
    return "access_result.actor_name" in content


def needs_actor_name_from_result(content: str) -> bool:
    """Check if the file uses actor_name from result (mutation result)."""
    # Check for result.actor_name but not access_result.actor_name
    return bool(
        re.search(r"(?<!access_)(?<!bundle_)(?<!view_)result\.actor_name", content)
    )


def needs_actor_name_from_view(content: str) -> bool:
    """Check if the file uses actor_name from view_result."""
    return "view_result.actor_name" in content


def needs_actor_name_from_bundle(content: str) -> bool:
    """Check if the file uses actor_name from bundle_result."""
    return "bundle_result.actor_name" in content


def file_already_migrated(content: str) -> bool:
    """Check if file already has context fetch block."""
    return (
        "get_profile_context_internal" in content
        and "pool = get_pool()" in content
        and "resolved_context" in content
    )


def uses_current_profile_id(content: str) -> bool:
    """Check if file uses current_profile_id instead of profile_id."""
    return "current_profile_id = http_request.state.profile_id" in content


def process_file(filepath: str) -> bool:
    """Process a single file. Returns True if modified."""
    with open(filepath) as f:
        original = f.read()

    content = original
    relpath = os.path.relpath(filepath, os.path.join(BASE_DIR, ".."))

    # Skip if already fully migrated
    if file_already_migrated(content):
        # But still check for residual references
        has_residual = (
            "access_result.user_role" in content
            or "access_result.actor_name" in content
            or "access_result.user_department_ids" in content
            or bool(
                re.search(
                    r"(?<!access_)(?<!bundle_)(?<!view_)result\.actor_name", content
                )
            )
            or bool(re.search(r"(?<!access_)result\.user_role", content))
        )
        if has_residual:
            print(f"  Fixing residual references in already-migrated: {relpath}")
            content = replace_access_result_refs(content)
            content = replace_result_actor_name(content)
            content = replace_result_user_role(content)
        elif (
            "view_result.actor_name" in content or "bundle_result.actor_name" in content
        ):
            print(f"  Fixing view/bundle result references in: {relpath}")
            content = replace_view_result_actor_name(content)
            content = replace_bundle_result_actor_name(content)
        else:
            return False
    else:
        # Determine what this file needs
        has_user_role = needs_user_role(content)
        has_dept_ids = needs_user_department_ids(content)
        has_actor_access = needs_actor_name_from_access(content)
        has_actor_result = needs_actor_name_from_result(content)
        has_actor_view = needs_actor_name_from_view(content)
        has_actor_bundle = needs_actor_name_from_bundle(content)

        needs_any = (
            has_user_role
            or has_dept_ids
            or has_actor_access
            or has_actor_result
            or has_actor_view
            or has_actor_bundle
        )

        if not needs_any:
            return False

        print(f"  Migrating: {relpath}")
        is_current = uses_current_profile_id(content)

        # Determine if we only need actor_name (no user_role/dept_ids)
        actor_only = not has_user_role and not has_dept_ids

        # Add imports
        content = add_context_import(content)
        content = add_get_pool_import(content)

        # Inject context fetch block
        content = inject_context_block(
            content, uses_current_profile_id=is_current, actor_only=actor_only
        )

        # Replace references
        if has_user_role:
            content = replace_access_result_refs(content)
            content = replace_result_user_role(content)
        if has_dept_ids:
            content = replace_access_result_refs(content)
        if has_actor_access:
            content = replace_access_result_refs(content)
        if has_actor_result:
            content = replace_result_actor_name(content)
        if has_actor_view:
            content = replace_view_result_actor_name(content)
        if has_actor_bundle:
            content = replace_bundle_result_actor_name(content)

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


def find_all_target_files() -> list[str]:
    """Find all Python files in artifacts that reference removed fields."""
    target_files = []
    for root, _dirs, files in os.walk(BASE_DIR):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(root, fname)
            with open(filepath) as f:
                content = f.read()

            # Check for any reference to removed fields
            if any(
                [
                    "access_result.user_role" in content,
                    "access_result.actor_name" in content,
                    "access_result.user_department_ids" in content,
                    re.search(
                        r"(?<!access_)(?<!bundle_)(?<!view_)result\.actor_name", content
                    ),
                    re.search(r"(?<!access_)result\.user_role", content),
                    "view_result.actor_name" in content,
                    "bundle_result.actor_name" in content,
                ]
            ):
                target_files.append(filepath)

    return sorted(target_files)


def main():
    print(f"Scanning artifacts directory: {BASE_DIR}")
    target_files = find_all_target_files()
    print(f"Found {len(target_files)} files with references to removed fields\n")

    modified_count = 0
    for filepath in target_files:
        try:
            if process_file(filepath):
                modified_count += 1
        except Exception as e:
            print(f"  ERROR processing {filepath}: {e}")
            import traceback

            traceback.print_exc()

    print(f"\nDone! Modified {modified_count} files.")


if __name__ == "__main__":
    main()
