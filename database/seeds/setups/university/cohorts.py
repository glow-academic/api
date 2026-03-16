"""University cohort seed definitions.

Each cohort is a dict mapping directly to CreateCohortItem.
Simulation references use deterministic IDs imported from simulations.py.

Names and descriptions are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT
from database.seeds.setups.university.profiles import (
    PROFESSOR_SMITH,
    TA_JOHNSON,
    UNIVERSITY_ADMIN,
)
from database.seeds.setups.university.simulations import (
    ACADEMIC_INTEGRITY_TRAINING,
    AGGRESSIVE_PRACTICE,
    CONFUSED_PRACTICE,
    FERPA_TRAINING,
    GENERAL_PRACTICE,
    HAPPY_PRACTICE,
    PASSIVE_PRACTICE,
    UPSET_STUDENT_TRAINING,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

PRACTICE_COHORT = sid("uni/cohort/practice")
TRAINING_COHORT = sid("uni/cohort/training")

# ---------------------------------------------------------------------------
# Cohort definitions
# ---------------------------------------------------------------------------

cohorts = [
    dict(
        id=PRACTICE_COHORT,
        name="Practice Cohort",
        description="Open practice cohort with all practice simulations available.",
        simulation_ids=[
            CONFUSED_PRACTICE,
            HAPPY_PRACTICE,
            PASSIVE_PRACTICE,
            AGGRESSIVE_PRACTICE,
            GENERAL_PRACTICE,
        ],
        profile_ids=[PROFESSOR_SMITH, TA_JOHNSON],
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=TRAINING_COHORT,
        name="Training Cohort",
        description="Training cohort with structured training simulations.",
        simulation_ids=[
            ACADEMIC_INTEGRITY_TRAINING,
            FERPA_TRAINING,
            UPSET_STUDENT_TRAINING,
        ],
        profile_ids=[UNIVERSITY_ADMIN, PROFESSOR_SMITH, TA_JOHNSON],
        department_ids=[UNIVERSITY_DEPT],
    ),
]
