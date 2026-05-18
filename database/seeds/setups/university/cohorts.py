"""University cohort seed definitions.

Each cohort is a dict mapping directly to CreateCohortItem.
Simulation references use deterministic IDs imported from simulations.py.

Names and descriptions are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT_RESOURCE
from database.seeds.setups.university.profile_personas import (
    ALL_PROFILE_PERSONA_IDS,
    PP_ADMIN,
    PP_INSTRUCTIONAL,
    PP_MEMBER,
    PP_PROFESSOR_SMITH,
    PP_SUPERADMIN,
    PP_TA_JOHNSON,
    PP_UNIVERSITY_ADMIN,
)
from database.seeds.setups.university.profiles import (
    BENCHMARK_PROFILE_RESOURCE,
    PROFESSOR_SMITH_RESOURCE,
    TA_JOHNSON_RESOURCE,
    UNI_ADMIN_RESOURCE,
    UNI_GUEST_RESOURCE,
    UNI_INSTRUCTIONAL_RESOURCE,
    UNI_MEMBER_RESOURCE,
    UNI_SUPERADMIN_RESOURCE,
    UNIVERSITY_ADMIN_RESOURCE,
)
from database.seeds.setups.university.simulations import (
    ACADEMIC_INTEGRITY_TRAINING_RESOURCE,
    AGGRESSIVE_PRACTICE_RESOURCE,
    CONFUSED_PRACTICE_RESOURCE,
    FERPA_TRAINING_RESOURCE,
    GENERAL_PRACTICE_RESOURCE,
    HAPPY_PRACTICE_RESOURCE,
    PASSIVE_PRACTICE_RESOURCE,
    UPSET_STUDENT_TRAINING_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

PRACTICE_COHORT = sid("uni/cohort/practice")
PRACTICE_COHORT_RESOURCE = sid("uni/cohort-resource/practice")
TRAINING_COHORT = sid("uni/cohort/training")
TRAINING_COHORT_RESOURCE = sid("uni/cohort-resource/training")

# ---------------------------------------------------------------------------
# Cohort definitions
# ---------------------------------------------------------------------------

cohorts = [
    dict(
        id=PRACTICE_COHORT,
        resource_id=PRACTICE_COHORT_RESOURCE,
        name="Practice Cohort",
        description="Open practice cohort with all practice simulations available.",
        simulation_ids=[
            CONFUSED_PRACTICE_RESOURCE,
            HAPPY_PRACTICE_RESOURCE,
            PASSIVE_PRACTICE_RESOURCE,
            AGGRESSIVE_PRACTICE_RESOURCE,
            GENERAL_PRACTICE_RESOURCE,
        ],
        profile_ids=[
            UNI_SUPERADMIN_RESOURCE,
            UNIVERSITY_ADMIN_RESOURCE,
            PROFESSOR_SMITH_RESOURCE,
            TA_JOHNSON_RESOURCE,
            BENCHMARK_PROFILE_RESOURCE,
            UNI_ADMIN_RESOURCE,
            UNI_INSTRUCTIONAL_RESOURCE,
            UNI_MEMBER_RESOURCE,
            UNI_GUEST_RESOURCE,
        ],
        profile_persona_ids=ALL_PROFILE_PERSONA_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=TRAINING_COHORT,
        resource_id=TRAINING_COHORT_RESOURCE,
        name="Training Cohort",
        description="Training cohort with structured training simulations.",
        simulation_ids=[
            ACADEMIC_INTEGRITY_TRAINING_RESOURCE,
            FERPA_TRAINING_RESOURCE,
            UPSET_STUDENT_TRAINING_RESOURCE,
        ],
        profile_ids=[
            UNI_SUPERADMIN_RESOURCE,
            UNIVERSITY_ADMIN_RESOURCE,
            PROFESSOR_SMITH_RESOURCE,
            TA_JOHNSON_RESOURCE,
            UNI_ADMIN_RESOURCE,
            UNI_INSTRUCTIONAL_RESOURCE,
            UNI_MEMBER_RESOURCE,
        ],
        profile_persona_ids=[
            PP_SUPERADMIN,
            PP_UNIVERSITY_ADMIN,
            PP_PROFESSOR_SMITH,
            PP_TA_JOHNSON,
            PP_ADMIN,
            PP_INSTRUCTIONAL,
            PP_MEMBER,
        ],
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
]
