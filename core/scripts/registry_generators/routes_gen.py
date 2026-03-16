"""Generate ARTIFACT_ROUTES and ROLE_ARTIFACTS from filesystem + manual data."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.v5.registry.manual import ARTIFACT_ROLES, ROUTE_TO_ARTIFACT


def _scan_client_routes(client_dir: Path) -> list[str]:
    """Scan client/app/(main)/ for all page.tsx route paths."""
    main_dir = client_dir / "app" / "(main)"
    if not main_dir.exists():
        return []

    routes: list[str] = []
    for page_file in main_dir.rglob("page.tsx"):
        # Convert file path to route path
        rel = page_file.relative_to(main_dir).parent
        parts = [p for p in str(rel).split(os.sep) if p and p != "."]
        route = "/" + "/".join(parts) if parts else "/"
        if route != "/":
            routes.append(route)

    return sorted(routes)


def _route_to_artifact(route: str, artifacts: dict) -> str | None:
    """Map a route path to an artifact name.

    Rules (in order):
    1. Direct ROUTE_TO_ARTIFACT overrides
    2. Dynamic segment routes ([id]) → parent dir artifact
    3. /new routes → parent dir artifact
    4. Section-level routes → section artifact (if it exists)
    5. Sub-section routes → pluralized name matching
    """
    parts = [p for p in route.split("/") if p]
    if not parts:
        return None

    # Get the last meaningful segment (not a dynamic param or "new")
    meaningful_parts = [p for p in parts if not p.startswith("[") and p != "new"]
    if not meaningful_parts:
        return None

    last_meaningful = meaningful_parts[-1]

    # Check ROUTE_TO_ARTIFACT overrides
    if last_meaningful in ROUTE_TO_ARTIFACT:
        return ROUTE_TO_ARTIFACT[last_meaningful]

    # Try singular form of the last meaningful segment
    singular = (
        last_meaningful.rstrip("s")
        if last_meaningful.endswith("s")
        else last_meaningful
    )
    if singular in artifacts:
        return singular

    # Try the segment as-is
    if last_meaningful in artifacts:
        return last_meaningful

    return None


def _route_to_view_artifact(route: str, artifacts: dict) -> str | None:
    """Map routes to view artifacts for special cases.

    Handles routes like:
    - /attempt/[attemptId] → "attempt"
    - /record/[recordId] → "record"
    - /session/[sessionId] → "session"
    - /group/[groupId] → "group"
    - /test/[testId] → "test"
    - /invocation/[invocationId] → "invocation"
    - /benchmark/[testId]/[suiteId] → "invocation"
    - /home/[attemptId] → "attempt"
    - /practice/[attemptId] → "attempt"
    - /home/[attemptId]/[trainingId] → "chat"
    - /practice/[attemptId]/[trainingId] → "chat"
    - /chat/[chatId] → "chat"
    """
    parts = [p for p in route.split("/") if p]
    if not parts:
        return None

    section = parts[0]
    dynamic_count = sum(1 for p in parts if p.startswith("["))

    # Top-level section pages (no dynamic segments, no subsection)
    if len(parts) == 1 and section in artifacts:
        return section

    # Bundle sections: home, practice
    if section in ("home", "practice"):
        if dynamic_count == 2:
            return "chat"
        if dynamic_count == 1:
            return "attempt"
        if dynamic_count == 0:
            return section

    # Benchmark section
    if section == "benchmark":
        if dynamic_count == 2:
            return "invocation"
        if dynamic_count == 1:
            return "test"
        if dynamic_count == 0:
            return "benchmark"

    # Analytics section special routes
    if section == "analytics":
        if len(parts) >= 2:
            subsection = parts[1]
            if subsection == "reports" and dynamic_count == 1:
                return "record"
            if subsection == "activity" and dynamic_count == 1:
                return "session"
            if subsection == "pricing" and dynamic_count == 1:
                return "group"
            # Subsection list pages
            subsection_artifact_map = {
                "dashboard": "dashboard",
                "reports": "reports",
                "activity": "activity",
                "pricing": "pricing",
            }
            if subsection in subsection_artifact_map and dynamic_count == 0:
                return subsection_artifact_map[subsection]
        return None

    # Top-level view routes with dynamic segments
    if section in artifacts and dynamic_count > 0:
        return section

    return None


def generate_artifact_routes(
    project_root: Path,
    artifacts: dict,
) -> dict[str, list[str]]:
    """Generate ARTIFACT_ROUTES from client filesystem scanning."""
    client_dir = project_root / "client"
    routes = _scan_client_routes(client_dir)

    artifact_routes: dict[str, set[str]] = defaultdict(set)

    for route in routes:
        parts = [p for p in route.split("/") if p]
        if not parts:
            continue

        section = parts[0]
        dynamic_count = sum(1 for p in parts if p.startswith("["))
        has_new = "new" in parts

        # Try view artifact mapping first (handles special cases)
        artifact = _route_to_view_artifact(route, artifacts)

        # If no match, try CRUD artifact mapping
        if artifact is None:
            artifact = _route_to_artifact(route, artifacts)

        if artifact and artifact in artifacts:
            artifact_routes[artifact].add(route)

    return {k: sorted(v) for k, v in sorted(artifact_routes.items())}


def generate_role_artifacts(
    artifact_roles: dict[str, frozenset[str]] | None = None,
) -> dict[str, list[str]]:
    """Generate ROLE_ARTIFACTS as inverse of ARTIFACT_ROLES.

    Also includes view artifacts accessible by each role based on route_permissions.
    """
    if artifact_roles is None:
        artifact_roles = ARTIFACT_ROLES

    # Invert: artifact → roles → role → artifacts
    role_artifacts: dict[str, set[str]] = defaultdict(set)
    for artifact, roles in artifact_roles.items():
        for role in roles:
            role_artifacts[role].add(artifact)

    return {k: sorted(v) for k, v in sorted(role_artifacts.items())}
