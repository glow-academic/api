"""University simulation seed definitions.

Each simulation is a dict mapping directly to CreateSimulationItem.
Scenario references use deterministic IDs imported from scenarios.py.

Names and descriptions are CREATED as new resources.
Flag IDs reference pre-existing resources from 01-resources/02-flags.sql.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT, UNIVERSITY_DEPT_RESOURCE
from database.seeds.setups.university.scenario_rubrics import (
    ACADEMIC_INTEGRITY_RUBRICS,
    AGGRESSIVE_RUBRICS,
    CONFUSED_RUBRICS,
    FERPA_RUBRICS,
    GENERAL_RUBRICS,
    HAPPY_RUBRICS,
    PASSIVE_RUBRICS,
    UPSET_STUDENT_RUBRICS,
)
from database.seeds.setups.university.scenarios import (
    ACADEMIC_INTEGRITY_SCENARIO,
    ACADEMIC_INTEGRITY_SCENARIO_RESOURCE,
    AGGRESSIVE_SCENARIO,
    AGGRESSIVE_SCENARIO_RESOURCE,
    CONFUSED_SCENARIO,
    CONFUSED_SCENARIO_RESOURCE,
    FERPA_SCENARIO,
    FERPA_SCENARIO_RESOURCE,
    GENERAL_SCENARIO,
    GENERAL_SCENARIO_RESOURCE,
    HAPPY_SCENARIO,
    HAPPY_SCENARIO_RESOURCE,
    PASSIVE_SCENARIO,
    PASSIVE_SCENARIO_RESOURCE,
    UPSET_STUDENT_SCENARIO,
    UPSET_STUDENT_SCENARIO_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by cohorts, etc.
# ---------------------------------------------------------------------------

CONFUSED_PRACTICE = sid("uni/simulation/confused-practice")
CONFUSED_PRACTICE_RESOURCE = sid("uni/simulation-resource/confused-practice")
HAPPY_PRACTICE = sid("uni/simulation/happy-practice")
HAPPY_PRACTICE_RESOURCE = sid("uni/simulation-resource/happy-practice")
PASSIVE_PRACTICE = sid("uni/simulation/passive-practice")
PASSIVE_PRACTICE_RESOURCE = sid("uni/simulation-resource/passive-practice")
AGGRESSIVE_PRACTICE = sid("uni/simulation/aggressive-practice")
AGGRESSIVE_PRACTICE_RESOURCE = sid("uni/simulation-resource/aggressive-practice")
GENERAL_PRACTICE = sid("uni/simulation/general-practice")
GENERAL_PRACTICE_RESOURCE = sid("uni/simulation-resource/general-practice")
ACADEMIC_INTEGRITY_TRAINING = sid("uni/simulation/academic-integrity-training")
ACADEMIC_INTEGRITY_TRAINING_RESOURCE = sid("uni/simulation-resource/academic-integrity-training")
FERPA_TRAINING = sid("uni/simulation/ferpa-training")
FERPA_TRAINING_RESOURCE = sid("uni/simulation-resource/ferpa-training")
UPSET_STUDENT_TRAINING = sid("uni/simulation/upset-student-training")
UPSET_STUDENT_TRAINING_RESOURCE = sid("uni/simulation-resource/upset-student-training")

# ---------------------------------------------------------------------------
# Pre-existing flag IDs (from 01-resources/02-flags.sql)
# ---------------------------------------------------------------------------

PRACTICE_FLAG = sid("flag/practice")

# ---------------------------------------------------------------------------
# Simulation definitions
# ---------------------------------------------------------------------------

simulations = [
    # ── Practice Simulations (single scenario, practice flag) ──────────────
    dict(
        id=CONFUSED_PRACTICE,
        resource_id=CONFUSED_PRACTICE_RESOURCE,
        name="Confused Practice",
        description="Seeks to understand by asking questions and exploring ideas.",
        scenario_ids=[CONFUSED_SCENARIO_RESOURCE],
        scenario_rubric_ids=CONFUSED_RUBRICS,
        flag_ids=[PRACTICE_FLAG],
        practice_flag_id=PRACTICE_FLAG,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=HAPPY_PRACTICE,
        resource_id=HAPPY_PRACTICE_RESOURCE,
        name="Happy Practice",
        description="Provides uplifting feedback and cheerful responses.",
        scenario_ids=[HAPPY_SCENARIO_RESOURCE],
        scenario_rubric_ids=HAPPY_RUBRICS,
        flag_ids=[PRACTICE_FLAG],
        practice_flag_id=PRACTICE_FLAG,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=PASSIVE_PRACTICE,
        resource_id=PASSIVE_PRACTICE_RESOURCE,
        name="Passive Practice",
        description="Responds with minimal engagement and requires prompting.",
        scenario_ids=[PASSIVE_SCENARIO_RESOURCE],
        scenario_rubric_ids=PASSIVE_RUBRICS,
        flag_ids=[PRACTICE_FLAG],
        practice_flag_id=PRACTICE_FLAG,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=AGGRESSIVE_PRACTICE,
        resource_id=AGGRESSIVE_PRACTICE_RESOURCE,
        name="Aggressive Practice",
        description="Challenges with confrontational and resistant responses.",
        scenario_ids=[AGGRESSIVE_SCENARIO_RESOURCE],
        scenario_rubric_ids=AGGRESSIVE_RUBRICS,
        flag_ids=[PRACTICE_FLAG],
        practice_flag_id=PRACTICE_FLAG,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=GENERAL_PRACTICE,
        resource_id=GENERAL_PRACTICE_RESOURCE,
        name="General Practice",
        description="A flexible simulation for open-ended practice with any persona.",
        scenario_ids=[GENERAL_SCENARIO_RESOURCE],
        scenario_rubric_ids=GENERAL_RUBRICS,
        flag_ids=[PRACTICE_FLAG],
        practice_flag_id=PRACTICE_FLAG,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Training Simulations (multiple scenarios, structured) ──────────────
    dict(
        id=ACADEMIC_INTEGRITY_TRAINING,
        resource_id=ACADEMIC_INTEGRITY_TRAINING_RESOURCE,
        name="Academic Integrity Training",
        description="Training simulation for practicing responses to academic integrity violations.",
        scenario_ids=[ACADEMIC_INTEGRITY_SCENARIO_RESOURCE],
        scenario_rubric_ids=ACADEMIC_INTEGRITY_RUBRICS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=FERPA_TRAINING,
        resource_id=FERPA_TRAINING_RESOURCE,
        name="FERPA Training",
        description="Training simulation for practicing FERPA compliance and student privacy protection.",
        scenario_ids=[FERPA_SCENARIO_RESOURCE],
        scenario_rubric_ids=FERPA_RUBRICS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=UPSET_STUDENT_TRAINING,
        resource_id=UPSET_STUDENT_TRAINING_RESOURCE,
        name="Upset Student Training",
        description="Training simulation for practicing de-escalation techniques with upset students.",
        scenario_ids=[UPSET_STUDENT_SCENARIO_RESOURCE],
        scenario_rubric_ids=UPSET_STUDENT_RUBRICS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
]
