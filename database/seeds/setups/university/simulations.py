"""University simulation seed definitions.

Each simulation is a dict mapping directly to CreateSimulationItem.
Scenario references use deterministic IDs imported from scenarios.py.

Names and descriptions are CREATED as new resources.
Flag IDs reference pre-existing resources from 01-resources/02-flags.sql.
"""

from uuid import UUID

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT
from database.seeds.setups.university.scenario_rubrics import (
    ACADEMIC_INTEGRITY_RUBRICS,
    FERPA_RUBRICS,
    UPSET_STUDENT_RUBRICS,
)
from database.seeds.setups.university.scenarios import (
    ACADEMIC_INTEGRITY_SCENARIO,
    AGGRESSIVE_SCENARIO,
    CONFUSED_SCENARIO,
    FERPA_SCENARIO,
    GENERAL_SCENARIO,
    HAPPY_SCENARIO,
    PASSIVE_SCENARIO,
    UPSET_STUDENT_SCENARIO,
)

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by cohorts, etc.
# ---------------------------------------------------------------------------

CONFUSED_PRACTICE = sid("uni/simulation/confused-practice")
HAPPY_PRACTICE = sid("uni/simulation/happy-practice")
PASSIVE_PRACTICE = sid("uni/simulation/passive-practice")
AGGRESSIVE_PRACTICE = sid("uni/simulation/aggressive-practice")
GENERAL_PRACTICE = sid("uni/simulation/general-practice")
ACADEMIC_INTEGRITY_TRAINING = sid("uni/simulation/academic-integrity-training")
FERPA_TRAINING = sid("uni/simulation/ferpa-training")
UPSET_STUDENT_TRAINING = sid("uni/simulation/upset-student-training")

# ---------------------------------------------------------------------------
# Pre-existing flag IDs (from 01-resources/02-flags.sql)
# ---------------------------------------------------------------------------

PRACTICE_FLAG = UUID("019b995a-86ef-78e3-8811-f5d0cfd31e3c")

# ---------------------------------------------------------------------------
# Simulation definitions
# ---------------------------------------------------------------------------

simulations = [
    # ── Practice Simulations (single scenario, practice flag) ──────────────
    dict(
        id=CONFUSED_PRACTICE,
        name="Confused Practice",
        description="Seeks to understand by asking questions and exploring ideas.",
        scenario_ids=[CONFUSED_SCENARIO],
        flag_ids=[PRACTICE_FLAG],
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=HAPPY_PRACTICE,
        name="Happy Practice",
        description="Provides uplifting feedback and cheerful responses.",
        scenario_ids=[HAPPY_SCENARIO],
        flag_ids=[PRACTICE_FLAG],
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=PASSIVE_PRACTICE,
        name="Passive Practice",
        description="Responds with minimal engagement and requires prompting.",
        scenario_ids=[PASSIVE_SCENARIO],
        flag_ids=[PRACTICE_FLAG],
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=AGGRESSIVE_PRACTICE,
        name="Aggressive Practice",
        description="Challenges with confrontational and resistant responses.",
        scenario_ids=[AGGRESSIVE_SCENARIO],
        flag_ids=[PRACTICE_FLAG],
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=GENERAL_PRACTICE,
        name="General Practice",
        description="A flexible simulation for open-ended practice with any persona.",
        scenario_ids=[GENERAL_SCENARIO],
        flag_ids=[PRACTICE_FLAG],
        department_ids=[UNIVERSITY_DEPT],
    ),
    # ── Training Simulations (multiple scenarios, structured) ──────────────
    dict(
        id=ACADEMIC_INTEGRITY_TRAINING,
        name="Academic Integrity Training",
        description="Training simulation for practicing responses to academic integrity violations.",
        scenario_ids=[ACADEMIC_INTEGRITY_SCENARIO],
        scenario_rubric_ids=ACADEMIC_INTEGRITY_RUBRICS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=FERPA_TRAINING,
        name="FERPA Training",
        description="Training simulation for practicing FERPA compliance and student privacy protection.",
        scenario_ids=[FERPA_SCENARIO],
        scenario_rubric_ids=FERPA_RUBRICS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=UPSET_STUDENT_TRAINING,
        name="Upset Student Training",
        description="Training simulation for practicing de-escalation techniques with upset students.",
        scenario_ids=[UPSET_STUDENT_SCENARIO],
        scenario_rubric_ids=UPSET_STUDENT_RUBRICS,
        department_ids=[UNIVERSITY_DEPT],
    ),
]
