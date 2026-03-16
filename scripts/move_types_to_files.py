#!/usr/bin/env python3
"""Move type definitions from search.py and get.py into types.py for each resource."""

import os
import re
from pathlib import Path

BASE = Path("server/app/api/v4/resources")
SERVER = Path("server")


def extract_class_blocks(filepath):
    """Extract all class blocks from a Python file.
    Returns list of dicts: {name, start, end, source_lines}
    start/end are 0-indexed line numbers (end is exclusive).
    """
    with open(filepath) as f:
        lines = f.readlines()

    blocks = []
    i = 0
    while i < len(lines):
        match = re.match(r"^class (\w+)\(", lines[i])
        if match:
            class_name = match.group(1)
            start = i

            # Find end: scan forward until we hit a non-blank, non-indented line
            j = i + 1
            while j < len(lines):
                line = lines[j]
                if line.strip() == "":
                    j += 1
                elif line[0].isspace():
                    j += 1
                else:
                    break
            end = j  # exclusive

            # Trim trailing blank lines from the class block
            actual_end = end
            while actual_end > start + 1 and lines[actual_end - 1].strip() == "":
                actual_end -= 1

            blocks.append(
                {
                    "name": class_name,
                    "start": start,
                    "end": end,  # exclusive, includes trailing blanks
                    "actual_end": actual_end,  # exclusive, no trailing blanks
                    "source_lines": lines[start:actual_end],
                }
            )
            i = end
        else:
            i += 1

    return blocks, lines


def find_comment_block_above(lines, class_start):
    """Find comment lines and section headers above a class definition."""
    i = class_start - 1
    comment_start = class_start

    while i >= 0:
        stripped = lines[i].strip()
        if stripped == "":
            # blank line - could be between comment and class
            i -= 1
        elif stripped.startswith("#"):
            comment_start = i
            i -= 1
        else:
            break

    return comment_start


def determine_imports(class_sources):
    """Determine what imports types.py needs based on class source code."""
    combined = "".join("".join(b["source_lines"]) for b in class_sources)

    imports = []
    typing_imports = []

    if "UUID" in combined:
        imports.append("from uuid import UUID")
    if "Any" in combined:
        typing_imports.append("Any")
    if "BaseModel" in combined:
        imports.append("from pydantic import BaseModel")
    if re.search(r"\bField\b", combined):
        # Check it's actually used as Field(...) not just in a comment
        if "Field(" in combined or "= Field" in combined:
            # Replace the pydantic import with one that includes Field
            imports = [
                imp
                if "pydantic" not in imp
                else "from pydantic import BaseModel, Field"
                for imp in imports
            ]

    if typing_imports:
        imports.insert(0, f"from typing import {', '.join(sorted(typing_imports))}")

    return imports


def build_types_file(imports, class_blocks, extra_imports=None):
    """Build the types.py content."""
    lines = ['"""Types for this resource endpoint."""\n', "\n"]

    for imp in imports:
        lines.append(imp + "\n")
    if extra_imports:
        lines.append("\n")
        for imp in extra_imports:
            lines.append(imp + "\n")

    for block in class_blocks:
        lines.append("\n\n")
        lines.extend(block["source_lines"])
        # Ensure trailing newline
        if block["source_lines"] and not block["source_lines"][-1].endswith("\n"):
            lines.append("\n")

    # Ensure file ends with single newline
    content = "".join(lines)
    content = content.rstrip("\n") + "\n"
    return content


def remove_classes_from_file(filepath, blocks_to_remove, lines):
    """Remove class blocks from a file, including leading comments/section headers."""
    # Build set of line ranges to remove
    remove_ranges = []
    for block in blocks_to_remove:
        # Find comment block above
        comment_start = find_comment_block_above(lines, block["start"])
        remove_ranges.append((comment_start, block["end"]))

    # Merge overlapping ranges
    remove_ranges.sort()
    merged = []
    for start, end in remove_ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Build remaining lines
    remaining = []
    i = 0
    for start, end in merged:
        remaining.extend(lines[i:start])
        i = end
    remaining.extend(lines[i:])

    return remaining


def add_import_to_file(lines, resource, class_names):
    """Add 'from app.api.v4.resources.{resource}.types import ...' to a file."""
    # Build the import statement
    if len(class_names) <= 3:
        import_line = f"from app.api.v4.resources.{resource}.types import {', '.join(sorted(class_names))}\n"
    else:
        parts = [f"from app.api.v4.resources.{resource}.types import (\n"]
        for name in sorted(class_names):
            parts.append(f"    {name},\n")
        parts.append(")\n")
        import_line = "".join(parts)

    # Find where to insert (after the last import block)
    last_import_line = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            last_import_line = i
        elif stripped.startswith(")") and i > 0 and "import" in lines[i - 1]:
            last_import_line = i

    # Insert after last import
    insert_pos = last_import_line + 1
    lines.insert(insert_pos, import_line)

    return lines


