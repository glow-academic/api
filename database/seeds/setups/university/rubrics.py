"""University rubric seed definitions.

Each rubric is a dict of text primitives that maps directly to CreateRubricItem.
The `id` field is a deterministic UUID so downstream seeds (scenarios, simulations)
can reference these rubrics by importing the ID constants.

Names and descriptions are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by scenarios, simulations, etc.
# ---------------------------------------------------------------------------

COMMUNICATION_SKILLS = sid("uni/rubric/communication-skills")
POLICY_KNOWLEDGE = sid("uni/rubric/policy-knowledge")
DE_ESCALATION = sid("uni/rubric/de-escalation")

# ---------------------------------------------------------------------------
# Rubric definitions
# ---------------------------------------------------------------------------

rubrics = [
    # ── Communication Skills ────────────────────────────────────────────
    dict(
        id=COMMUNICATION_SKILLS,
        name="Communication Skills",
        description=(
            "Evaluates clarity of explanations, active listening techniques, "
            "and empathy demonstrated during student interactions. Assesses "
            "whether the trainee adapts language to the student's level of "
            "understanding and confirms comprehension before moving on."
        ),
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    # ── Policy Knowledge ────────────────────────────────────────────────
    dict(
        id=POLICY_KNOWLEDGE,
        name="Policy Knowledge",
        description=(
            "Evaluates accuracy of policy citations, proper procedure "
            "following, and ability to direct students to the correct "
            "institutional resources. Assesses whether the trainee "
            "references official guidelines rather than personal opinion "
            "when advising on academic policies."
        ),
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    # ── De-escalation ───────────────────────────────────────────────────
    dict(
        id=DE_ESCALATION,
        name="De-escalation",
        description=(
            "Evaluates conflict resolution approach, emotional regulation, "
            "and problem-solving under pressure. Assesses whether the "
            "trainee acknowledges the student's frustration, maintains a "
            "calm and professional tone, and guides the conversation toward "
            "a constructive resolution."
        ),
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
]
