#!/usr/bin/env python3
"""Fix unused context variables by trimming the context fetch block.

For files that don't use all three variables (actor_name, user_role, user_department_ids),
this script removes the unused variable assignments from the context block.
"""

import os
import re

BASE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "server", "app", "api", "v4", "artifacts"
)
BASE_DIR = os.path.abspath(BASE_DIR)


def is_var_used_beyond_context_block(content: str, var_name: str) -> bool:
    """Check if variable is used outside of the context fetch block."""
    # Remove the context block from content, then check for remaining references
    # Context block is between "# Fetch user context" and the next unindented line after "else:" block
    # Simpler approach: remove everything between "pool = get_pool()" and the blank line after the else block
    cleaned = re.sub(
        r"        # Fetch user context.*?user_department_ids = \[\]\n",
        "",
        content,
        flags=re.DOTALL,
    )
    # Also try the "audit logging" variant
    cleaned = re.sub(
        r"        # Fetch user context.*?actor_name = None\n",
        "",
        cleaned,
        flags=re.DOTALL,
    )
    return bool(re.search(rf"\b{var_name}\b", cleaned))


def trim_context_block(content: str) -> str:
    """Remove unused variable assignments from the context block."""
    lines = content.split("\n")

    # Find which variables are actually used
    uses_actor_name = is_var_used_beyond_context_block(content, "actor_name")
    uses_user_role = is_var_used_beyond_context_block(content, "user_role")
    uses_user_department_ids = is_var_used_beyond_context_block(
        content, "user_department_ids"
    )

    if uses_actor_name and uses_user_role and uses_user_department_ids:
        return content  # All used, nothing to trim

    new_lines = []
    skip_next_blank = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Remove actor_name assignment lines
        if not uses_actor_name:
            if stripped == "actor_name = resolved_context.actor_name":
                i += 1
                continue
            if stripped == "actor_name = None":
                i += 1
                continue

        # Remove user_role assignment lines
        if not uses_user_role:
            if stripped == "user_role = resolved_context.user_role":
                i += 1
                continue
            if stripped == "user_role = None":
                i += 1
                continue

        # Remove user_department_ids assignment lines (can be multi-line)
        if not uses_user_department_ids:
            if stripped.startswith("user_department_ids = ["):
                # Multi-line list comprehension - skip until closing ]
                while i < len(lines) and "]" not in lines[i]:
                    i += 1
                i += 1  # Skip the line with ]
                continue
            if stripped == "user_department_ids = []":
                i += 1
                continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines)


def process_file(filepath: str) -> bool:
    """Process a single file. Returns True if modified."""
    with open(filepath) as f:
        original = f.read()

    # Only process files with our context block
    if "resolved_context = await get_profile_context_internal(" not in original:
        return False

    content = trim_context_block(original)

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        relpath = os.path.relpath(filepath, os.path.join(BASE_DIR, ".."))
        print(f"  Fixed: {relpath}")
        return True
    return False


def main():
    print(f"Scanning artifacts directory: {BASE_DIR}")
    modified_count = 0
    for root, _dirs, files in os.walk(BASE_DIR):
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(root, fname)
            try:
                if process_file(filepath):
                    modified_count += 1
            except Exception as e:
                print(f"  ERROR processing {filepath}: {e}")
                import traceback

                traceback.print_exc()

    print(f"\nDone! Fixed {modified_count} files.")


if __name__ == "__main__":
    main()
