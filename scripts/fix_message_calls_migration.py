#!/usr/bin/env python3
"""
Script to fix SQL files after dropping message_calls, message_audios,
message_texts, message_images, message_videos, message_documents, and instruction_schemas tables.

Changes:
1. Remove JOIN message_calls and replace mc.message_id with c.message_id (only when mc is from message_calls)
2. Replace INSERT INTO message_calls with UPDATE calls SET message_id
3. Remove JOIN message_audios and fix audio lookups to go through calls
4. Remove references to instruction_schemas
"""

import re
from pathlib import Path

SQL_DIR = Path("/Users/ashoksaravanan/Coding/glow/server/app/sql/v4")


def fix_join_message_calls(content: str) -> str:
    """
    Fix various message_calls patterns. Be careful not to touch message_contents mc patterns.
    """
    # Pattern 1: Inline subquery pattern
    # FROM calls c JOIN message_calls mc ON mc.call_id = c.id JOIN message_runs mr ON mr.message_id = mc.message_id
    # -> FROM calls c JOIN message_runs mr ON mr.message_id = c.message_id
    content = re.sub(
        r"(FROM|JOIN) calls c JOIN message_calls mc ON mc\.call_id = c\.id JOIN message_runs mr ON mr\.message_id = mc\.message_id",
        r"\1 calls c JOIN message_runs mr ON mr.message_id = c.message_id",
        content,
    )

    # Pattern 1b: Similar but with departments_resource
    content = re.sub(
        r"FROM departments_resource d JOIN calls c ON c\.id = d\.call_id JOIN message_calls mc ON mc\.call_id = c\.id JOIN message_runs mr ON mr\.message_id = mc\.message_id",
        r"FROM departments_resource d JOIN calls c ON c.id = d.call_id JOIN message_runs mr ON mr.message_id = c.message_id",
        content,
    )

    # Pattern 2: JOIN message_calls mc ON mc.call_id = c.id (standalone on its own line)
    # Only match when followed by a line that uses mc.message_id
    content = re.sub(
        r"\n(\s*)JOIN message_calls mc ON mc\.call_id = c\.id\s*\n(\s*)(.+)mr\.message_id = mc\.message_id",
        r"\n\2\3mr.message_id = c.message_id",
        content,
    )

    # Pattern 2b: Same but for c2 alias
    content = re.sub(
        r"\n(\s*)JOIN message_calls mc ON mc\.call_id = c2\.id\s*\n(\s*)(.+)mr\.message_id = mc\.message_id",
        r"\n\2\3mr.message_id = c2.message_id",
        content,
    )

    # Pattern 3: JOIN message_calls mcc ON mcc.message_id = X JOIN calls tc ON tc.id = mcc.call_id
    # -> JOIN calls tc ON tc.message_id = X
    content = re.sub(
        r"JOIN message_calls mcc ON mcc\.message_id = (\S+)\s*\n\s*JOIN calls tc ON tc\.id = mcc\.call_id",
        r"JOIN calls tc ON tc.message_id = \1",
        content,
    )
    content = re.sub(
        r"JOIN message_calls mcc2 ON mcc2\.message_id = (\S+)\s*\n\s*JOIN calls tc ON tc\.id = mcc2\.call_id",
        r"JOIN calls tc ON tc.message_id = \1",
        content,
    )

    # Pattern 4: Multiline JOIN message_calls patterns
    content = re.sub(
        r"JOIN message_calls mcc ON mcc\.message_id = (\S+)(\s+)JOIN calls tc ON tc\.id = mcc\.call_id",
        r"JOIN calls tc ON tc.message_id = \1",
        content,
    )

    return content


def fix_insert_message_calls(content: str) -> str:
    """
    Fix pattern:
    INSERT INTO message_calls (message_id, call_id, created_at, updated_at)
    VALUES (v_message_id, v_call_id, NOW(), NOW());

    Becomes:
    UPDATE calls SET message_id = v_message_id WHERE id = v_call_id;
    """
    # Pattern for INSERT INTO message_calls with various formats
    # Match multi-line INSERT statements
    pattern = r"INSERT INTO message_calls\s*\(\s*message_id\s*,\s*call_id\s*,\s*created_at\s*,\s*updated_at\s*\)\s*\n?\s*VALUES\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*NOW\(\)\s*,\s*NOW\(\)\s*\);"

    def replace_insert(match):
        message_id_var = match.group(1)
        call_id_var = match.group(2)
        return (
            f"UPDATE calls SET message_id = {message_id_var} WHERE id = {call_id_var};"
        )

    content = re.sub(pattern, replace_insert, content, flags=re.IGNORECASE)

    # Also handle the case with ON CONFLICT
    pattern_conflict = r"INSERT INTO message_calls\s*\(\s*message_id\s*,\s*call_id\s*,\s*created_at\s*,\s*updated_at\s*\)\s*\n?\s*VALUES\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*NOW\(\)\s*,\s*NOW\(\)\s*\)\s*ON CONFLICT[^;]*;"

    content = re.sub(pattern_conflict, replace_insert, content, flags=re.IGNORECASE)

    # Handle CTE-style INSERT (as in link_system_tool_call)
    # This is more complex - need to convert to UPDATE with subquery
    # For now, just mark these for manual fix

    return content


