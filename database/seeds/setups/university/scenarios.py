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
from database.seeds.setups.university.departments import UNIVERSITY_DEPT
from database.seeds.setups.university.documents import (
    ACADEMIC_INTEGRITY_POLICY,
    FERPA_POLICY,
)
from database.seeds.setups.university.personas import (
    AGGRESSIVE_HIGH,
    CONFUSED,
    HAPPY,
    INSTRUCTIONAL_STAFF,
    PASSIVE,
    PROFESSOR,
    STUDENT,
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

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

scenarios = [
    # ── Practice Scenarios (simple persona-linked) ────────────────────────
    dict(
        id=CONFUSED_SCENARIO,
        name="Confused Scenario",
        description="Practice scenario featuring a confused or uncertain student persona.",
        persona_ids=[CONFUSED],
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=HAPPY_SCENARIO,
        name="Happy Scenario",
        description="Practice scenario featuring a cheerful and positive student persona.",
        persona_ids=[HAPPY],
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=PASSIVE_SCENARIO,
        name="Passive Scenario",
        description="Practice scenario featuring a passive or hesitant student persona.",
        persona_ids=[PASSIVE],
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=AGGRESSIVE_SCENARIO,
        name="Aggressive Scenario",
        description="Practice scenario featuring an aggressive or confrontational student persona.",
        persona_ids=[AGGRESSIVE_HIGH],
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=GENERAL_SCENARIO,
        name="General Scenario",
        description="General purpose scenario for flexible practice across various situations.",
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
    ),
    # ── Training Scenarios (with problem statements and multiple personas) ─
    dict(
        id=ACADEMIC_INTEGRITY_SCENARIO,
        name="Academic Integrity Training Scenario",
        description="Training scenario for practicing responses to academic integrity violations and policy enforcement.",
        persona_ids=[PROFESSOR, STUDENT],
        problem_statement=(
            "A student is seen looking at another student's exam paper during a test. "
            "The professor notices the behavior and must approach the student to discuss "
            "the violation, explain the consequences, and emphasize the importance of "
            "maintaining academic honesty."
        ),
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
        document_ids=[ACADEMIC_INTEGRITY_POLICY],
        objective_ids=ACADEMIC_INTEGRITY_OBJECTIVES,
        question_ids=ACADEMIC_INTEGRITY_QUESTIONS,
        option_ids=ACADEMIC_INTEGRITY_OPTIONS,
    ),
    dict(
        id=FERPA_SCENARIO,
        name="FERPA Training Scenario",
        description="Training scenario for practicing FERPA compliance and student privacy protection.",
        persona_ids=[PROFESSOR, STUDENT, INSTRUCTIONAL_STAFF],
        problem_statement=(
            "An instructional staff member accidentally leaves a student's grade sheet "
            "visible on their computer screen. A student notices the visible information "
            "and questions whether this violates FERPA. The staff member must quickly "
            "address the situation and explain the importance of protecting student privacy."
        ),
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
        document_ids=[FERPA_POLICY],
        objective_ids=FERPA_OBJECTIVES,
        question_ids=FERPA_QUESTIONS,
        option_ids=FERPA_OPTIONS,
    ),
    dict(
        id=UPSET_STUDENT_SCENARIO,
        name="Upset Student Training Scenario",
        description="Training scenario for practicing de-escalation techniques with upset or frustrated students.",
        persona_ids=[PROFESSOR, STUDENT],
        problem_statement=(
            "A student approaches a professor's office hours visibly upset about a grade. "
            "The student expresses frustration and concerns about the grading. The professor "
            "must listen attentively, acknowledge the student's concerns, and offer to review "
            "the work together while providing constructive feedback."
        ),
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT],
        objective_ids=UPSET_STUDENT_OBJECTIVES,
        question_ids=UPSET_STUDENT_QUESTIONS,
        option_ids=UPSET_STUDENT_OPTIONS,
    ),
]
