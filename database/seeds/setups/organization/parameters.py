"""Organization parameter seed definitions.

3 parameters referencing the 13 fields:
  - Employee Level (4 fields)
  - Years with Company (5 fields)
  - Job Position (4 fields)
"""

from database.seeds.ids import sid
from database.seeds.setups.organization.departments import ORGANIZATION_DEPT
from database.seeds.setups.organization.fields import (
    EMPLOYEE_LEVEL_FIELDS,
    JOB_POSITION_FIELDS,
    YEARS_FIELDS,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

P_EMPLOYEE_LEVEL = sid("org/parameter/employee-level")
P_YEARS_WITH_COMPANY = sid("org/parameter/years-with-company")
P_JOB_POSITION = sid("org/parameter/job-position")

# ---------------------------------------------------------------------------
# Parameter definitions
# ---------------------------------------------------------------------------

parameters = [
    dict(
        id=P_EMPLOYEE_LEVEL,
        name="Employee Level",
        description="Employee seniority level",
        field_ids=EMPLOYEE_LEVEL_FIELDS,
        department_ids=[ORGANIZATION_DEPT],
    ),
    dict(
        id=P_YEARS_WITH_COMPANY,
        name="Years with Company",
        description="Tenure at the company",
        field_ids=YEARS_FIELDS,
        department_ids=[ORGANIZATION_DEPT],
    ),
    dict(
        id=P_JOB_POSITION,
        name="Job Position",
        description="Job role/position",
        field_ids=JOB_POSITION_FIELDS,
        department_ids=[ORGANIZATION_DEPT],
    ),
]
