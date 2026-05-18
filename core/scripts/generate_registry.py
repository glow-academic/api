#!/usr/bin/env python3
"""Generate registry files from database introspection and filesystem scanning.

Each constant lives in its own file under server/app/registry/.

Usage:
    python server/scripts/generate_registry.py all              # Generate all registry files
    python server/scripts/generate_registry.py resource_schemas  # Generate resource_schemas.py
    python server/scripts/generate_registry.py entry_schemas     # Generate entry_schemas.py
    python server/scripts/generate_registry.py entry_view_schemas # Generate entry_view_schemas.py + entry_view_names.py
    python server/scripts/generate_registry.py artifact_flags    # Generate artifact_flags.py
    python server/scripts/generate_registry.py artifact_resources # Generate artifact_resources.py
    python server/scripts/generate_registry.py entry_resources   # Generate entry_resources.py + resource_entries.py
    python server/scripts/generate_registry.py resource_modalities # Generate resource_modalities.py
    python server/scripts/generate_registry.py artifacts         # Generate artifacts.py
    python server/scripts/generate_registry.py artifact_routes   # Generate artifact_routes.py
    python server/scripts/generate_registry.py role_artifacts    # Generate role_artifacts.py
    python server/scripts/generate_registry.py validate          # Validate generated vs current
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

# Ensure server/ is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))

from scripts.registry_generators.formatter import (
    format_dict_of_dicts,
    format_dict_of_frozensets,
    format_dict_of_strings,
    write_registry_file,
)

REGISTRY_DIR = SERVER_DIR / "app" / "registry"


# ---------------------------------------------------------------------------
# Individual generators — each returns (filename, content) pairs
# ---------------------------------------------------------------------------


def gen_resource_schemas() -> list[tuple[str, str]]:
    """Generate resource_schemas.py."""
    from scripts.registry_generators.resources_gen import generate_resource_schemas

    schemas = generate_resource_schemas()

    content = "\n".join(
        [
            '"""Per-resource-type column schemas.',
            "",
            "Business columns only — excludes system columns (id, created_at, active, generated, mcp)",
            "that are present on every resource table.",
            "",
            "Type strings: text, int, float, numeric, bool, uuid, array, enum, timestamp",
            '"""',
            "",
            format_dict_of_dicts(
                "RESOURCE_SCHEMAS",
                "dict[str, dict[str, str]]",
                schemas,
            ),
        ]
    )
    return [("resource_schemas.py", content)]


def gen_resource_output_schemas() -> list[tuple[str, str]]:
    """Generate resource_output_schemas.py (re-export from manual.py)."""
    content = "\n".join(
        [
            '"""Resource output schemas — curated tool output contracts.',
            "",
            "Simplified types (string/number/boolean) for the tool-facing output contract.",
            "Not derivable from DB schema — hand-maintained in manual.py.",
            '"""',
            "",
            "from app.v5.registry.manual import RESOURCE_OUTPUT_SCHEMAS as RESOURCE_OUTPUT_SCHEMAS",
        ]
    )
    return [("resource_output_schemas.py", content)]


def gen_entry_schemas() -> list[tuple[str, str]]:
    """Generate entry_schemas.py."""
    from scripts.registry_generators.entries_gen import generate_entry_schemas

    schemas = generate_entry_schemas()

    content = "\n".join(
        [
            '"""Per-entry-type column schemas for tool-targetable entries.',
            "",
            "Only includes entry types reachable via entry_tools_relation or tool_bindings_junction.",
            "Business columns only — excludes system columns (id, created_at, active, generated, mcp).",
            "",
            "Entry type keys match the entry_type enum values (unprefixed).",
            "For highlights/replacements, columns come from the standalone tables (not attempt_* variants).",
            "",
            "Type strings: text, int, float, numeric, bool, uuid, array, enum, timestamp",
            '"""',
            "",
            format_dict_of_dicts(
                "ENTRY_SCHEMAS",
                "dict[str, dict[str, str]]",
                schemas,
            ),
        ]
    )
    return [("entry_schemas.py", content)]


