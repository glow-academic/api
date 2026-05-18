"""Organization department seed definitions."""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ORGANIZATION_DEPT = sid("org/department/organization")
ORGANIZATION_DEPT_RESOURCE = sid("org/department-resource/organization")

# ---------------------------------------------------------------------------
# Department definitions (creates)
# ---------------------------------------------------------------------------

departments = [
    dict(
        id=ORGANIZATION_DEPT,
        resource_id=ORGANIZATION_DEPT_RESOURCE,
        name="Organization",
        description="Organization department",
        settings_ids=[sid("org/setting-resource/organization")],
    ),
]
