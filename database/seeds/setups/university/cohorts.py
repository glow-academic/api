"""University cohort seed definitions.

Each cohort is a dict mapping directly to CreateCohortItem.
Simulation references use deterministic IDs imported from simulations.py.

Names and descriptions are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import (
    EXTRA_DEPT_RESOURCES,
    UNIVERSITY_DEPT_RESOURCE,
)
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

# ---------------------------------------------------------------------------
# Per-department cohorts — one practice-style cohort per academic department.
#
# Why: the cohort list view paginates at 12 rows/page; with only the two
# cohorts above the list is a tiny demo with no second page. Seeding one
# cohort per extra department (11 below) brings the total to 13, giving a
# full first page plus a second page to demo, and ties each cohort to a
# realistic department.
#
# Each reuses the existing practice simulations, the admin-tier profiles,
# and the admin-tier profile_personas already created upstream — no new
# simulations/profiles needed, so all FKs resolve against rows the earlier
# seed modules materialize. department_ids points at the matching extra
# department's *resource* id (cohort_departments_junction references
# departments_resource).
# ---------------------------------------------------------------------------

_DEPT_COHORTS: list[tuple[str, str, str]] = [
    ("computer-science", "Intro to Programming Cohort", "CS 180 students practicing TA office-hours conversations."),
    ("mathematics", "Calculus Recitation Cohort", "Math TAs rehearsing student support during recitation."),
    ("biology", "Genetics Lab Cohort", "Biology lab instructors practicing student lab guidance."),
    ("history", "World History Seminar Cohort", "History TAs practicing seminar facilitation and feedback."),
    ("physics", "Mechanics Lab Cohort", "Physics instructors practicing lab safety and concept coaching."),
    ("chemistry", "Organic Chemistry Cohort", "Chemistry TAs practicing problem-set office hours."),
    ("english", "Composition Workshop Cohort", "English instructors practicing writing-feedback conversations."),
    ("psychology", "Intro Psychology Cohort", "Psychology TAs practicing student advising scenarios."),
    ("economics", "Microeconomics Cohort", "Economics TAs practicing concept review office hours."),
    ("mechanical-engineering", "Statics Lab Cohort", "Engineering instructors practicing design-review feedback."),
    ("nursing", "Clinical Skills Cohort", "Nursing instructors practicing bedside-manner and care coaching."),
]

_DEPT_COHORT_PRACTICE_SIMULATIONS = [
    CONFUSED_PRACTICE_RESOURCE,
    HAPPY_PRACTICE_RESOURCE,
    PASSIVE_PRACTICE_RESOURCE,
    AGGRESSIVE_PRACTICE_RESOURCE,
    GENERAL_PRACTICE_RESOURCE,
]

_DEPT_COHORT_PROFILES = [
    UNI_SUPERADMIN_RESOURCE,
    UNIVERSITY_ADMIN_RESOURCE,
    PROFESSOR_SMITH_RESOURCE,
    TA_JOHNSON_RESOURCE,
    UNI_INSTRUCTIONAL_RESOURCE,
]

_DEPT_COHORT_PROFILE_PERSONAS = [
    PP_SUPERADMIN,
    PP_UNIVERSITY_ADMIN,
    PP_PROFESSOR_SMITH,
    PP_TA_JOHNSON,
    PP_INSTRUCTIONAL,
]

cohorts += [
    dict(
        id=sid(f"uni/cohort/{slug}"),
        resource_id=sid(f"uni/cohort-resource/{slug}"),
        name=name,
        description=desc,
        simulation_ids=list(_DEPT_COHORT_PRACTICE_SIMULATIONS),
        profile_ids=list(_DEPT_COHORT_PROFILES),
        profile_persona_ids=list(_DEPT_COHORT_PROFILE_PERSONAS),
        department_ids=[EXTRA_DEPT_RESOURCES[slug]],
    )
    for slug, name, desc in _DEPT_COHORTS
]
