"""Auto-discover infra operations from the filesystem.

Scans app/infra/{artifact}/{operation}.py for async def *_impl functions
and builds the INFRA_OPS registry automatically. Files with multiple _impl
functions are skipped (those are workflow/internal files).

Convention:
  File:     app/infra/{artifact}/{operation}.py
  Function: {operation}_{artifact}_impl  (or create_{artifact}_impl, etc.)
  Registry: ("artifact", "operation") -> ("app.infra.artifact.operation", "fn_name")

Non-canonical entries (cross-artifact refs, aliases) are handled via an
explicit INFRA_OPS_OVERRIDES dict that takes precedence over auto-discovery.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Directories to skip — internal utilities, not artifact operations
_SKIP_DIRS = {
    "common_context",
    "events",
    "helpers",
    "identity",
    "ledger",
    "search",
    "tools",
    "types",
    "websocket",
}

# Files to skip — internal helpers, not operations
_SKIP_FILES = {
    "context",  # separate from page_context — has resolve_*_context functions
    "permissions",
    "permissions_context",
    "sections",
    "types",
    "mode",
    "department",
    "workflows",
}

_IMPL_RE = re.compile(r"^async def (\w+_impl)\(", re.MULTILINE)


def discover_infra_ops(
    base_path: str | Path = "app/infra",
) -> dict[tuple[str, str], tuple[str, str]]:
    """Scan app/infra/ for *_impl functions and build the ops registry.

    Returns:
        Dict mapping (artifact, operation) to (module_path, function_name).
        Files with multiple _impl functions are skipped.
    """
    base = Path(base_path)
    if not base.exists():
        logger.warning("discover_infra_ops: %s does not exist", base)
        return {}

    ops: dict[tuple[str, str], tuple[str, str]] = {}

    for artifact_dir in sorted(base.iterdir()):
        if not artifact_dir.is_dir():
            continue
        if artifact_dir.name.startswith("_") or artifact_dir.name in _SKIP_DIRS:
            continue

        artifact = artifact_dir.name

        for py_file in sorted(artifact_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            operation = py_file.stem
            if operation in _SKIP_FILES:
                continue

            source = py_file.read_text()
            fns = _IMPL_RE.findall(source)

            if len(fns) != 1:
                # Skip files with 0 or multiple _impl functions
                continue

            fn_name = fns[0]
            module_path = f"app.infra.{artifact}.{operation}"
            ops[(artifact, operation)] = (module_path, fn_name)

    return ops


_ITEM_RE = re.compile(r"^class ((?:Create|Update)\w+Item)\(", re.MULTILINE)


def discover_infra_item_types(
    base_path: str | Path = "app/infra",
) -> dict[tuple[str, str], tuple[str, str]]:
    """Scan app/infra/{artifact}/types.py for Create/Update Item classes.

    Convention:
      - CreateFooItem in app/infra/foo/types.py → ("foo", "create")
      - UpdateFooItem in app/infra/foo/types.py → ("foo", "update")

    Returns:
        Dict mapping (artifact, operation) to (module_path, class_name).
    """
    base = Path(base_path)
    if not base.exists():
        return {}

    items: dict[tuple[str, str], tuple[str, str]] = {}

    for types_file in sorted(base.glob("*/types.py")):
        artifact = types_file.parent.name
        if artifact.startswith("_") or artifact in _SKIP_DIRS:
            continue

        source = types_file.read_text()
        for match in _ITEM_RE.finditer(source):
            cls_name = match.group(1)
            op = "create" if cls_name.startswith("Create") else "update"
            module_path = f"app.infra.{artifact}.types"
            items[(artifact, op)] = (module_path, cls_name)

    return items


def validate_tool_registrations(
    tool_defs: list[dict],
    infra_ops: dict[tuple[str, str], tuple[str, str] | None],
) -> list[str]:
    """Check that every tool with static routing has a matching INFRA_OPS entry.

    Returns list of warning messages for tools missing registrations.
    """
    missing: list[str] = []

    for td in tool_defs:
        args_outputs = td.get("_args_outputs", [])
        tool_name = td.get("name", "unknown")

        artifact = None
        operation = None
        for ao in args_outputs:
            name = ao.get("name")
            template = ao.get("template", "")
            if name == "artifact" and not template.startswith("{"):
                artifact = template.strip()
            elif name == "operation" and not template.startswith("{"):
                operation = template.strip()

        if artifact and operation:
            key = (artifact, operation)
            if key not in infra_ops:
                missing.append(
                    f"Tool '{tool_name}': ({artifact}, {operation}) not in INFRA_OPS"
                )
            elif infra_ops[key] is None:
                missing.append(
                    f"Tool '{tool_name}': ({artifact}, {operation}) is None (stub)"
                )

    return missing
