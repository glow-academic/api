"""University parameter seed definitions.

Each parameter is a dict mapping directly to CreateParameterItem.
Parameters group related fields into logical categories.

Names and descriptions are CREATED as new resources.
Field references use deterministic IDs imported from fields.py.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT
from database.seeds.setups.university.fields import (
    CLASS_FIELDS,
    CONCEPTS_FIELDS,
    CROWDEDNESS_FIELDS,
    DEADLINE_FIELDS,
    DOCUMENT_TYPE_FIELDS,
    INTENSITY_FIELDS,
    LOCATION_FIELDS,
    PERSONA_TYPE_FIELDS,
    ROLE_FIELDS,
    TEMPERAMENT_FIELDS,
    TIME_FIELDS,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

P_TEMPERAMENT = sid("uni/parameter/temperament")
P_PERSONA_TYPE = sid("uni/parameter/persona-type")
P_INTENSITY = sid("uni/parameter/intensity")
P_CROWDEDNESS = sid("uni/parameter/crowdedness")
P_DEADLINE = sid("uni/parameter/deadline")
P_TIME = sid("uni/parameter/time")
P_LOCATION = sid("uni/parameter/location")
P_CLASS = sid("uni/parameter/class")
P_DOCUMENT_TYPE = sid("uni/parameter/document-type")
P_CONCEPTS = sid("uni/parameter/concepts")
P_ROLE = sid("uni/parameter/role")

# ---------------------------------------------------------------------------
# Parameter definitions
# ---------------------------------------------------------------------------

parameters = [
    dict(
        id=P_TEMPERAMENT,
        name="Temperament",
        description="Emotional temperament types for personas (aggressive, passive, confused, happy)",
        field_ids=TEMPERAMENT_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_PERSONA_TYPE,
        name="Persona Type",
        description="Categorizes personas by their type (Emotion or Neutral)",
        field_ids=PERSONA_TYPE_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_INTENSITY,
        name="Intensity",
        description="How emotionally charged or urgent the situation feels",
        field_ids=INTENSITY_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_CROWDEDNESS,
        name="Crowdedness",
        description="How many students are present in the room",
        field_ids=CROWDEDNESS_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_DEADLINE,
        name="Deadline",
        description="How close it is to an assignment or project deadline",
        field_ids=DEADLINE_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_TIME,
        name="Time",
        description="When the scenario occurs",
        field_ids=TIME_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_LOCATION,
        name="Location",
        description="Where the interaction is taking place",
        field_ids=LOCATION_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_CLASS,
        name="Class",
        description="Which course or subject the scenario is about",
        field_ids=CLASS_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_DOCUMENT_TYPE,
        name="Document Type",
        description="Categorizes documents by their type (homework, project, quiz, etc.)",
        field_ids=DOCUMENT_TYPE_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_CONCEPTS,
        name="Concepts",
        description="FERPA-related concepts for policy selection",
        field_ids=CONCEPTS_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
    dict(
        id=P_ROLE,
        name="Role",
        description="Role types for neutral personas (Student, Professor, Instructional Staff)",
        field_ids=ROLE_FIELDS,
        department_ids=[UNIVERSITY_DEPT],
    ),
]
