"""Generate shared args.py from existing tools.py data.

Extracts all unique arg definitions from tools, creates deterministic IDs,
and rewrites tools.py to reference args by key instead of inline dicts.

Run: python database/scripts/generate_shared_args.py
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "core"))
sys.path.insert(0, str(PROJECT_ROOT))

from database.seeds.tools import tools

# Step 1: Collect unique args by name
arg_map: dict[str, dict] = {}
for tool in tools:
    for arg in tool.get("args", []):
        key = arg["name"]
        if key not in arg_map:
            arg_map[key] = {
                "name": arg["name"],
                "field_type": arg.get("field_type", "string"),
                "required": arg.get("required", False),
                "description": arg.get("description", ""),
            }

# Step 2: Generate args.py
lines = [
    '"""Shared argument resource seeds.',
    "",
    "Each arg is defined once with a deterministic ID. Tools reference args",
    "by key instead of inlining duplicate definitions.",
    "",
    f"Generated from {len(arg_map)} unique args across {len(tools)} tools.",
    "Regenerate with: python database/scripts/generate_shared_args.py",
    '"""',
    "",
    "from database.seeds.ids import sid",
    "",
    "SHARED_ARGS = {",
]

for name in sorted(arg_map.keys()):
    info = arg_map[name]
    parts = [
        f'id=sid("arg/{name}")',
        f'name="{name}"',
        f'field_type="{info["field_type"]}"',
    ]
    if info["required"]:
        parts.append("required=True")
    if info["description"]:
        parts.append(f'description="{info["description"]}"')
    lines.append(f'    "{name}": dict({", ".join(parts)}),')

lines.append("}")
lines.append("")
lines.append("# Flat list for seeding")
lines.append("args = list(SHARED_ARGS.values())")
lines.append("")

args_path = PROJECT_ROOT / "database" / "seeds" / "resources" / "args.py"
args_path.write_text("\n".join(lines))
print(f"Generated {len(arg_map)} shared args → {args_path}")

# Step 3: Rewrite tools.py — replace inline arg dicts with key lists
# Read original to preserve permission_id lines as-is
tools_content = (PROJECT_ROOT / "database" / "seeds" / "tools.py").read_text()

# For each tool, replace the args=[dict(...), ...] with args=["key1", "key2"]
new_tools = []
for tool in tools:
    arg_keys = [arg["name"] for arg in tool.get("args", [])]
    new_tools.append(tool | {"arg_keys": arg_keys})

# Write new tools.py
out_lines = [
    '"""Tool definitions for seeding.',
    "",
    "Tools reference shared args by key (from database/seeds/resources/args.py).",
    "Regenerate with: python database/scripts/generate_tools.py",
    '"""',
    "",
    "from database.seeds.ids import sid",
    "",
    "tools = [",
]

for tool in tools:
    arg_keys = [arg["name"] for arg in tool.get("args", [])]
    pid = tool.get("permission_id")
    out_lines.append("    dict(")
    out_lines.append(f'        id="{tool["id"]}",')
    out_lines.append(f'        name="{tool["name"]}",')
    out_lines.append(f'        description="{tool["description"]}",')
    # Reconstruct the sid() call for permission_id
    from database.seeds.resources.permissions import permissions
    from database.seeds.ids import sid
    perm_key = None
    for p in permissions:
        if sid(f"permission/{p['artifact']}/{p['operation']}") == pid:
            perm_key = f"permission/{p['artifact']}/{p['operation']}"
            break
    if perm_key:
        out_lines.append(f'        permission_id=sid("{perm_key}"),')
    else:
        out_lines.append(f'        permission_id="{pid}",')

    if arg_keys:
        keys_str = ", ".join(f'"{k}"' for k in arg_keys)
        out_lines.append(f'        args=[{keys_str}],')
    else:
        out_lines.append("        args=[],")
    out_lines.append("    ),")

out_lines.append("]")
out_lines.append("")

tools_path = PROJECT_ROOT / "database" / "seeds" / "tools.py"
tools_path.write_text("\n".join(out_lines))
print(f"Rewrote {len(tools)} tools with arg keys → {tools_path}")
