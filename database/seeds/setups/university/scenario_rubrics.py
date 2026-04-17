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
    COMMUNICATION_SKILLS_RESOURCE,
    DE_ESCALATION,
    DE_ESCALATION_RESOURCE,
    POLICY_KNOWLEDGE,
    POLICY_KNOWLEDGE_RESOURCE,
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

# Training Rubric resource ID (defined in database/seeds/rubrics.py)
TRAINING_RUBRIC_RESOURCE = sid("rubric-resource/training-rubric")

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

# Practice scenario-rubric IDs (each practice scenario → Training Rubric)
CONFUSED_TRAINING = sid("uni/scenario-rubric/confused+training")
HAPPY_TRAINING = sid("uni/scenario-rubric/happy+training")
PASSIVE_TRAINING = sid("uni/scenario-rubric/passive+training")
AGGRESSIVE_TRAINING = sid("uni/scenario-rubric/aggressive+training")
GENERAL_TRAINING = sid("uni/scenario-rubric/general+training")

ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE_RESOURCE = sid(
    "uni/scenario-rubric-resource/academic-integrity+policy-knowledge"
)
ACADEMIC_INTEGRITY_COMMUNICATION_SKILLS_RESOURCE = sid(
    "uni/scenario-rubric-resource/academic-integrity+communication-skills"
)
FERPA_POLICY_KNOWLEDGE_RESOURCE = sid(
    "uni/scenario-rubric-resource/ferpa+policy-knowledge"
)
FERPA_COMMUNICATION_SKILLS_RESOURCE = sid(
    "uni/scenario-rubric-resource/ferpa+communication-skills"
)
UPSET_STUDENT_DE_ESCALATION_RESOURCE = sid(
    "uni/scenario-rubric-resource/upset-student+de-escalation"
)
UPSET_STUDENT_COMMUNICATION_SKILLS_RESOURCE = sid(
    "uni/scenario-rubric-resource/upset-student+communication-skills"
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
CONFUSED_RUBRICS = [CONFUSED_TRAINING]
HAPPY_RUBRICS = [HAPPY_TRAINING]
PASSIVE_RUBRICS = [PASSIVE_TRAINING]
AGGRESSIVE_RUBRICS = [AGGRESSIVE_TRAINING]
GENERAL_RUBRICS = [GENERAL_TRAINING]

# ---------------------------------------------------------------------------
# Scenario-rubric definitions
# ---------------------------------------------------------------------------

scenario_rubrics = [
    # -- Academic Integrity + Policy Knowledge ---------------------------------
    dict(
        id=ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE,
        resource_id=ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE_RESOURCE,
        scenario_id=ACADEMIC_INTEGRITY_SCENARIO_RESOURCE,
        rubric_id=POLICY_KNOWLEDGE_RESOURCE,
    ),
    # -- Academic Integrity + Communication Skills -----------------------------
    dict(
        id=ACADEMIC_INTEGRITY_COMMUNICATION_SKILLS,
        resource_id=ACADEMIC_INTEGRITY_COMMUNICATION_SKILLS_RESOURCE,
        scenario_id=ACADEMIC_INTEGRITY_SCENARIO_RESOURCE,
        rubric_id=COMMUNICATION_SKILLS_RESOURCE,
    ),
    # -- FERPA + Policy Knowledge ----------------------------------------------
    dict(
        id=FERPA_POLICY_KNOWLEDGE,
        resource_id=FERPA_POLICY_KNOWLEDGE_RESOURCE,
        scenario_id=FERPA_SCENARIO_RESOURCE,
        rubric_id=POLICY_KNOWLEDGE_RESOURCE,
    ),
    # -- FERPA + Communication Skills ------------------------------------------
    dict(
        id=FERPA_COMMUNICATION_SKILLS,
        resource_id=FERPA_COMMUNICATION_SKILLS_RESOURCE,
        scenario_id=FERPA_SCENARIO_RESOURCE,
        rubric_id=COMMUNICATION_SKILLS_RESOURCE,
    ),
    # -- Upset Student + De-escalation -----------------------------------------
    dict(
        id=UPSET_STUDENT_DE_ESCALATION,
        resource_id=UPSET_STUDENT_DE_ESCALATION_RESOURCE,
        scenario_id=UPSET_STUDENT_SCENARIO_RESOURCE,
        rubric_id=DE_ESCALATION_RESOURCE,
    ),
    # -- Upset Student + Communication Skills ----------------------------------
    dict(
        id=UPSET_STUDENT_COMMUNICATION_SKILLS,
        resource_id=UPSET_STUDENT_COMMUNICATION_SKILLS_RESOURCE,
        scenario_id=UPSET_STUDENT_SCENARIO_RESOURCE,
        rubric_id=COMMUNICATION_SKILLS_RESOURCE,
    ),
    # -- Practice Scenarios + Training Rubric ---------------------------------
    dict(
        id=CONFUSED_TRAINING,
        scenario_id=CONFUSED_SCENARIO_RESOURCE,
        rubric_id=TRAINING_RUBRIC_RESOURCE,
    ),
    dict(
        id=HAPPY_TRAINING,
        scenario_id=HAPPY_SCENARIO_RESOURCE,
        rubric_id=TRAINING_RUBRIC_RESOURCE,
    ),
    dict(
        id=PASSIVE_TRAINING,
        scenario_id=PASSIVE_SCENARIO_RESOURCE,
        rubric_id=TRAINING_RUBRIC_RESOURCE,
    ),
    dict(
        id=AGGRESSIVE_TRAINING,
        scenario_id=AGGRESSIVE_SCENARIO_RESOURCE,
        rubric_id=TRAINING_RUBRIC_RESOURCE,
    ),
    dict(
        id=GENERAL_TRAINING,
        scenario_id=GENERAL_SCENARIO_RESOURCE,
        rubric_id=TRAINING_RUBRIC_RESOURCE,
    ),
]
