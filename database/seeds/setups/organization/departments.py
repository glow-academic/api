"""Organization department seed definitions."""

from database.seeds.ids import sid
from database.seeds.setups.organization.settings import ORGANIZATION_SETTING_RESOURCE

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
        settings_ids=[ORGANIZATION_SETTING_RESOURCE],
    ),
]
