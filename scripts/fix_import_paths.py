#!/usr/bin/env python3
"""Fix imports that were incorrectly changed from .get to .types by the automation script.

The move_types_to_files.py script replaced ALL imports from {resource}.get with
{resource}.types, but only TYPE CLASS imports should have been changed. Function
imports (router, *_internal) need to stay as .get imports.

This script handles both single-line and multi-line imports.
"""

import os
import re

# Resources that had get.py types moved to types.py
resources_with_get_types = [
    "cohorts",
    "images",
    "objectives",
    "options",
    "problem_statements",
    "questions",
    "roles",
    "settings",
    "simulation_positions",
    "simulations",
    "standard_groups",
    "standards",
    "videos",
]

server_dir = "server"
fixes = []

for root, dirs, files in os.walk(server_dir):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for fname in files:
        if not fname.endswith(".py"):
            continue
        filepath = os.path.join(root, fname)

        with open(filepath) as f:
            content = f.read()

        original = content

        for resource in resources_with_get_types:
            types_import = f"from app.api.v4.resources.{resource}.types import"
            get_import = f"from app.api.v4.resources.{resource}.get import"

            if types_import not in content:
                continue

            # Use regex to find import blocks (both single-line and multi-line)
            # Pattern matches: from ...types import X or from ...types import (\n    X,\n    Y,\n)
            pattern = (
                re.escape(types_import) + r"(.*?)(?=\n(?:from |import |\n|$|[a-zA-Z#]))"
            )

            # Simpler approach: process line by line, tracking multi-line imports
            lines = content.split("\n")
            new_lines = []
            in_multiline_import = False
            multiline_resource = None
            multiline_start_idx = None
            multiline_has_function = False

            for i, line in enumerate(lines):
                if in_multiline_import:
                    # Check if this line has router or _internal
                    if "router" in line or "_internal" in line:
                        multiline_has_function = True
                    # Check if multi-line import ends
                    if ")" in line:
                        in_multiline_import = False
                        if multiline_has_function:
                            # Revert the import line to .get
                            new_lines[multiline_start_idx] = new_lines[
                                multiline_start_idx
                            ].replace(types_import, get_import)
                    new_lines.append(line)
                    continue

                if types_import in line:
                    # Check if this is a multi-line import (ends with `(`)
                    import_part = line.split("import")[-1].strip()
                    if import_part == "(":
                        # Multi-line import starts
                        in_multiline_import = True
                        multiline_resource = resource
                        multiline_start_idx = len(new_lines)
                        multiline_has_function = False
                        new_lines.append(line)
                    else:
                        # Single-line import
                        if "router" in import_part or "_internal" in import_part:
                            line = line.replace(types_import, get_import)
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            content = "\n".join(new_lines)

        if content != original:
            with open(filepath, "w") as f:
                f.write(content)
            fixes.append(filepath)

print(f"Fixed {len(fixes)} files:")
for f in sorted(fixes):
    print(f"  {f}")
