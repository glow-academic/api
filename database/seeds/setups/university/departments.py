"""University department seed definitions.

Each department is a dict mapping directly to CreateDepartmentItem.
Names and descriptions are CREATED as new resources.

department_updates are applied after all creates (settings must exist first).
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules for department_ids linking
# ---------------------------------------------------------------------------

UNIVERSITY_DEPT = sid("uni/department/university")

# ---------------------------------------------------------------------------
# Department definitions (creates)
# ---------------------------------------------------------------------------

departments = [
    dict(
        id=UNIVERSITY_DEPT,
        name="University",
        description="Innovative base of knowledge in the emerging field of computing.",
    ),
]

# ---------------------------------------------------------------------------
# Department updates (applied after settings are created)
# ---------------------------------------------------------------------------


def get_department_updates():
    """Deferred import to avoid circular dependency with settings module."""
    from database.seeds.setups.university.settings import UNIVERSITY_SETTING

    return [
        dict(
            id=UNIVERSITY_DEPT,
            settings_ids=[UNIVERSITY_SETTING],
        ),
    ]