def gen_entry_view_schemas() -> list[tuple[str, str]]:
    """Generate entry_view_schemas.py and entry_view_names.py."""
    from scripts.registry_generators.entry_views_gen import generate_entry_view_schemas

    schemas, names = generate_entry_view_schemas()

    # entry_view_schemas.py
    parts = [
        '"""Per-entry-type materialized view schemas.',
        "",
        "Each tool-targetable entry type has a corresponding MV that consumers read from.",
        "These schemas represent the SELECT columns of each MV — distinct from ENTRY_SCHEMAS",
        "which represent the table columns tools write to.",
        "",
        "Differences from ENTRY_SCHEMAS:",
        "- IDs renamed: entry.id → {type}_id (e.g. analysis_id, content_id)",
        "- Joined columns added (e.g. standard_id on feedbacks, question_id/option_id on responses)",
        "- Computed columns (e.g. idx via ROW_NUMBER on contents/hints)",
        "- Type casts (e.g. total::float on feedbacks, score::float on grades)",
        "- Internal columns dropped (e.g. call_id, updated_at filtered out by most MVs)",
        "",
        "MV name mapping:",
    ]
    for entry_key in sorted(names.keys()):
        mv_name = names[entry_key]
        parts.append(f"  {entry_key:14s} → {mv_name}")
    parts.extend(
        [
            "",
            "Type strings: text, int, float, numeric, bool, uuid, array, enum, timestamp",
            '"""',
            "",
            format_dict_of_dicts(
                "ENTRY_VIEW_SCHEMAS",
                "dict[str, dict[str, str]]",
                schemas,
            ),
        ]
    )
    schemas_content = "\n".join(parts)

    # entry_view_names.py
    names_content = "\n".join(
        [
            '"""Entry type → materialized view name mapping."""',
            "",
            format_dict_of_strings(
                "ENTRY_VIEW_NAMES",
                "dict[str, str]",
                names,
            ),
        ]
    )

    return [
        ("entry_view_schemas.py", schemas_content),
        ("entry_view_names.py", names_content),
    ]


def gen_artifact_flags() -> list[tuple[str, str]]:
    """Generate artifact_flags.py from DB."""
    from scripts.registry_generators.artifact_flags_gen import generate_artifact_flags

    flags = generate_artifact_flags()

    content = "\n".join(
        [
            '"""artifact_flags_relation (artifact_type → flag_type)."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "ARTIFACT_FLAGS",
                "dict[str, frozenset[str]]",
                flags,
                comment="artifact_flags_relation (artifact_type → flag_type)",
            ),
        ]
    )
    return [("artifact_flags.py", content)]


def gen_artifact_resources() -> list[tuple[str, str]]:
    """Generate artifact_resources.py from DB FK introspection."""
    from scripts.registry_generators.db import get_connection, group_by_key, query_rows
    from scripts.registry_generators.relations_gen import ARTIFACT_RESOURCES_SQL

    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = query_rows(cur, ARTIFACT_RESOURCES_SQL)
        grouped = group_by_key(rows)
        cur.close()
    finally:
        conn.close()

    content = "\n".join(
        [
            '"""artifact_resources_relation (artifact_type → resource_type)."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "ARTIFACT_RESOURCES",
                "dict[str, frozenset[str]]",
                grouped,
            ),
        ]
    )
    return [("artifact_resources.py", content)]


def gen_entry_resources() -> list[tuple[str, str]]:
    """Generate entry_resources.py and resource_entries.py from DB FK introspection."""
    from scripts.registry_generators.db import (
        get_connection,
        group_by_key,
        invert_map,
        query_rows,
    )
    from scripts.registry_generators.relations_gen import ENTRY_RESOURCES_SQL

    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = query_rows(cur, ENTRY_RESOURCES_SQL)
        er_grouped = group_by_key(rows)
        re_grouped = invert_map(er_grouped)
        cur.close()
    finally:
        conn.close()

    er_content = "\n".join(
        [
            '"""entry_resource_relation (entry_type → resource_type)."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "ENTRY_RESOURCES",
                "dict[str, frozenset[str]]",
                er_grouped,
            ),
        ]
    )

    re_content = "\n".join(
        [
            '"""resource_entry_relation (resource_type → entry_type)."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "RESOURCE_ENTRIES",
                "dict[str, frozenset[str]]",
                re_grouped,
            ),
        ]
    )

    return [
        ("entry_resources.py", er_content),
        ("resource_entries.py", re_content),
    ]


