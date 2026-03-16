"""Generate ROLE_ARTIFACTS from ROUTE_PERMISSIONS in route_permissions.py."""

from __future__ import annotations

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.v5.api.auth.route_permissions import ROUTE_PERMISSIONS


def generate_role_artifacts() -> dict[str, list[str]]:
    """Build role → frozenset[artifacts] from ROUTE_PERMISSIONS.

    For each SectionPermission → each RoutePermission, collect route.artifact per route.roles.
    """
    role_artifacts: dict[str, set[str]] = defaultdict(set)

    for section in ROUTE_PERMISSIONS:
        for route in section.routes:
            artifact = route.artifact
            if not artifact:
                continue
            for role in route.roles:
                role_artifacts[role].add(artifact)

    return {k: sorted(v) for k, v in sorted(role_artifacts.items())}
