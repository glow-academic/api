"""University document seed definitions.

Each document is a dict mapping directly to CreateDocumentItem.
Names and descriptions are CREATED as new resources.

These documents can be linked to scenarios via document_ids.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by scenarios, etc.
# ---------------------------------------------------------------------------

ACADEMIC_INTEGRITY_POLICY = sid("uni/document/academic-integrity-policy")
FERPA_POLICY = sid("uni/document/ferpa-policy")
FERPA_GENERAL = sid("uni/document/ferpa")
SYLLABUS_TEMPLATE = sid("uni/document/syllabus-template")
HOMEWORK_TEMPLATE = sid("uni/document/homework-template")
LAB_TEMPLATE = sid("uni/document/lab-template")
LECTURE_TEMPLATE = sid("uni/document/lecture-template")
MIDTERM_TEMPLATE = sid("uni/document/midterm-template")
POLICY_TEMPLATE = sid("uni/document/policy-template")
PROJECT_TEMPLATE = sid("uni/document/project-template")
QUIZ_TEMPLATE = sid("uni/document/quiz-template")

# ---------------------------------------------------------------------------
# Document definitions
# ---------------------------------------------------------------------------

documents = [
    # ── Policy documents ──────────────────────────────────────────────────
    dict(
        id=ACADEMIC_INTEGRITY_POLICY,
        name="Academic Integrity Policy",
        description="Academic integrity and honor code policy document",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=FERPA_POLICY,
        name="FERPA Policy",
        description="Family Educational Rights and Privacy Act (FERPA) policy document",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=FERPA_GENERAL,
        name="FERPA",
        description="FERPA compliance and student privacy guidelines",
        department_ids=[UNIVERSITY_DEPT],
    ),
    # ── Template documents ────────────────────────────────────────────────
    dict(
        id=SYLLABUS_TEMPLATE,
        name="Syllabus Template",
        description="Template document for syllabus",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=HOMEWORK_TEMPLATE,
        name="Homework Template",
        description="Template document for homework",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=LAB_TEMPLATE,
        name="Lab Template",
        description="Template document for lab",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=LECTURE_TEMPLATE,
        name="Lecture Template",
        description="Template document for lecture",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=MIDTERM_TEMPLATE,
        name="Midterm Template",
        description="Template document for midterm",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=POLICY_TEMPLATE,
        name="Policy Template",
        description="Template document for policy",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=PROJECT_TEMPLATE,
        name="Project Template",
        description="Template document for project",
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=QUIZ_TEMPLATE,
        name="Quiz Template",
        description="Template document for quiz",
        department_ids=[UNIVERSITY_DEPT],
    ),
]
