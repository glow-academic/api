"""University scenario-rubric seed definitions.

Each scenario_rubric is a junction resource linking a scenario to a rubric.
The `id` field is a deterministic UUID so downstream seeds (simulations, etc.)
can reference these pairings by importing the ID constants.

Grouped ID lists (e.g. ACADEMIC_INTEGRITY_RUBRICS) are provided for easy
import by simulations.py or other consumers.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.rubrics import (
    DE_ESCALATION_RESOURCE,
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
FERPA_POLICY_KNOWLEDGE = sid("uni/scenario-rubric/ferpa+policy-knowledge")
UPSET_STUDENT_DE_ESCALATION = sid("uni/scenario-rubric/upset-student+de-escalation")

# Practice scenario-rubric IDs (each practice scenario → Training Rubric)
CONFUSED_TRAINING = sid("uni/scenario-rubric/confused+training")
HAPPY_TRAINING = sid("uni/scenario-rubric/happy+training")
PASSIVE_TRAINING = sid("uni/scenario-rubric/passive+training")
AGGRESSIVE_TRAINING = sid("uni/scenario-rubric/aggressive+training")
GENERAL_TRAINING = sid("uni/scenario-rubric/general+training")

ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE_RESOURCE = sid(
    "uni/scenario-rubric-resource/academic-integrity+policy-knowledge"
)
FERPA_POLICY_KNOWLEDGE_RESOURCE = sid(
    "uni/scenario-rubric-resource/ferpa+policy-knowledge"
)
UPSET_STUDENT_DE_ESCALATION_RESOURCE = sid(
    "uni/scenario-rubric-resource/upset-student+de-escalation"
)

# ---------------------------------------------------------------------------
# Grouped IDs — convenient for simulations.py imports
# ---------------------------------------------------------------------------

ACADEMIC_INTEGRITY_RUBRICS = [ACADEMIC_INTEGRITY_POLICY_KNOWLEDGE]
FERPA_RUBRICS = [FERPA_POLICY_KNOWLEDGE]
UPSET_STUDENT_RUBRICS = [UPSET_STUDENT_DE_ESCALATION]
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
    # -- FERPA + Policy Knowledge ----------------------------------------------
    dict(
        id=FERPA_POLICY_KNOWLEDGE,
        resource_id=FERPA_POLICY_KNOWLEDGE_RESOURCE,
        scenario_id=FERPA_SCENARIO_RESOURCE,
        rubric_id=POLICY_KNOWLEDGE_RESOURCE,
    ),
    # -- Upset Student + De-escalation -----------------------------------------
    dict(
        id=UPSET_STUDENT_DE_ESCALATION,
        resource_id=UPSET_STUDENT_DE_ESCALATION_RESOURCE,
        scenario_id=UPSET_STUDENT_SCENARIO_RESOURCE,
        rubric_id=DE_ESCALATION_RESOURCE,
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
