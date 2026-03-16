"""Organization department seed definitions."""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ORGANIZATION_DEPT = sid("org/department/organization")

# ---------------------------------------------------------------------------
# Department definitions (creates)
# ---------------------------------------------------------------------------

departments = [
    dict(
        id=ORGANIZATION_DEPT,
        name="Organization",
        description="Organization department",
    ),
]

# ---------------------------------------------------------------------------
# Department updates (applied after settings are created)
# ---------------------------------------------------------------------------


def get_department_updates():
    """Deferred import to avoid circular dependency with settings module."""
    from database.seeds.setups.organization.settings import ORGANIZATION_SETTING

    return [
        dict(
            id=ORGANIZATION_DEPT,
            settings_ids=[ORGANIZATION_SETTING],
        ),
    ]
