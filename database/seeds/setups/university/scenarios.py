"""University scenario seed definitions.

Each scenario is a dict mapping directly to CreateScenarioItem.
Persona references use deterministic IDs imported from personas.py.

Flags are matched by NAME against pre-existing resources (01-resources/).
Names, descriptions, and problem_statements are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.content import (
    ACADEMIC_INTEGRITY_OBJECTIVES,
    ACADEMIC_INTEGRITY_OPTIONS,
    ACADEMIC_INTEGRITY_QUESTIONS,
    FERPA_OBJECTIVES,
    FERPA_OPTIONS,
    FERPA_QUESTIONS,
    UPSET_STUDENT_OBJECTIVES,
    UPSET_STUDENT_OPTIONS,
    UPSET_STUDENT_QUESTIONS,
)
from database.seeds.setups.university.departments import UNIVERSITY_DEPT, UNIVERSITY_DEPT_RESOURCE
from database.seeds.setups.university.documents import (
    ACADEMIC_INTEGRITY_POLICY,
    ACADEMIC_INTEGRITY_POLICY_RESOURCE,
    ACADEMIC_INTEGRITY_IMAGE,
    FERPA_POLICY,
    FERPA_POLICY_RESOURCE,
    FERPA_POLICY_IMAGE,
)
from database.seeds.setups.university.personas import (
    AGGRESSIVE_HIGH,
    AGGRESSIVE_HIGH_RESOURCE,
    CONFUSED,
    CONFUSED_RESOURCE,
    HAPPY,
    HAPPY_RESOURCE,
    INSTRUCTIONAL_STAFF,
    INSTRUCTIONAL_STAFF_RESOURCE,
    PASSIVE,
    PASSIVE_RESOURCE,
    PROFESSOR,
    PROFESSOR_RESOURCE,
    STUDENT,
    STUDENT_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by simulations, cohorts, etc.
# ---------------------------------------------------------------------------

CONFUSED_SCENARIO = sid("uni/scenario/confused")
HAPPY_SCENARIO = sid("uni/scenario/happy")
PASSIVE_SCENARIO = sid("uni/scenario/passive")
AGGRESSIVE_SCENARIO = sid("uni/scenario/aggressive")
GENERAL_SCENARIO = sid("uni/scenario/general")
ACADEMIC_INTEGRITY_SCENARIO = sid("uni/scenario/academic-integrity")
FERPA_SCENARIO = sid("uni/scenario/ferpa")
UPSET_STUDENT_SCENARIO = sid("uni/scenario/upset-student")

CONFUSED_SCENARIO_RESOURCE = sid("uni/scenario-resource/confused")
HAPPY_SCENARIO_RESOURCE = sid("uni/scenario-resource/happy")
PASSIVE_SCENARIO_RESOURCE = sid("uni/scenario-resource/passive")
AGGRESSIVE_SCENARIO_RESOURCE = sid("uni/scenario-resource/aggressive")
GENERAL_SCENARIO_RESOURCE = sid("uni/scenario-resource/general")
ACADEMIC_INTEGRITY_SCENARIO_RESOURCE = sid("uni/scenario-resource/academic-integrity")
FERPA_SCENARIO_RESOURCE = sid("uni/scenario-resource/ferpa")
UPSET_STUDENT_SCENARIO_RESOURCE = sid("uni/scenario-resource/upset-student")

# Video resource IDs — set on scenarios_resource.video_ids at creation,
# resolved later when video seeds run.
ACADEMIC_INTEGRITY_VIDEO = sid("uni/videos-resource/academic-integrity")
FERPA_VIDEO = sid("uni/videos-resource/ferpa")
UPSET_STUDENT_VIDEO = sid("uni/videos-resource/upset-student")

# ---------------------------------------------------------------------------
# Default toggle flags for all scenarios
# ---------------------------------------------------------------------------

_SCENARIO_ACTIVE_TRUE = sid("flag/scenario-active")
_PROBLEM_STATEMENT_TRUE = sid("flag/problem-statement")
_OBJECTIVES_TRUE = sid("flag/objectives")
_IMAGES_TRUE = sid("flag/images")
_IMAGES_FALSE = sid("flag/images/false")
_QUESTIONS_TRUE = sid("flag/questions")
_QUESTIONS_FALSE = sid("flag/questions/false")
_VIDEO_TRUE = sid("flag/video")
_VIDEO_FALSE = sid("flag/video/false")

_PRACTICE_FLAG_IDS = [
    _SCENARIO_ACTIVE_TRUE,
    _PROBLEM_STATEMENT_TRUE,
    _OBJECTIVES_TRUE,
    _IMAGES_TRUE,
    _QUESTIONS_FALSE,
    _VIDEO_FALSE,
]

_TRAINING_FLAG_IDS = [
    _SCENARIO_ACTIVE_TRUE,
    _PROBLEM_STATEMENT_TRUE,
    _OBJECTIVES_TRUE,
    _IMAGES_FALSE,
    _QUESTIONS_TRUE,
    _VIDEO_TRUE,
]

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

scenarios = [
    # ── Practice Scenarios (simple persona-linked) ────────────────────────
    dict(
        id=CONFUSED_SCENARIO,
        resource_id=CONFUSED_SCENARIO_RESOURCE,
        name="Confused Scenario",
        description="Practice scenario featuring a confused or uncertain student persona.",
        persona_ids=[CONFUSED_RESOURCE],
        flag_ids=_PRACTICE_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=HAPPY_SCENARIO,
        resource_id=HAPPY_SCENARIO_RESOURCE,
        name="Happy Scenario",
        description="Practice scenario featuring a cheerful and positive student persona.",
        persona_ids=[HAPPY_RESOURCE],
        flag_ids=_PRACTICE_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=PASSIVE_SCENARIO,
        resource_id=PASSIVE_SCENARIO_RESOURCE,
        name="Passive Scenario",
        description="Practice scenario featuring a passive or hesitant student persona.",
        persona_ids=[PASSIVE_RESOURCE],
        flag_ids=_PRACTICE_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=AGGRESSIVE_SCENARIO,
        resource_id=AGGRESSIVE_SCENARIO_RESOURCE,
        name="Aggressive Scenario",
        description="Practice scenario featuring an aggressive or confrontational student persona.",
        persona_ids=[AGGRESSIVE_HIGH_RESOURCE],
        flag_ids=_PRACTICE_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=GENERAL_SCENARIO,
        resource_id=GENERAL_SCENARIO_RESOURCE,
        name="General Scenario",
        description="General purpose scenario for flexible practice across various situations.",
        flag_ids=_PRACTICE_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Training Scenarios (with problem statements and multiple personas) ─
    dict(
        id=ACADEMIC_INTEGRITY_SCENARIO,
        resource_id=ACADEMIC_INTEGRITY_SCENARIO_RESOURCE,
        name="Academic Integrity Training Scenario",
        description="Training scenario for practicing responses to academic integrity violations and policy enforcement.",
        persona_ids=[PROFESSOR_RESOURCE, STUDENT_RESOURCE],
        problem_statement=(
            "A student is seen looking at another student's exam paper during a test. "
            "The professor notices the behavior and must approach the student to discuss "
            "the violation, explain the consequences, and emphasize the importance of "
            "maintaining academic honesty."
        ),
        flag_ids=_TRAINING_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        document_ids=[ACADEMIC_INTEGRITY_POLICY_RESOURCE],
        video_ids=[ACADEMIC_INTEGRITY_VIDEO],
        image_ids=[ACADEMIC_INTEGRITY_IMAGE],
        objective_ids=ACADEMIC_INTEGRITY_OBJECTIVES,
        question_ids=ACADEMIC_INTEGRITY_QUESTIONS,
        option_ids=ACADEMIC_INTEGRITY_OPTIONS,
    ),
    dict(
        id=FERPA_SCENARIO,
        resource_id=FERPA_SCENARIO_RESOURCE,
        name="FERPA Training Scenario",
        description="Training scenario for practicing FERPA compliance and student privacy protection.",
        persona_ids=[PROFESSOR_RESOURCE, STUDENT_RESOURCE, INSTRUCTIONAL_STAFF_RESOURCE],
        problem_statement=(
            "An instructional staff member accidentally leaves a student's grade sheet "
            "visible on their computer screen. A student notices the visible information "
            "and questions whether this violates FERPA. The staff member must quickly "
            "address the situation and explain the importance of protecting student privacy."
        ),
        flag_ids=_TRAINING_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        document_ids=[FERPA_POLICY_RESOURCE],
        video_ids=[FERPA_VIDEO],
        image_ids=[FERPA_POLICY_IMAGE],
        objective_ids=FERPA_OBJECTIVES,
        question_ids=FERPA_QUESTIONS,
        option_ids=FERPA_OPTIONS,
    ),
    dict(
        id=UPSET_STUDENT_SCENARIO,
        resource_id=UPSET_STUDENT_SCENARIO_RESOURCE,
        name="Upset Student Training Scenario",
        description="Training scenario for practicing de-escalation techniques with upset or frustrated students.",
        persona_ids=[PROFESSOR_RESOURCE, STUDENT_RESOURCE],
        problem_statement=(
            "A student approaches a professor's office hours visibly upset about a grade. "
            "The student expresses frustration and concerns about the grading. The professor "
            "must listen attentively, acknowledge the student's concerns, and offer to review "
            "the work together while providing constructive feedback."
        ),
        flag_ids=_TRAINING_FLAG_IDS,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        video_ids=[UPSET_STUDENT_VIDEO],
        objective_ids=UPSET_STUDENT_OBJECTIVES,
        question_ids=UPSET_STUDENT_QUESTIONS,
        option_ids=UPSET_STUDENT_OPTIONS,
    ),
]
