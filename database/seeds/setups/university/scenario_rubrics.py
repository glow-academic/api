"""University scenario-rubric seed definitions.

Each scenario_rubric is a junction resource linking a scenario to a rubric.
The `id` field is a deterministic UUID so downstream seeds (simulations, etc.)
can reference these pairings by importing the ID constants.

Grouped ID lists (e.g. ACADEMIC_INTEGRITY_RUBRICS) are provided for easy
import by simulations.py or other consumers.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.rubrics import (
    COMMUNICATION_SKILLS,
    DE_ESCALATION,
    POLICY_KNOWLEDGE,
)
from database.seeds.setups.university.scenarios import (
    ACADEMIC_INTEGRITY_SCENARIO,
    FERPA_SCENARIO,
    UPSET_STUDENT_SCENARIO,
)

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by simulations, etc.
# ---------------------------------------------------------------------------

ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE = sid(
    "uni/scenario-rubric/academic-integrity+policy-knowledge"
)
ACADEMIC_INTEGRITY_COMMUNICATION_SKILLS = sid(
    "uni/scenario-rubric/academic-integrity+communication-skills"
)
FERPA_POLICY_KNOWLEDGE = sid("uni/scenario-rubric/ferpa+policy-knowledge")
FERPA_COMMUNICATION_SKILLS = sid("uni/scenario-rubric/ferpa+communication-skills")
UPSET_STUDENT_DE_ESCALATION = sid("uni/scenario-rubric/upset-student+de-escalation")
UPSET_STUDENT_COMMUNICATION_SKILLS = sid(
    "uni/scenario-rubric/upset-student+communication-skills"
)

# ---------------------------------------------------------------------------
# Grouped IDs — convenient for simulations.py imports
# ---------------------------------------------------------------------------

ACADEMIC_INTEGRITY_RUBRICS = [
    ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE,
    ACADEMIC_INTEGRITY_COMMUNICATION_SKILLS,
]
FERPA_RUBRICS = [FERPA_POLICY_KNOWLEDGE, FERPA_COMMUNICATION_SKILLS]
UPSET_STUDENT_RUBRICS = [
    UPSET_STUDENT_DE_ESCALATION,
    UPSET_STUDENT_COMMUNICATION_SKILLS,
]

# ---------------------------------------------------------------------------
# Scenario-rubric definitions
# ---------------------------------------------------------------------------

scenario_rubrics = [
    # -- Academic Integrity + Policy Knowledge ---------------------------------
    dict(
        id=ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE,
        scenario_id=ACADEMIC_INTEGRITY_SCENARIO,
        rubric_id=POLICY_KNOWLEDGE,
    ),
    # -- Academic Integrity + Communication Skills -----------------------------
    dict(
        id=ACADEMIC_INTEGRITY_COMMUNICATION_SKILLS,
        scenario_id=ACADEMIC_INTEGRITY_SCENARIO,
        rubric_id=COMMUNICATION_SKILLS,
    ),
    # -- FERPA + Policy Knowledge ----------------------------------------------
    dict(
        id=FERPA_POLICY_KNOWLEDGE,
        scenario_id=FERPA_SCENARIO,
        rubric_id=POLICY_KNOWLEDGE,
    ),
    # -- FERPA + Communication Skills ------------------------------------------
    dict(
        id=FERPA_COMMUNICATION_SKILLS,
        scenario_id=FERPA_SCENARIO,
        rubric_id=COMMUNICATION_SKILLS,
    ),
    # -- Upset Student + De-escalation -----------------------------------------
    dict(
        id=UPSET_STUDENT_DE_ESCALATION,
        scenario_id=UPSET_STUDENT_SCENARIO,
        rubric_id=DE_ESCALATION,
    ),
    # -- Upset Student + Communication Skills ----------------------------------
    dict(
        id=UPSET_STUDENT_COMMUNICATION_SKILLS,
        scenario_id=UPSET_STUDENT_SCENARIO,
        rubric_id=COMMUNICATION_SKILLS,
    ),
]