def gen_resource_modalities() -> list[tuple[str, str]]:
    """Generate resource_modalities.py from convention + exceptions."""
    from scripts.registry_generators.resource_modalities_gen import (
        generate_resource_modalities,
    )

    # Read current file to determine which resources have modalities
    from app.v5.registry.modalities import RESOURCE_MODALITIES as current

    modalities = generate_resource_modalities(sorted({k for _, k in current.keys()}))

    content = "\n".join(
        [
            '"""resource_modalities_relation (resource_type → modality_type)."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "RESOURCE_MODALITIES",
                "dict[str, frozenset[str]]",
                modalities,
            ),
        ]
    )
    return [("resource_modalities.py", content)]


def gen_artifact_roles() -> list[tuple[str, str]]:
    """Generate artifact_roles.py (re-export from manual.py)."""
    content = "\n".join(
        [
            '"""artifact_roles_relation (artifact_type → profile_type).',
            "",
            "Not derivable from DB — pure business logic, maintained in manual.py.",
            '"""',
            "",
            "from app.v5.registry.manual import ARTIFACT_ROLES as ARTIFACT_ROLES",
        ]
    )
    return [("artifact_roles.py", content)]


def gen_artifact_views() -> list[tuple[str, str]]:
    """Generate artifact_views.py (re-export from manual.py)."""
    content = "\n".join(
        [
            '"""artifact_view_relation (artifact_type → view_type).',
            "",
            "Not derivable — maintained in manual.py.",
            '"""',
            "",
            "from app.v5.registry.manual import ARTIFACT_VIEWS as ARTIFACT_VIEWS",
        ]
    )
    return [("artifact_views.py", content)]


def gen_view_entries() -> list[tuple[str, str]]:
    """Generate view_entries.py (re-export from manual.py)."""
    content = "\n".join(
        [
            '"""view_entry_relation (view_type → entry_type).',
            "",
            "Not derivable — maintained in manual.py.",
            '"""',
            "",
            "from app.v5.registry.manual import VIEW_ENTRIES as VIEW_ENTRIES",
        ]
    )
    return [("view_entries.py", content)]


def gen_view_resources() -> list[tuple[str, str]]:
    """Generate view_resources.py (re-export from manual.py)."""
    content = "\n".join(
        [
            '"""view_resource_relation (view_type → resource_type).',
            "",
            "Not derivable — maintained in manual.py.",
            '"""',
            "",
            "from app.v5.registry.manual import VIEW_RESOURCES as VIEW_RESOURCES",
        ]
    )
    return [("view_resources.py", content)]


def gen_artifact_entries() -> list[tuple[str, str]]:
    """Generate artifact_entries.py (computed from ARTIFACT_VIEWS × VIEW_ENTRIES)."""
    content = "\n".join(
        [
            '"""artifact_entry_relation (artifact_type → entry_types).',
            "",
            "Computed from ARTIFACT_VIEWS × VIEW_ENTRIES.",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "from app.v5.registry.artifact_views import ARTIFACT_VIEWS",
            "from app.v5.registry.view_entries import VIEW_ENTRIES",
            "",
            "ARTIFACT_ENTRIES: dict[str, list[str]] = {}",
            "for _art, _views in ARTIFACT_VIEWS.items():",
            "    _ents: set[str] = set()",
            "    for _v in _views:",
            "        if _v in VIEW_ENTRIES:",
            "            _ents.update(VIEW_ENTRIES[_v])",
            "    if _ents:",
            "        ARTIFACT_ENTRIES[_art] = sorted(_ents)",
        ]
    )
    return [("artifact_entries.py", content)]


