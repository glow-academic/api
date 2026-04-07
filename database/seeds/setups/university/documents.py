"""University document seed definitions.

Each document is a dict mapping directly to CreateDocumentItem.
Names and descriptions are CREATED as new resources.

These documents can be linked to scenarios via document_ids.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT, UNIVERSITY_DEPT_RESOURCE

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
        resource_id=sid("uni/document-resource/academic-integrity-policy"),
        name="Academic Integrity Policy",
        description="Academic integrity and honor code policy document",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=FERPA_POLICY,
        resource_id=sid("uni/document-resource/ferpa-policy"),
        name="FERPA Policy",
        description="Family Educational Rights and Privacy Act (FERPA) policy document",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=FERPA_GENERAL,
        resource_id=sid("uni/document-resource/ferpa"),
        name="FERPA",
        description="FERPA compliance and student privacy guidelines",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Template documents ────────────────────────────────────────────────
    dict(
        id=SYLLABUS_TEMPLATE,
        resource_id=sid("uni/document-resource/syllabus-template"),
        name="Syllabus Template",
        description="Template document for syllabus",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=HOMEWORK_TEMPLATE,
        resource_id=sid("uni/document-resource/homework-template"),
        name="Homework Template",
        description="Template document for homework",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=LAB_TEMPLATE,
        resource_id=sid("uni/document-resource/lab-template"),
        name="Lab Template",
        description="Template document for lab",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=LECTURE_TEMPLATE,
        resource_id=sid("uni/document-resource/lecture-template"),
        name="Lecture Template",
        description="Template document for lecture",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=MIDTERM_TEMPLATE,
        resource_id=sid("uni/document-resource/midterm-template"),
        name="Midterm Template",
        description="Template document for midterm",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=POLICY_TEMPLATE,
        resource_id=sid("uni/document-resource/policy-template"),
        name="Policy Template",
        description="Template document for policy",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=PROJECT_TEMPLATE,
        resource_id=sid("uni/document-resource/project-template"),
        name="Project Template",
        description="Template document for project",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=QUIZ_TEMPLATE,
        resource_id=sid("uni/document-resource/quiz-template"),
        name="Quiz Template",
        description="Template document for quiz",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
]
