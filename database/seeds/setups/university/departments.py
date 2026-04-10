"""University department seed definitions.

Each department is a dict mapping directly to CreateDepartmentItem.
Names and descriptions are CREATED as new resources.

settings_ids uses a forward-reference to the setting resource ID (no FK constraint
on department_settings_junction, so the setting doesn't need to exist yet).
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules for department_ids linking
# ---------------------------------------------------------------------------

UNIVERSITY_DEPT = sid("uni/department/university")
UNIVERSITY_DEPT_RESOURCE = sid("uni/department-resource/university")

# ---------------------------------------------------------------------------
# Department definitions (creates)
# ---------------------------------------------------------------------------

departments = [
    dict(
        id=UNIVERSITY_DEPT,
        resource_id=UNIVERSITY_DEPT_RESOURCE,
        name="University",
        description="Innovative base of knowledge in the emerging field of computing.",
        settings_ids=[sid("uni/setting-resource/university")],
        is_primary=True,
    ),
]