def fix_join_message_audios(content: str) -> str:
    """
    Fix pattern:
    LEFT JOIN message_audios ma ON ma.message_id = m.id
    LEFT JOIN audios_resource ar ON ar.id = ma.audio_id

    Becomes:
    LEFT JOIN calls c_audio ON c_audio.message_id = m.id
    LEFT JOIN audios_resource ar ON ar.call_id = c_audio.id
    """
    # Check if message_audios is referenced
    if "message_audios" not in content:
        return content

    # Replace the JOIN pattern
    content = re.sub(
        r"LEFT JOIN message_audios ma ON ma\.message_id = m\.id",
        "LEFT JOIN calls c_audio ON c_audio.message_id = m.id",
        content,
    )
    content = re.sub(
        r"JOIN message_audios ma ON ma\.message_id = mr\.message_id",
        "JOIN calls c_audio ON c_audio.message_id = mr.message_id",
        content,
    )

    # Fix the audios_resource join
    content = re.sub(
        r"(LEFT )?JOIN audios_resource ar ON ar\.id = ma\.audio_id",
        r"\1JOIN audios_resource ar ON ar.call_id = c_audio.id",
        content,
    )

    # Replace any remaining ma. references
    content = content.replace("ma.audio_id", "ar.id")
    content = content.replace("ma.message_id", "c_audio.message_id")

    return content


def fix_insert_message_audios(content: str) -> str:
    """
    Fix pattern:
    INSERT INTO message_audios (message_id, audio_id, created_at, updated_at)

    This should be removed - audios are linked via calls.message_id -> audios_resource.call_id
    """
    # Remove INSERT INTO message_audios statements
    pattern = r"INSERT INTO message_audios\s*\([^)]+\)\s*\n?\s*(?:SELECT[^;]+|VALUES[^;]+)(?:ON CONFLICT[^;]+)?;"
    content = re.sub(
        pattern,
        "-- message_audios INSERT removed - audios linked via calls.message_id",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return content


def fix_instruction_schemas(content: str) -> str:
    """
    Remove references to instruction_schemas table.
    """
    if "instruction_schemas" not in content:
        return content

    # Remove JOIN instruction_schemas lines
    content = re.sub(r"\s*LEFT JOIN instruction_schemas[^\n]+\n", "\n", content)

    # Remove references to ins. columns (likely ins.schema_id)
    content = re.sub(r"ins\.schema_id", "NULL::uuid", content)
    content = re.sub(r"ins\.instruction_id", "NULL::uuid", content)

    return content


def process_file(filepath: Path) -> tuple[bool, list[str]]:
    """Process a single SQL file and return (changed, changes_made)."""
    changes = []

    with open(filepath) as f:
        original = f.read()

    content = original

    # Apply fixes
    if "message_calls" in content:
        content = fix_join_message_calls(content)
        content = fix_insert_message_calls(content)
        if content != original:
            changes.append("message_calls")

    if "message_audios" in content:
        before = content
        content = fix_join_message_audios(content)
        content = fix_insert_message_audios(content)
        if content != before:
            changes.append("message_audios")

    if "instruction_schemas" in content:
        before = content
        content = fix_instruction_schemas(content)
        if content != before:
            changes.append("instruction_schemas")

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        return True, changes

    return False, changes


def main():
    """Main function to process all SQL files."""
    print("Fixing SQL files for message_calls migration...")
    print("=" * 60)

    changed_files = []

    for sql_file in SQL_DIR.rglob("*.sql"):
        changed, changes = process_file(sql_file)
        if changed:
            rel_path = sql_file.relative_to(SQL_DIR)
            print(f"  Fixed: {rel_path} ({', '.join(changes)})")
            changed_files.append((rel_path, changes))

    print("=" * 60)
    print(f"Total files modified: {len(changed_files)}")

    # Summary by change type
    mc_count = sum(1 for _, changes in changed_files if "message_calls" in changes)
    ma_count = sum(1 for _, changes in changed_files if "message_audios" in changes)
    is_count = sum(
        1 for _, changes in changed_files if "instruction_schemas" in changes
    )

    print(f"  - message_calls fixes: {mc_count}")
    print(f"  - message_audios fixes: {ma_count}")
    print(f"  - instruction_schemas fixes: {is_count}")


if __name__ == "__main__":
    main()
