#!/usr/bin/env python3
"""
Convert MV files from 6-step ceremony format to pure CREATE + separate indexes.

Reads from database/schema/views/ (subdirectory structure with 6-step MV files)
and rewrites to:
  - database/schema/views/<name>.sql         — header comment + CREATE MATERIALIZED VIEW ... WITH NO DATA
  - database/schema/indexes/views/<name>.sql  — CREATE INDEX statements for the MV

Usage:
    python database/scripts/convert_views.py
"""

import os
import re
import shutil
import sys


def parse_mv_file(path: str) -> tuple[str, str, str, list[str]]:
    """Parse a 6-step MV file and extract components.

    Returns:
        (header_comment, create_mv_block, mv_name, create_index_blocks)
    """
    content = open(path).read()
    lines = content.split("\n")

    # Extract header comment (lines before first ===== separator or DO $$ block)
    header_lines: list[str] = []
    for line in lines:
        if "=====" in line or line.strip().startswith("DO $$"):
            break
        header_lines.append(line)
    while header_lines and header_lines[-1].strip() == "":
        header_lines.pop()
    header = "\n".join(header_lines)

    # Extract CREATE MATERIALIZED VIEW ... WITH NO DATA block
    create_block = ""
    m = re.search(
        r"(CREATE MATERIALIZED VIEW\b.+?WITH NO DATA\s*;)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        create_block = m.group(1)

    # Extract MV name
    mv_name = ""
    name_m = re.search(r"CREATE MATERIALIZED VIEW\s+(\w+)", create_block, re.IGNORECASE)
    if name_m:
        mv_name = name_m.group(1)

    # Extract CREATE INDEX blocks (after the CREATE MV, before REFRESH)
    index_blocks: list[str] = []
    # Find all CREATE [UNIQUE] INDEX <name> ON ... statements
    # Require index name + ON to avoid matching step-header comments like
    # "Create Unique Index (Required for CONCURRENT refresh)"
    for idx_m in re.finditer(
        r"(CREATE\s+(?:UNIQUE\s+)?INDEX\s+\w+\s+ON\b.+?;)",
        content,
        re.DOTALL | re.IGNORECASE,
    ):
        index_blocks.append(idx_m.group(1))

    return header, create_block, mv_name, index_blocks


def convert_views(schema_dir: str) -> tuple[int, int]:
    """Convert all MV files in views/ subdirectories to flat pure-CREATE format."""
    views_dir = os.path.join(schema_dir, "views")
    indexes_views_dir = os.path.join(schema_dir, "indexes", "views")

    if not os.path.exists(views_dir):
        print(f"Error: {views_dir} not found", file=sys.stderr)
        return 0, 0

    # Collect all .sql files from subdirectories only
    mv_files: list[str] = []
    for root, dirs, files in os.walk(views_dir):
        # Only process files in subdirectories, not top-level (already converted) files
        if root == views_dir:
            continue
        for f in files:
            if f.endswith(".sql"):
                mv_files.append(os.path.join(root, f))
    mv_files.sort()

    if not mv_files:
        print("  No subdirectory MV files found (already converted?)")
        return 0, 0

    # Parse all
    parsed: list[tuple[str, str, str, str, list[str]]] = []
    for path in mv_files:
        basename = os.path.basename(path).replace(".sql", "")
        header, create_block, mv_name, index_blocks = parse_mv_file(path)
        if not create_block:
            print(f"  WARNING: No CREATE MV found in {path}")
            continue
        parsed.append((basename, header, create_block, mv_name, index_blocks))

    # Remove old subdirectory structure
    for item in os.listdir(views_dir):
        item_path = os.path.join(views_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)

    # Write flat view files + index files
    os.makedirs(indexes_views_dir, exist_ok=True)
    view_count = 0
    index_count = 0

    for basename, header, create_block, mv_name, index_blocks in parsed:
        # Write pure CREATE MV file
        view_path = os.path.join(views_dir, f"{basename}.sql")
        with open(view_path, "w") as f:
            f.write(header + "\n\n")
            f.write(create_block + "\n")
        view_count += 1

        # Write MV index file
        if index_blocks:
            idx_path = os.path.join(indexes_views_dir, f"{basename}.sql")
            with open(idx_path, "w") as f:
                f.write(f"-- Indexes for materialized view: {mv_name}\n")
                f.write("--\n\n")
                f.write("\n\n".join(index_blocks) + "\n")
            index_count += len(index_blocks)

    return view_count, index_count


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.dirname(script_dir)
    schema_dir = os.path.join(db_dir, "schema")

    print(f"Converting MV files in {schema_dir}/views/")
    view_count, index_count = convert_views(schema_dir)
    print(f"  Wrote {view_count} pure CREATE MV files → views/")
    print(f"  Extracted {index_count} indexes → indexes/views/")


if __name__ == "__main__":
    main()
