#!/usr/bin/env python3
"""Fix get.py files: move context fetch into *_internal() and remove from endpoint.

The migration script incorrectly:
1. Left self-assignments like `user_role = user_role` in *_internal()
2. Injected a duplicate context block in the endpoint function

This script fixes both issues for the 7 affected get.py files.
"""

import os
import re

BASE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "server", "app", "api", "v4", "artifacts"
)
BASE_DIR = os.path.abspath(BASE_DIR)

# Context block to inject inside *_internal() - uses pool that's already available
# This goes BEFORE the access check, right after `pool = get_pool()` / pool check
INTERNAL_CONTEXT_BLOCK = """\
    # Fetch user context for permissions
    async with pool.acquire() as context_conn:
        resolved_context = await get_profile_context_internal(
            conn=context_conn,
            profile_id=profile_id,
            department_id_cookie=None,
            bypass_cache=bypass_cache,
        )
    user_role = resolved_context.user_role
    actor_name = resolved_context.actor_name
    user_department_ids = [
        d.department_id for d in resolved_context.departments if d.department_id
    ]

"""

# Erroneously injected block in endpoint function (to remove)
ENDPOINT_CONTEXT_BLOCK_PATTERN = re.compile(
    r"        # Fetch user context for permissions and audit logging\n"
    r"        pool = get_pool\(\)\n"
    r"        if pool:\n"
    r"            async with pool\.acquire\(\) as context_conn:\n"
    r"                resolved_context = await get_profile_context_internal\(\n"
    r"                    conn=context_conn,\n"
    r"                    profile_id=profile_id,\n"
    r"                    department_id_cookie=None,\n"
    r"                    bypass_cache=False,\n"
    r"                \)\n"
    r"                actor_name = resolved_context\.actor_name\n"
    r"                user_role = resolved_context\.user_role\n"
    r"                user_department_ids = \[\n"
    r"                    d\.department_id\n"
    r"                    for d in resolved_context\.departments\n"
    r"                    if d\.department_id\n"
    r"                \]\n"
    r"        else:\n"
    r"            actor_name = None\n"
    r"            user_role = None\n"
    r"            user_department_ids = \[\]\n"
    r"\n",
    re.MULTILINE,
)

# Files with *_internal() helper pattern
INTERNAL_FILES = [
    "department/get.py",
    "eval/get.py",
    "field/get.py",
    "parameter/get.py",
    "profile/get.py",
    "scenario/get.py",
    "simulation/get.py",
]

# setting/get.py has a different pattern - no internal function
SETTING_FILE = "setting/get.py"


def fix_internal_file(filepath: str) -> bool:
    """Fix a get.py file with *_internal() function."""
    with open(filepath) as f:
        content = f.read()

    original = content

    # 1. Remove self-assignments in the internal function
    # Replace lines like "        user_role = user_role" with nothing
    content = content.replace("        user_role = user_role\n", "")
    content = content.replace("        user_department_ids = user_department_ids\n", "")

    # 2. Remove the erroneously injected context block from the endpoint function
    content = ENDPOINT_CONTEXT_BLOCK_PATTERN.sub("", content)

    # 3. Inject context fetch in *_internal() - after the draft check block, before access check
    # Find the pattern: draft check block ends, then "async with pool.acquire() as conn:"
    # We want to insert the context block before the first "async with pool.acquire() as conn:"
    # that's inside the *_internal function

    # Find the internal function
    internal_func_match = re.search(r"async def \w+_internal\(", content)
    if not internal_func_match:
        print(f"  WARNING: No *_internal function found in {filepath}")
        return content != original

    func_start = internal_func_match.start()

    # Find the first "async with pool.acquire() as conn:" after the internal function
    conn_pattern = re.compile(r"(\n    async with pool\.acquire\(\) as conn:)")
    conn_match = conn_pattern.search(content, func_start)
    if not conn_match:
        print(
            f"  WARNING: No pool.acquire() as conn found in internal function: {filepath}"
        )
        return content != original

    # Insert context block before the "async with pool.acquire() as conn:" line
    insert_pos = conn_match.start() + 1  # +1 for the newline
    content = content[:insert_pos] + INTERNAL_CONTEXT_BLOCK + content[insert_pos:]

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


def fix_setting_file(filepath: str) -> bool:
    """Fix setting/get.py - only needs self-assignment removal."""
    with open(filepath) as f:
        content = f.read()

    original = content

    # Remove self-assignments
    content = content.replace("        user_role = user_role\n", "")
    content = content.replace("        user_department_ids = user_department_ids\n", "")

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


def main():
    print("Fixing get.py files...")
    modified = 0

    for relpath in INTERNAL_FILES:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (not found): {relpath}")
            continue
        try:
            if fix_internal_file(filepath):
                print(f"  Fixed: {relpath}")
                modified += 1
        except Exception as e:
            print(f"  ERROR: {relpath}: {e}")
            import traceback

            traceback.print_exc()

    # Fix setting/get.py
    setting_path = os.path.join(BASE_DIR, SETTING_FILE)
    if os.path.exists(setting_path):
        try:
            if fix_setting_file(setting_path):
                print(f"  Fixed: {SETTING_FILE}")
                modified += 1
        except Exception as e:
            print(f"  ERROR: {SETTING_FILE}: {e}")

    print(f"\nDone! Fixed {modified} files.")


if __name__ == "__main__":
    main()