def cleanup_unused_imports(lines, removed_names):
    """Remove imports that are no longer used after class removal."""
    content = "".join(lines)

    # Check if BaseModel is still used (not just in import)
    basemodel_used = False
    for line in lines:
        stripped = line.strip()
        if (
            "BaseModel" in stripped
            and not stripped.startswith("from ")
            and not stripped.startswith("import ")
        ):
            basemodel_used = True
            break

    if not basemodel_used:
        # Remove BaseModel import
        new_lines = []
        for line in lines:
            if line.strip() == "from pydantic import BaseModel":
                continue
            elif "from pydantic import BaseModel, Field" in line.strip():
                # Check if Field is still used
                field_used = any(
                    "Field(" in l or "= Field" in l
                    for l in lines
                    if not l.strip().startswith("from ")
                )
                if field_used:
                    new_lines.append(
                        line.replace("BaseModel, Field", "Field").replace(
                            "BaseModel,Field", "Field"
                        )
                    )
                continue
            elif "from pydantic import" in line and "BaseModel" in line:
                # Multi-import line, remove BaseModel
                new_line = re.sub(r",?\s*BaseModel\s*,?", "", line)
                if (
                    "import ()" in new_line
                    or "import" in new_line
                    and new_line.strip().endswith("import")
                ):
                    continue
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        lines = new_lines

    # Check if Any is still used
    any_used = False
    for line in lines:
        stripped = line.strip()
        if (
            "Any" in stripped
            and not stripped.startswith("from ")
            and not stripped.startswith("import ")
        ):
            any_used = True
            break

    if not any_used:
        new_lines = []
        for line in lines:
            if "from typing import" in line and "Any" in line:
                # Remove Any from the import
                new_line = re.sub(r",?\s*Any\s*,?", ",", line)
                # Clean up
                new_line = re.sub(r"import\s*,", "import ", new_line)
                new_line = re.sub(r",\s*\)", ")", new_line)
                new_line = re.sub(r",\s*$", "\n", new_line)
                if "import ()" in new_line or new_line.strip() == "from typing import":
                    continue
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        lines = new_lines

    return lines


def update_external_import(filepath, resource, old_module, class_names):
    """Update an external file to import from types.py instead of get.py."""
    with open(filepath) as f:
        content = f.read()

    old_path = f"app.api.v4.resources.{resource}.{old_module}"
    new_path = f"app.api.v4.resources.{resource}.types"

    # Replace the import path
    new_content = content.replace(f"from {old_path} import", f"from {new_path} import")

    if new_content != content:
        with open(filepath, "w") as f:
            f.write(new_content)
        return True
    return False