def gen_artifacts() -> list[tuple[str, str]]:
    """Generate artifacts.py."""
    from scripts.registry_generators.artifacts_gen import generate_artifacts

    artifacts = generate_artifacts(PROJECT_ROOT)

    # Split into CRUD and VIEW
    crud_items: dict[str, dict] = {}
    view_items: dict[str, dict] = {}
    for name, meta in sorted(artifacts.items()):
        if meta["kind"] == "crud":
            crud_items[name] = meta
        else:
            view_items[name] = meta

    parts = [
        '"""',
        "Per-artifact metadata — kind, section, endpoints, socket events.",
        "",
        "Data sources:",
        "- CRUD vs view: server/app/api/v5/router.py (lines 105-138)",
        "- Socket handlers: server/app/v5/socket/__init__.py",
        "- Per-artifact endpoints: each server/app/api/v5/artifacts/{artifact}/__init__.py",
        "- Section mapping: derived from ARTIFACT_ROUTES route prefixes",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from enum import Enum",
        "",
        "",
        "class ArtifactKind(str, Enum):",
        '    crud = "crud"',
        '    view = "view"',
        "",
        "",
        "class ArtifactMeta:",
        '    __slots__ = ("kind", "section", "endpoints", "socket_events")',
        "",
        "    def __init__(",
        "        self,",
        "        kind: ArtifactKind,",
        "        section: str,",
        "        endpoints: frozenset[str],",
        "        socket_events: frozenset[str] = frozenset(),",
        "    ) -> None:",
        "        self.kind = kind",
        "        self.section = section",
        "        self.endpoints = endpoints",
        "        self.socket_events = socket_events",
        "",
        "    def __repr__(self) -> str:",
        "        return (",
        '            f"ArtifactMeta(kind={self.kind.value!r}, section={self.section!r}, "',
        '            f"endpoints={sorted(self.endpoints)}, socket_events={sorted(self.socket_events)})"',
        "        )",
        "",
        "",
        "# Standard endpoint sets",
        "_CRUD_ENDPOINTS = frozenset(",
        '    {"get", "list", "save", "delete", "duplicate", "draft", "docs"}',
        ")",
        '_SOCKET_EVENTS = frozenset({"generate", "complete", "progress", "error"})',
        "",
        "# ---------------------------------------------------------------------------",
        f"# {len(crud_items)} CRUD artifacts",
        "# ---------------------------------------------------------------------------",
        "_CRUD: dict[str, tuple[str, bool]] = {",
        "    # (section, has_socket)",
    ]

    for name, meta in sorted(crud_items.items()):
        has_socket = len(meta["socket_events"]) > 0
        parts.append(f'    "{name}": ("{meta["section"]}", {has_socket}),')

    parts.extend(
        [
            "}",
            "",
            "# ---------------------------------------------------------------------------",
            f"# {len(view_items)} view artifacts (endpoints derived from each __init__.py)",
            "# ---------------------------------------------------------------------------",
            "_VIEWS: dict[str, tuple[str, frozenset[str]]] = {",
            "    # (section, endpoints)",
        ]
    )

    for name, meta in sorted(view_items.items()):
        endpoints = meta["endpoints"]
        if not endpoints:
            parts.append(f'    "{name}": ("{meta["section"]}", frozenset()),')
        elif len(endpoints) <= 3:
            items = ", ".join(f'"{e}"' for e in sorted(endpoints))
            parts.append(
                f'    "{name}": ("{meta["section"]}", frozenset({{{items}}})),'
            )
        else:
            parts.append(f'    "{name}": (')
            parts.append(f'        "{meta["section"]}",')
            parts.append("        frozenset(")
            items = ", ".join(f'"{e}"' for e in sorted(endpoints))
            parts.append(f"            {{{items}}}")
            parts.append("        ),")
            parts.append("    ),")

    parts.extend(
        [
            "}",
            "",
            "# ---------------------------------------------------------------------------",
            "# Combined registry",
            "# ---------------------------------------------------------------------------",
            "ARTIFACTS: dict[str, ArtifactMeta] = {}",
            "",
            "for _name, (_section, _has_socket) in _CRUD.items():",
            "    ARTIFACTS[_name] = ArtifactMeta(",
            "        kind=ArtifactKind.crud,",
            "        section=_section,",
            "        endpoints=_CRUD_ENDPOINTS,",
            "        socket_events=_SOCKET_EVENTS if _has_socket else frozenset(),",
            "    )",
            "",
            "for _name, (_section, _endpoints) in _VIEWS.items():",
            "    ARTIFACTS[_name] = ArtifactMeta(",
            "        kind=ArtifactKind.view,",
            "        section=_section,",
            "        endpoints=_endpoints,",
            "    )",
            "",
            "# Clean up module namespace",
            "del _name, _section, _has_socket, _endpoints, _CRUD, _VIEWS",
        ]
    )

    return [("artifacts.py", "\n".join(parts))]


