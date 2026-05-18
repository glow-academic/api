"""University rubric seed definitions.

Each rubric is a dict of text primitives that maps directly to CreateRubricItem.
The `id` field is a deterministic UUID so downstream seeds (scenarios, simulations)
can reference these rubrics by importing the ID constants.

Names and descriptions are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT, UNIVERSITY_DEPT_RESOURCE

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by scenarios, simulations, etc.
# ---------------------------------------------------------------------------

COMMUNICATION_SKILLS = sid("uni/rubric/communication-skills")
POLICY_KNOWLEDGE = sid("uni/rubric/policy-knowledge")
DE_ESCALATION = sid("uni/rubric/de-escalation")

COMMUNICATION_SKILLS_RESOURCE = sid("uni/rubric-resource/communication-skills")
POLICY_KNOWLEDGE_RESOURCE = sid("uni/rubric-resource/policy-knowledge")
DE_ESCALATION_RESOURCE = sid("uni/rubric-resource/de-escalation")

# ---------------------------------------------------------------------------
# Standard group IDs (defined in database/seeds/resources/standard_groups.py)
# ---------------------------------------------------------------------------

_COMMUNICATION_SKILLS_SG_IDS = [
    sid("standard-group/uni-clarity"),
    sid("standard-group/uni-active-listening"),
    sid("standard-group/uni-empathy"),
    sid("standard-group/uni-language-adaptation"),
]

_POLICY_KNOWLEDGE_SG_IDS = [
    sid("standard-group/uni-policy-accuracy"),
    sid("standard-group/uni-procedure-compliance"),
    sid("standard-group/uni-resource-referral"),
]

_DE_ESCALATION_SG_IDS = [
    sid("standard-group/uni-conflict-recognition"),
    sid("standard-group/uni-emotional-regulation"),
    sid("standard-group/uni-solution-oriented"),
    sid("standard-group/uni-professional-tone"),
]

# ---------------------------------------------------------------------------
# Standard IDs (defined in database/seeds/resources/standards.py)
# ---------------------------------------------------------------------------

_LEVELS = ["excellent", "good", "acceptable", "marginal", "poor"]

_COMMUNICATION_SKILLS_STD_IDS = [
    sid(f"standard/uni-{slug}/{level}")
    for slug in ["clarity", "active-listening", "empathy", "language-adaptation"]
    for level in _LEVELS
]

_POLICY_KNOWLEDGE_STD_IDS = [
    sid(f"standard/uni-{slug}/{level}")
    for slug in ["policy-accuracy", "procedure-compliance", "resource-referral"]
    for level in _LEVELS
]

_DE_ESCALATION_STD_IDS = [
    sid(f"standard/uni-{slug}/{level}")
    for slug in [
        "conflict-recognition",
        "emotional-regulation",
        "solution-oriented",
        "professional-tone",
    ]
    for level in _LEVELS
]

# ---------------------------------------------------------------------------
# Point IDs (defined in database/seeds/resources/points.py)
# ---------------------------------------------------------------------------

_PASS_16 = sid("point/pass/16")
_PASS_12 = sid("point/pass/12")

# ---------------------------------------------------------------------------
# Rubric definitions
# ---------------------------------------------------------------------------

rubrics = [
    # ── Communication Skills ────────────────────────────────────────────
    dict(
        id=COMMUNICATION_SKILLS,
        resource_id=COMMUNICATION_SKILLS_RESOURCE,
        name="Communication Skills",
        description=(
            "Evaluates clarity of explanations, active listening techniques, "
            "and empathy demonstrated during student interactions. Assesses "
            "whether the trainee adapts language to the student's level of "
            "understanding and confirms comprehension before moving on."
        ),
        flag_ids=[sid("flag/rubric-active"), sid("flag/simulation-rubric")],
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        standard_group_ids=_COMMUNICATION_SKILLS_SG_IDS,
        standard_ids=_COMMUNICATION_SKILLS_STD_IDS,
        pass_points_id=_PASS_16,
    ),
    # ── Policy Knowledge ────────────────────────────────────────────────
    dict(
        id=POLICY_KNOWLEDGE,
        resource_id=POLICY_KNOWLEDGE_RESOURCE,
        name="Policy Knowledge",
        description=(
            "Evaluates accuracy of policy citations, proper procedure "
            "following, and ability to direct students to the correct "
            "institutional resources. Assesses whether the trainee "
            "references official guidelines rather than personal opinion "
            "when advising on academic policies."
        ),
        flag_ids=[sid("flag/rubric-active"), sid("flag/video-rubric")],
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        standard_group_ids=_POLICY_KNOWLEDGE_SG_IDS,
        standard_ids=_POLICY_KNOWLEDGE_STD_IDS,
        pass_points_id=_PASS_12,
    ),
    # ── De-escalation ───────────────────────────────────────────────────
    dict(
        id=DE_ESCALATION,
        resource_id=DE_ESCALATION_RESOURCE,
        name="De-escalation",
        description=(
            "Evaluates conflict resolution approach, emotional regulation, "
            "and problem-solving under pressure. Assesses whether the "
            "trainee acknowledges the student's frustration, maintains a "
            "calm and professional tone, and guides the conversation toward "
            "a constructive resolution."
        ),
        flag_ids=[sid("flag/rubric-active"), sid("flag/simulation-rubric")],
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        standard_group_ids=_DE_ESCALATION_SG_IDS,
        standard_ids=_DE_ESCALATION_STD_IDS,
        pass_points_id=_PASS_16,
    ),
]
