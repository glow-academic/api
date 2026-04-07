"""Organization field seed definitions.

13 fields organized into 3 parameter groups:
  - Employee Level (4): Junior, Mid-Level, Senior, Executive
  - Years with Company (5): <1, 1-3, 3-5, 5-10, 10+
  - Job Position (4): Engineer, Designer, Analyst, Manager
"""

from database.seeds.ids import sid
from database.seeds.setups.organization.departments import ORGANIZATION_DEPT, ORGANIZATION_DEPT_RESOURCE

# ---------------------------------------------------------------------------
# Deterministic IDs — Employee Level
# ---------------------------------------------------------------------------

F_JUNIOR = sid("org/field/junior")
F_MID_LEVEL = sid("org/field/mid-level")
F_SENIOR = sid("org/field/senior")
F_EXECUTIVE = sid("org/field/executive")

EMPLOYEE_LEVEL_FIELDS = [F_JUNIOR, F_MID_LEVEL, F_SENIOR, F_EXECUTIVE]

# ---------------------------------------------------------------------------
# Deterministic IDs — Years with Company
# ---------------------------------------------------------------------------

F_LESS_THAN_1 = sid("org/field/less-than-1-year")
F_1_3_YEARS = sid("org/field/1-3-years")
F_3_5_YEARS = sid("org/field/3-5-years")
F_5_10_YEARS = sid("org/field/5-10-years")
F_10_PLUS = sid("org/field/10-plus-years")

YEARS_FIELDS = [F_LESS_THAN_1, F_1_3_YEARS, F_3_5_YEARS, F_5_10_YEARS, F_10_PLUS]

# ---------------------------------------------------------------------------
# Deterministic IDs — Job Position
# ---------------------------------------------------------------------------

F_ENGINEER = sid("org/field/engineer")
F_DESIGNER = sid("org/field/designer")
F_ANALYST = sid("org/field/analyst")
F_MANAGER_POS = sid("org/field/manager-position")

JOB_POSITION_FIELDS = [F_ENGINEER, F_DESIGNER, F_ANALYST, F_MANAGER_POS]

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

fields = [
    # Employee Level
    dict(
        id=F_JUNIOR,
        resource_id=sid("org/field-resource/junior"),
        name="Junior",
        description="Junior employee level",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_MID_LEVEL,
        resource_id=sid("org/field-resource/mid-level"),
        name="Mid-Level",
        description="Mid-level employee level",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_SENIOR,
        resource_id=sid("org/field-resource/senior"),
        name="Senior",
        description="Senior employee level",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_EXECUTIVE,
        resource_id=sid("org/field-resource/executive"),
        name="Executive",
        description="Executive employee level",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    # Years with Company
    dict(
        id=F_LESS_THAN_1,
        resource_id=sid("org/field-resource/less-than-1-year"),
        name="Less than 1 year",
        description="Less than 1 year tenure",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_1_3_YEARS,
        resource_id=sid("org/field-resource/1-3-years"),
        name="1-3 years",
        description="1-3 years tenure",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_3_5_YEARS,
        resource_id=sid("org/field-resource/3-5-years"),
        name="3-5 years",
        description="3-5 years tenure",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_5_10_YEARS,
        resource_id=sid("org/field-resource/5-10-years"),
        name="5-10 years",
        description="5-10 years tenure",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_10_PLUS,
        resource_id=sid("org/field-resource/10-plus-years"),
        name="10+ years",
        description="10+ years tenure",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    # Job Position
    dict(
        id=F_ENGINEER,
        resource_id=sid("org/field-resource/engineer"),
        name="Engineer",
        description="Engineer position",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_DESIGNER,
        resource_id=sid("org/field-resource/designer"),
        name="Designer",
        description="Designer position",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_ANALYST,
        resource_id=sid("org/field-resource/analyst"),
        name="Analyst",
        description="Analyst position",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=F_MANAGER_POS,
        resource_id=sid("org/field-resource/manager-position"),
        name="Manager",
        description="Manager position",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
]