def gen_artifact_routes() -> list[tuple[str, str]]:
    """Generate artifact_routes.py from filesystem scanning."""
    from scripts.registry_generators.routes_gen import generate_artifact_routes

    from app.v5.registry.artifacts import ARTIFACTS

    artifact_routes = generate_artifact_routes(PROJECT_ROOT, ARTIFACTS)

    content = "\n".join(
        [
            '"""artifact → route paths it unlocks."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "ARTIFACT_ROUTES",
                "dict[str, frozenset[str]]",
                artifact_routes,
            ),
        ]
    )
    return [("artifact_routes.py", content)]


def gen_role_artifacts() -> list[tuple[str, str]]:
    """Generate role_artifacts.py from ROUTE_PERMISSIONS."""
    from scripts.registry_generators.role_artifacts_gen import generate_role_artifacts

    role_artifacts = generate_role_artifacts()

    content = "\n".join(
        [
            '"""role → artifacts accessible to that role."""',
            "",
            "from __future__ import annotations",
            "",
            format_dict_of_frozensets(
                "ROLE_ARTIFACTS",
                "dict[str, frozenset[str]]",
                role_artifacts,
            ),
        ]
    )
    return [("role_artifacts.py", content)]


# ---------------------------------------------------------------------------
# All generators registry
# ---------------------------------------------------------------------------

# Each generator returns a list of (filename, content) pairs.
# Some generators produce multiple files (e.g. entry_view_schemas → 2 files).
FILE_GENERATORS: dict[str, callable] = {
    "resource_schemas": gen_resource_schemas,
    "resource_output_schemas": gen_resource_output_schemas,
    "entry_schemas": gen_entry_schemas,
    "entry_view_schemas": gen_entry_view_schemas,
    "artifact_flags": gen_artifact_flags,
    "artifact_resources": gen_artifact_resources,
    "entry_resources": gen_entry_resources,
    "resource_modalities": gen_resource_modalities,
    "artifact_roles": gen_artifact_roles,
    "artifact_views": gen_artifact_views,
    "view_entries": gen_view_entries,
    "view_resources": gen_view_resources,
    "artifact_entries": gen_artifact_entries,
    "artifacts": gen_artifacts,
    "artifact_routes": gen_artifact_routes,
    "role_artifacts": gen_role_artifacts,
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate() -> bool:
    """Compare generated output against current files. Returns True if all match."""
    all_match = True
    for name, gen_func in FILE_GENERATORS.items():
        try:
            file_pairs = gen_func()
        except Exception as e:
            print(f"ERROR generating {name}: {e}")
            all_match = False
            continue

        for filename, generated in file_pairs:
            filepath = REGISTRY_DIR / filename
            if not filepath.exists():
                print(f"MISSING: {filename}")
                all_match = False
                continue

            current = filepath.read_text()

            # Normalize whitespace for comparison (ruff may format differently)
            current_lines = current.strip().splitlines()
            generated_lines = generated.strip().splitlines()

            if current_lines != generated_lines:
                print(f"DIFF: {filename}")
                diff = difflib.unified_diff(
                    current_lines,
                    generated_lines,
                    fromfile=f"current/{filename}",
                    tofile=f"generated/{filename}",
                    lineterm="",
                )
                for line in list(diff)[:50]:
                    print(f"  {line}")
                all_match = False
            else:
                print(f"OK: {filename}")

    return all_match


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "validate":
        ok = validate()
        sys.exit(0 if ok else 1)
    elif command == "all":
        for name, gen_func in FILE_GENERATORS.items():
            print(f"Generating {name}...")
            try:
                file_pairs = gen_func()
                for filename, content in file_pairs:
                    write_registry_file(REGISTRY_DIR / filename, content)
                    print(f"  → {filename} written")
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback

                traceback.print_exc()
    elif command in FILE_GENERATORS:
        gen_func = FILE_GENERATORS[command]
        print(f"Generating {command}...")
        file_pairs = gen_func()
        for filename, content in file_pairs:
            write_registry_file(REGISTRY_DIR / filename, content)
            print(f"  → {filename} written")
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
