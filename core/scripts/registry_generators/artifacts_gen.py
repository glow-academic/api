"""Generate ARTIFACTS dict from DB + filesystem scanning."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.v5.registry.manual import (
    ARTIFACTS_WITHOUT_SOCKET,
    SECTION_OVERRIDES,
    VIEW_ENDPOINT_OVERRIDES,
)

from .db import get_connection, query_rows

# Standard endpoint sets
CRUD_ENDPOINTS = frozenset(
    {"get", "list", "save", "delete", "duplicate", "draft", "docs"}
)
SOCKET_EVENTS = frozenset({"generate", "complete", "progress", "error"})

# SQL to find all *_artifact tables
ARTIFACT_TABLES_SQL = """\
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_name LIKE '%%\\_artifact'
    AND table_type = 'BASE TABLE'
ORDER BY table_name;
"""


def _scan_api_dirs(server_dir: Path) -> set[str]:
    """Scan server/app/api/v5/artifacts/ for artifact directory names."""
    artifacts_dir = server_dir / "app" / "v5" / "main"
    if not artifacts_dir.exists():
        return set()
    return {
        d.name
        for d in artifacts_dir.iterdir()
        if d.is_dir() and not d.name.startswith(("_", "."))
    }


def _scan_view_endpoints(server_dir: Path, artifact_name: str) -> frozenset[str]:
    """Scan a view artifact's __init__.py for endpoint function names."""
    init_file = server_dir / "app" / "v5" / "main" / artifact_name / "__init__.py"
    if not init_file.exists():
        return frozenset()

    endpoints: set[str] = set()
    content = init_file.read_text()
    for line in content.splitlines():
        line = line.strip()
        # Look for route decorators or function defs
        if line.startswith("async def ") or line.startswith("def "):
            # Extract function name
            func_name = line.split("(")[0].split()[-1]
            # Skip private functions
            if not func_name.startswith("_"):
                endpoints.add(func_name)

    return frozenset(endpoints)


def _scan_py_endpoints(server_dir: Path, artifact_name: str) -> frozenset[str]:
    """Scan for .py files in the artifact directory (excluding __init__.py, __pycache__)."""
    artifact_dir = server_dir / "app" / "v5" / "main" / artifact_name
    if not artifact_dir.exists():
        return frozenset()
    return frozenset(
        f.stem
        for f in artifact_dir.glob("*.py")
        if f.stem not in ("__init__", "types", "permissions")
        and not f.stem.startswith("_")
    )


def _client_section_for_artifact(client_dir: Path, artifact_name: str) -> str:
    """Determine the section for an artifact from client directory structure."""
    # Check overrides first
    if artifact_name in SECTION_OVERRIDES:
        return SECTION_OVERRIDES[artifact_name]

    main_dir = client_dir / "app" / "(main)"
    if not main_dir.exists():
        return artifact_name

    # Section mapping from client filesystem
    section_map: dict[str, str] = {}

    # Scan top-level directories
    for section_dir in main_dir.iterdir():
        if not section_dir.is_dir() or section_dir.name.startswith((".", "_")):
            continue
        section_name = section_dir.name
        # Check if this section contains the artifact as a subsection
        for sub_dir in section_dir.iterdir():
            if sub_dir.is_dir() and not sub_dir.name.startswith((".", "_", "[")):
                # Convert plural client dir to singular artifact name
                singular = (
                    sub_dir.name.rstrip("s")
                    if sub_dir.name.endswith("s")
                    else sub_dir.name
                )
                section_map[singular] = section_name
                # Also map the plural form
                section_map[sub_dir.name] = section_name

    # Check if the artifact name (or its plural) maps to a section
    if artifact_name in section_map:
        return section_map[artifact_name]

    # Check if the artifact itself IS a top-level section
    if (main_dir / artifact_name).is_dir():
        return artifact_name

    return artifact_name


def generate_artifacts(
    project_root: Path,
) -> dict[str, dict]:
    """Generate the ARTIFACTS metadata dict.

    Returns dict of artifact_name → {kind, section, endpoints, socket_events}
    """
    server_dir = project_root / "server"
    client_dir = project_root / "client"

    # 1. Get CRUD artifacts from DB (have *_artifact tables)
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = query_rows(cur, ARTIFACT_TABLES_SQL)
        cur.close()
    finally:
        conn.close()

    crud_artifacts: set[str] = set()
    for (table_name,) in rows:
        artifact_name = table_name.replace("_artifact", "")
        crud_artifacts.add(artifact_name)

    # 2. Get all API dirs (these are all artifacts)
    api_artifacts = _scan_api_dirs(server_dir)

    # 3. View artifacts = API dirs that aren't CRUD
    view_artifacts = api_artifacts - crud_artifacts

    # 4. Determine which CRUD artifacts have socket events
    # Use SAVE_REGISTRY membership minus ARTIFACTS_WITHOUT_SOCKET
    # Import lazily to avoid circular imports
    from app.v5.api.socket.internal.generation_save_registry import SAVE_REGISTRY

    socket_artifacts = set(SAVE_REGISTRY.keys()) - ARTIFACTS_WITHOUT_SOCKET

    # 5. Build the result
    artifacts: dict[str, dict] = {}

    for name in sorted(crud_artifacts):
        section = _client_section_for_artifact(client_dir, name)
        has_socket = name in socket_artifacts
        artifacts[name] = {
            "kind": "crud",
            "section": section,
            "endpoints": sorted(CRUD_ENDPOINTS),
            "socket_events": sorted(SOCKET_EVENTS) if has_socket else [],
        }

    for name in sorted(view_artifacts):
        section = _client_section_for_artifact(client_dir, name)

        # Get endpoints from overrides or scan .py files
        if name in VIEW_ENDPOINT_OVERRIDES:
            endpoints = sorted(VIEW_ENDPOINT_OVERRIDES[name])
        else:
            # Scan for .py files as endpoint names
            py_endpoints = _scan_py_endpoints(server_dir, name)
            endpoints = sorted(py_endpoints)

        artifacts[name] = {
            "kind": "view",
            "section": section,
            "endpoints": endpoints,
            "socket_events": [],
        }

    return artifacts