def process_resource(resource_dir):
    """Process a single resource directory."""
    resource = resource_dir.name
    search_py = resource_dir / "search.py"
    get_py = resource_dir / "get.py"
    types_py = resource_dir / "types.py"

    if not search_py.exists():
        return

    # Extract classes from search.py
    search_blocks, search_lines = extract_class_blocks(str(search_py))
    if not search_blocks:
        return

    # Check if get.py has local classes too
    get_blocks = []
    get_lines = []
    get_has_local_types = False
    if get_py.exists():
        get_blocks, get_lines = extract_class_blocks(str(get_py))
        # Only include if get.py defines types locally (not imported from app.sql.types)
        # Check if any class is referenced in the file itself (defined locally)
        if get_blocks:
            # Check if classes are actually defined here (have body, not just imported)
            local_get_blocks = []
            for block in get_blocks:
                # All class blocks extracted are local definitions
                local_get_blocks.append(block)
            get_blocks = local_get_blocks
            get_has_local_types = len(get_blocks) > 0

    # Build types.py content
    all_blocks = []
    # Get types first (they may be referenced by search types)
    if get_has_local_types:
        all_blocks.extend(get_blocks)
    all_blocks.extend(search_blocks)

    # Determine imports for types.py
    imports = determine_imports(all_blocks)

    # Check if any search type references a get type (need to keep in same file)
    # Also check if types reference app.sql.types
    extra_imports = []
    search_source = "".join("".join(b["source_lines"]) for b in search_blocks)

    # Check for references to app.sql.types in the class definitions
    for block in search_blocks:
        block_src = "".join(block["source_lines"])
        # Find type references like QGetFooV4Item that might come from sql.types
        for match in re.finditer(r"\b(QGet\w+V4Item)\b", block_src):
            type_name = match.group(1)
            # If this type is defined in get_blocks, it's fine (same file)
            if any(b["name"] == type_name for b in get_blocks):
                continue
            # Otherwise it might need to be imported from app.sql.types
            # Check if search.py imports it from app.sql.types
            search_content = "".join(search_lines)
            if (
                "from app.sql.types import" in search_content
                and type_name in search_content
            ):
                extra_imports.append(f"    {type_name},")

    # Finalize extra imports
    if extra_imports:
        extra_imports = [
            "from app.sql.types import (",
            *extra_imports,
            ")",
        ]

    types_content = build_types_file(imports, all_blocks, extra_imports)

    # Write types.py
    with open(str(types_py), "w") as f:
        f.write(types_content)

    # Update search.py
    search_class_names = [b["name"] for b in search_blocks]
    new_search_lines = remove_classes_from_file(
        str(search_py), search_blocks, search_lines
    )

    # If search.py imported types from get.py, update to import from types.py
    if get_has_local_types:
        get_class_names = [b["name"] for b in get_blocks]
        new_search_lines_str = "".join(new_search_lines)
        old_import = f"from app.api.v4.resources.{resource}.get import"
        if old_import in new_search_lines_str:
            new_search_lines = [
                line.replace(
                    f"from app.api.v4.resources.{resource}.get import",
                    f"from app.api.v4.resources.{resource}.types import",
                )
                for line in new_search_lines
            ]

    # Add import from types.py for search classes
    new_search_lines = add_import_to_file(
        new_search_lines, resource, search_class_names
    )
    new_search_lines = cleanup_unused_imports(new_search_lines, search_class_names)

    # Clean up excessive blank lines
    search_content = "".join(new_search_lines)
    search_content = re.sub(r"\n{4,}", "\n\n\n", search_content)
    search_content = search_content.rstrip("\n") + "\n"

    with open(str(search_py), "w") as f:
        f.write(search_content)

    # Update get.py if it had local types
    if get_has_local_types:
        get_class_names = [b["name"] for b in get_blocks]
        new_get_lines = remove_classes_from_file(str(get_py), get_blocks, get_lines)
        new_get_lines = add_import_to_file(new_get_lines, resource, get_class_names)
        new_get_lines = cleanup_unused_imports(new_get_lines, get_class_names)

        get_content = "".join(new_get_lines)
        get_content = re.sub(r"\n{4,}", "\n\n\n", get_content)
        get_content = get_content.rstrip("\n") + "\n"

        with open(str(get_py), "w") as f:
            f.write(get_content)

        # Update external importers of get.py types
        update_external_importers(resource, get_class_names)

    return {
        "resource": resource,
        "search_classes": [b["name"] for b in search_blocks],
        "get_classes": [b["name"] for b in get_blocks] if get_has_local_types else [],
    }


def update_external_importers(resource, class_names):
    """Find and update all files that import from {resource}.get to import from {resource}.types."""
    old_import_path = f"from app.api.v4.resources.{resource}.get import"

    # Search all Python files
    for root, dirs, files in os.walk(str(SERVER)):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(root, fname)

            # Skip the resource's own files (already handled)
            resource_dir = str(BASE / resource)
            if filepath.startswith(resource_dir):
                continue

            with open(filepath) as f:
                content = f.read()

            if old_import_path in content:
                new_content = content.replace(
                    old_import_path,
                    f"from app.api.v4.resources.{resource}.types import",
                )
                with open(filepath, "w") as f:
                    f.write(new_content)
                print(f"  Updated external: {filepath}")


def main():
    processed = 0
    search_total = 0
    get_total = 0
    external_total = 0

    for resource_dir in sorted(BASE.iterdir()):
        if not resource_dir.is_dir() or resource_dir.name.startswith("_"):
            continue

        result = process_resource(resource_dir)
        if result:
            processed += 1
            sc = len(result["search_classes"])
            gc = len(result["get_classes"])
            search_total += sc
            get_total += gc
            marker = " + get.py types" if gc else ""
            print(f"  {result['resource']}: {sc} search classes{marker}")

    print(f"\nDone! Processed {processed} resources.")
    print(f"  Search classes moved: {search_total}")
    print(f"  Get classes moved: {get_total}")


if __name__ == "__main__":
    main()
