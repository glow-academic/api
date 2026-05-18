"""Transform tools.py to replace operation_id + artifact_id with permission_id.

Reads the current tools.py, builds reverse maps from artifact/operation UUIDs
to their string names, then rewrites each tool entry to use:
    permission_id=sid(f"permission/{artifact}/{operation}")
instead of the old operation_id=UUID(...) + artifact_id=UUID(...) pair.

Usage:
    python database/scripts/fix_tools_permissions.py
"""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Build UUID → name maps from the seed files
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent

# Parse artifacts.py
artifact_by_uuid: dict[str, str] = {}
artifacts_path = ROOT / "database" / "seeds" / "resources" / "artifacts.py"
for match in re.finditer(
    r'id=UUID\("([^"]+)"\),\s*artifact="([^"]+)"', artifacts_path.read_text()
):
    artifact_by_uuid[match.group(1)] = match.group(2)

# Parse operations.py
operation_by_uuid: dict[str, str] = {}
operations_path = ROOT / "database" / "seeds" / "resources" / "operations.py"
for match in re.finditer(
    r'id=UUID\("([^"]+)"\),\s*operation="([^"]+)"', operations_path.read_text()
):
    operation_by_uuid[match.group(1)] = match.group(2)

print(f"Loaded {len(artifact_by_uuid)} artifacts, {len(operation_by_uuid)} operations")

# ---------------------------------------------------------------------------
# Read and transform tools.py
# ---------------------------------------------------------------------------

tools_path = ROOT / "database" / "seeds" / "tools.py"
text = tools_path.read_text()

# Replace the import line
text = text.replace(
    "from uuid import UUID",
    "from uuid import UUID\n\nfrom database.seeds.ids import sid",
)

# Strategy: find each occurrence of the operation_id + artifact_id pair
# and replace with a single permission_id line.
#
# Patterns in the file look like:
#     operation_id=UUID("..."),
#     artifact_id=UUID("..."),
# OR (on consecutive lines with varying whitespace)

# We'll use a regex that matches both lines together (they always appear
# consecutively: operation_id first, then artifact_id on the next line).

pattern = re.compile(
    r'(?P<indent>\s+)operation_id=UUID\("(?P<op_uuid>[^"]+)"\),\n'
    r'\s+artifact_id=UUID\("(?P<art_uuid>[^"]+)"\),'
)

replacements = 0
missing = []


def replacer(m: re.Match) -> str:
    global replacements
    indent = m.group("indent")
    op_uuid = m.group("op_uuid")
    art_uuid = m.group("art_uuid")

    op_name = operation_by_uuid.get(op_uuid)
    art_name = artifact_by_uuid.get(art_uuid)

    if op_name is None or art_name is None:
        missing.append((op_uuid, art_uuid))
        # Leave unchanged if we can't resolve
        return m.group(0)

    replacements += 1
    return f'{indent}permission_id=sid("permission/{art_name}/{op_name}"),'


text = pattern.sub(replacer, text)

if missing:
    print(f"WARNING: {len(missing)} tools could not be resolved:")
    for op_uuid, art_uuid in missing:
        print(f"  operation={op_uuid} artifact={art_uuid}")

print(f"Replaced {replacements} tool entries")

# ---------------------------------------------------------------------------
# Write the result
# ---------------------------------------------------------------------------

tools_path.write_text(text)
print(f"Written to {tools_path}")
