"""Parameter field ID lookup helpers.

Provides easy access to parameter_field IDs by parameter/field name
for use in persona, document, and scenario seeds.
"""

from database.seeds.setups.university.parameter_fields import parameter_fields
from database.seeds.setups.university.parameters import (
    P_TEMPERAMENT_RESOURCE, P_PERSONA_TYPE_RESOURCE, P_INTENSITY_RESOURCE,
    P_CROWDEDNESS_RESOURCE, P_DEADLINE_RESOURCE, P_TIME_RESOURCE,
    P_LOCATION_RESOURCE, P_CLASS_RESOURCE, P_DOCUMENT_TYPE_RESOURCE,
    P_CONCEPTS_RESOURCE, P_ROLE_RESOURCE,
)
from database.seeds.setups.university.fields import (
    # Temperament
    FR_AGGRESSIVE, FR_CONFUSED, FR_HAPPY, FR_PASSIVE,
    # Persona Type
    FR_EMOTION, FR_NEUTRAL,
    # Intensity
    FR_VERY_CALM_1, FR_CALM_2, FR_MILD_3, FR_SLIGHTLY_TENSE_4,
    FR_MODERATE_5, FR_NOTICEABLY_INTENSE_6, FR_TENSE_7,
    FR_VERY_TENSE_8, FR_EXTREMELY_INTENSE_9, FR_MAXIMUM_INTENSITY_10,
    # Role
    FR_STUDENT, FR_PROFESSOR, FR_INSTRUCTIONAL_STAFF,
    # Document Type
    FR_HOMEWORK, FR_LAB, FR_LECTURE, FR_MIDTERM, FR_POLICY,
    FR_PROJECT, FR_QUIZ, FR_SYLLABUS,
    # Concepts
    FR_ANNUAL_FERPA, FR_CONSENT_DISCLOSURES, FR_EDUCATION_RECORDS,
    FR_RECORD_AMENDMENT, FR_STUDENT_ACCESS,
)

# Build lookup: (param_resource_id, field_resource_id) -> parameter_field_id
_PF = {}
for pf in parameter_fields:
    _PF[(pf["parameter_id"], pf["field_id"])] = pf["id"]


def pf(param_resource, field_resource):
    """Get parameter_field ID from parameter + field resource IDs."""
    return _PF[(param_resource, field_resource)]


# ---------------------------------------------------------------------------
# Persona parameter_field_ids
# ---------------------------------------------------------------------------

PF_CONFUSED = [pf(P_TEMPERAMENT_RESOURCE, FR_CONFUSED)]
PF_HAPPY = [pf(P_TEMPERAMENT_RESOURCE, FR_HAPPY)]
PF_PASSIVE = [pf(P_TEMPERAMENT_RESOURCE, FR_PASSIVE)]

PF_AGGRESSIVE_HIGH = [
    pf(P_INTENSITY_RESOURCE, FR_VERY_TENSE_8),
    pf(P_INTENSITY_RESOURCE, FR_EXTREMELY_INTENSE_9),
    pf(P_INTENSITY_RESOURCE, FR_MAXIMUM_INTENSITY_10),
]
PF_AGGRESSIVE_MEDIUM = [
    pf(P_INTENSITY_RESOURCE, FR_MODERATE_5),
    pf(P_INTENSITY_RESOURCE, FR_NOTICEABLY_INTENSE_6),
    pf(P_INTENSITY_RESOURCE, FR_TENSE_7),
]
PF_AGGRESSIVE_LOW = [
    pf(P_INTENSITY_RESOURCE, FR_VERY_CALM_1),
    pf(P_INTENSITY_RESOURCE, FR_CALM_2),
    pf(P_INTENSITY_RESOURCE, FR_MILD_3),
    pf(P_INTENSITY_RESOURCE, FR_SLIGHTLY_TENSE_4),
]

PF_STUDENT = [pf(P_ROLE_RESOURCE, FR_STUDENT)]
PF_PROFESSOR = [pf(P_ROLE_RESOURCE, FR_PROFESSOR)]
PF_INSTRUCTIONAL_STAFF = [pf(P_ROLE_RESOURCE, FR_INSTRUCTIONAL_STAFF)]

# ---------------------------------------------------------------------------
# Document parameter_field_ids
# ---------------------------------------------------------------------------

PF_DOC_HOMEWORK = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_HOMEWORK)]
PF_DOC_LAB = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_LAB)]
PF_DOC_LECTURE = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_LECTURE)]
PF_DOC_MIDTERM = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_MIDTERM)]
PF_DOC_POLICY = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_POLICY)]
PF_DOC_PROJECT = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_PROJECT)]
PF_DOC_QUIZ = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_QUIZ)]
PF_DOC_SYLLABUS = [pf(P_DOCUMENT_TYPE_RESOURCE, FR_SYLLABUS)]

PF_ALL_CONCEPTS = [
    pf(P_CONCEPTS_RESOURCE, FR_ANNUAL_FERPA),
    pf(P_CONCEPTS_RESOURCE, FR_CONSENT_DISCLOSURES),
    pf(P_CONCEPTS_RESOURCE, FR_EDUCATION_RECORDS),
    pf(P_CONCEPTS_RESOURCE, FR_RECORD_AMENDMENT),
    pf(P_CONCEPTS_RESOURCE, FR_STUDENT_ACCESS),
]

PF_FERPA_DOC = PF_ALL_CONCEPTS + PF_DOC_POLICY
PF_POLICY_TEMPLATE = PF_ALL_CONCEPTS + PF_DOC_POLICY
