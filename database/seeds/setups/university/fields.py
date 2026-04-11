"""University field seed definitions.

Each field is a dict mapping directly to CreateFieldItem.
Fields are grouped by their parent parameter for readability.

Names and descriptions are CREATED as new resources.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT, UNIVERSITY_DEPT_RESOURCE

# ---------------------------------------------------------------------------
# Deterministic IDs — organized by parameter group
# ---------------------------------------------------------------------------

# ── Temperament fields (4) ────────────────────────────────────────────────

F_AGGRESSIVE = sid("uni/field/aggressive")
FR_AGGRESSIVE = sid("uni/field-resource/aggressive")
F_CONFUSED = sid("uni/field/confused")
FR_CONFUSED = sid("uni/field-resource/confused")
F_HAPPY = sid("uni/field/happy")
FR_HAPPY = sid("uni/field-resource/happy")
F_PASSIVE = sid("uni/field/passive")
FR_PASSIVE = sid("uni/field-resource/passive")

TEMPERAMENT_FIELDS = [F_HAPPY, F_PASSIVE, F_CONFUSED, F_AGGRESSIVE]
TEMPERAMENT_FIELD_RESOURCES = [FR_HAPPY, FR_PASSIVE, FR_CONFUSED, FR_AGGRESSIVE]

# ── Persona Type fields (2) ───────────────────────────────────────────────

F_EMOTION = sid("uni/field/emotion")
FR_EMOTION = sid("uni/field-resource/emotion")
F_NEUTRAL = sid("uni/field/neutral")
FR_NEUTRAL = sid("uni/field-resource/neutral")

PERSONA_TYPE_FIELDS = [F_EMOTION, F_NEUTRAL]
PERSONA_TYPE_FIELD_RESOURCES = [FR_EMOTION, FR_NEUTRAL]

# ── Intensity fields (10) ─────────────────────────────────────────────────

F_VERY_CALM_1 = sid("uni/field/very-calm-1")
FR_VERY_CALM_1 = sid("uni/field-resource/very-calm-1")
F_CALM_2 = sid("uni/field/calm-2")
FR_CALM_2 = sid("uni/field-resource/calm-2")
F_MILD_3 = sid("uni/field/mild-3")
FR_MILD_3 = sid("uni/field-resource/mild-3")
F_SLIGHTLY_TENSE_4 = sid("uni/field/slightly-tense-4")
FR_SLIGHTLY_TENSE_4 = sid("uni/field-resource/slightly-tense-4")
F_MODERATE_5 = sid("uni/field/moderate-5")
FR_MODERATE_5 = sid("uni/field-resource/moderate-5")
F_NOTICEABLY_INTENSE_6 = sid("uni/field/noticeably-intense-6")
FR_NOTICEABLY_INTENSE_6 = sid("uni/field-resource/noticeably-intense-6")
F_TENSE_7 = sid("uni/field/tense-7")
FR_TENSE_7 = sid("uni/field-resource/tense-7")
F_VERY_TENSE_8 = sid("uni/field/very-tense-8")
FR_VERY_TENSE_8 = sid("uni/field-resource/very-tense-8")
F_EXTREMELY_INTENSE_9 = sid("uni/field/extremely-intense-9")
FR_EXTREMELY_INTENSE_9 = sid("uni/field-resource/extremely-intense-9")
F_MAXIMUM_INTENSITY_10 = sid("uni/field/maximum-intensity-10")
FR_MAXIMUM_INTENSITY_10 = sid("uni/field-resource/maximum-intensity-10")

INTENSITY_FIELDS = [
    F_VERY_CALM_1,
    F_CALM_2,
    F_MILD_3,
    F_SLIGHTLY_TENSE_4,
    F_MODERATE_5,
    F_NOTICEABLY_INTENSE_6,
    F_TENSE_7,
    F_VERY_TENSE_8,
    F_EXTREMELY_INTENSE_9,
    F_MAXIMUM_INTENSITY_10,
]
INTENSITY_FIELD_RESOURCES = [    FR_VERY_CALM_1,
    FR_CALM_2,
    FR_MILD_3,
    FR_SLIGHTLY_TENSE_4,
    FR_MODERATE_5,
    FR_NOTICEABLY_INTENSE_6,
    FR_TENSE_7,
    FR_VERY_TENSE_8,
    FR_EXTREMELY_INTENSE_9,
    FR_MAXIMUM_INTENSITY_10,
]
INTENSITY_FIELD_RESOURCES = [
    FR_VERY_CALM_1,
    FR_CALM_2,
    FR_MILD_3,
    FR_SLIGHTLY_TENSE_4,
    FR_MODERATE_5,
    FR_NOTICEABLY_INTENSE_6,
    FR_TENSE_7,
    FR_VERY_TENSE_8,
    FR_EXTREMELY_INTENSE_9,
    FR_MAXIMUM_INTENSITY_10,
]

# ── Crowdedness fields (10) ───────────────────────────────────────────────

F_ALMOST_EMPTY_1 = sid("uni/field/almost-empty-1")
FR_ALMOST_EMPTY_1 = sid("uni/field-resource/almost-empty-1")
F_VERY_FEW_STUDENTS_2 = sid("uni/field/very-few-students-2")
FR_VERY_FEW_STUDENTS_2 = sid("uni/field-resource/very-few-students-2")
F_SPARSE_3 = sid("uni/field/sparse-3")
FR_SPARSE_3 = sid("uni/field-resource/sparse-3")
F_SOME_STUDENTS_4 = sid("uni/field/some-students-4")
FR_SOME_STUDENTS_4 = sid("uni/field-resource/some-students-4")
F_MODERATELY_BUSY_5 = sid("uni/field/moderately-busy-5")
FR_MODERATELY_BUSY_5 = sid("uni/field-resource/moderately-busy-5")
F_BUSY_6 = sid("uni/field/busy-6")
FR_BUSY_6 = sid("uni/field-resource/busy-6")
F_VERY_BUSY_7 = sid("uni/field/very-busy-7")
FR_VERY_BUSY_7 = sid("uni/field-resource/very-busy-7")
F_CROWDED_8 = sid("uni/field/crowded-8")
FR_CROWDED_8 = sid("uni/field-resource/crowded-8")
F_EXTREMELY_CROWDED_9 = sid("uni/field/extremely-crowded-9")
FR_EXTREMELY_CROWDED_9 = sid("uni/field-resource/extremely-crowded-9")
F_HECTIC_10 = sid("uni/field/hectic-10")
FR_HECTIC_10 = sid("uni/field-resource/hectic-10")

CROWDEDNESS_FIELDS = [
    F_ALMOST_EMPTY_1,
    F_VERY_FEW_STUDENTS_2,
    F_SPARSE_3,
    F_SOME_STUDENTS_4,
    F_MODERATELY_BUSY_5,
    F_BUSY_6,
    F_VERY_BUSY_7,
    F_CROWDED_8,
    F_EXTREMELY_CROWDED_9,
    F_HECTIC_10,
]
CROWDEDNESS_FIELD_RESOURCES = [    FR_ALMOST_EMPTY_1,
    FR_VERY_FEW_STUDENTS_2,
    FR_SPARSE_3,
    FR_SOME_STUDENTS_4,
    FR_MODERATELY_BUSY_5,
    FR_BUSY_6,
    FR_VERY_BUSY_7,
    FR_CROWDED_8,
    FR_EXTREMELY_CROWDED_9,
    FR_HECTIC_10,
]
CROWDEDNESS_FIELD_RESOURCES = [
    FR_ALMOST_EMPTY_1,
    FR_VERY_FEW_STUDENTS_2,
    FR_SPARSE_3,
    FR_SOME_STUDENTS_4,
    FR_MODERATELY_BUSY_5,
    FR_BUSY_6,
    FR_VERY_BUSY_7,
    FR_CROWDED_8,
    FR_EXTREMELY_CROWDED_9,
    FR_HECTIC_10,
]

# ── Deadline fields (5) ───────────────────────────────────────────────────

F_NO_DEADLINE = sid("uni/field/no-deadline")
FR_NO_DEADLINE = sid("uni/field-resource/no-deadline")
F_END_OF_WEEK = sid("uni/field/end-of-week")
FR_END_OF_WEEK = sid("uni/field-resource/end-of-week")
F_COUPLE_OF_DAYS = sid("uni/field/couple-of-days")
FR_COUPLE_OF_DAYS = sid("uni/field-resource/couple-of-days")
F_NEXT_DAY = sid("uni/field/next-day")
FR_NEXT_DAY = sid("uni/field-resource/next-day")
F_FEW_HOURS = sid("uni/field/few-hours")
FR_FEW_HOURS = sid("uni/field-resource/few-hours")

DEADLINE_FIELDS = [
    F_NO_DEADLINE,
    F_END_OF_WEEK,
    F_COUPLE_OF_DAYS,
    F_NEXT_DAY,
    F_FEW_HOURS,
]
DEADLINE_FIELD_RESOURCES = [    FR_NO_DEADLINE,
    FR_END_OF_WEEK,
    FR_COUPLE_OF_DAYS,
    FR_NEXT_DAY,
    FR_FEW_HOURS,
]
DEADLINE_FIELD_RESOURCES = [
    FR_NO_DEADLINE,
    FR_END_OF_WEEK,
    FR_COUPLE_OF_DAYS,
    FR_NEXT_DAY,
    FR_FEW_HOURS,
]

# ── Time fields (9) ───────────────────────────────────────────────────────

F_900_AM = sid("uni/field/900-am")
FR_900_AM = sid("uni/field-resource/900-am")
F_1000_AM = sid("uni/field/1000-am")
FR_1000_AM = sid("uni/field-resource/1000-am")
F_1100_AM = sid("uni/field/1100-am")
FR_1100_AM = sid("uni/field-resource/1100-am")
F_1200_PM = sid("uni/field/1200-pm")
FR_1200_PM = sid("uni/field-resource/1200-pm")
F_100_PM = sid("uni/field/100-pm")
FR_100_PM = sid("uni/field-resource/100-pm")
F_200_PM = sid("uni/field/200-pm")
FR_200_PM = sid("uni/field-resource/200-pm")
F_300_PM = sid("uni/field/300-pm")
FR_300_PM = sid("uni/field-resource/300-pm")
F_400_PM = sid("uni/field/400-pm")
FR_400_PM = sid("uni/field-resource/400-pm")
F_500_PM = sid("uni/field/500-pm")
FR_500_PM = sid("uni/field-resource/500-pm")

TIME_FIELDS = [
    F_900_AM,
    F_1000_AM,
    F_1100_AM,
    F_1200_PM,
    F_100_PM,
    F_200_PM,
    F_300_PM,
    F_400_PM,
    F_500_PM,
]
TIME_FIELD_RESOURCES = [    FR_900_AM,
    FR_1000_AM,
    FR_1100_AM,
    FR_1200_PM,
    FR_100_PM,
    FR_200_PM,
    FR_300_PM,
    FR_400_PM,
    FR_500_PM,
]
TIME_FIELD_RESOURCES = [
    FR_900_AM,
    FR_1000_AM,
    FR_1100_AM,
    FR_1200_PM,
    FR_100_PM,
    FR_200_PM,
    FR_300_PM,
    FR_400_PM,
    FR_500_PM,
]

# ── Location fields (3) ───────────────────────────────────────────────────

F_LAWSON = sid("uni/field/lawson-computer-science-building")
FR_LAWSON = sid("uni/field-resource/lawson-computer-science-building")
F_FELIX_HAAS = sid("uni/field/felix-haas-hall")
FR_FELIX_HAAS = sid("uni/field-resource/felix-haas-hall")
F_DSAI = sid("uni/field/data-science-and-ai-building")
FR_DSAI = sid("uni/field-resource/data-science-and-ai-building")

LOCATION_FIELDS = [F_LAWSON, F_FELIX_HAAS, F_DSAI]
LOCATION_FIELD_RESOURCES = [FR_LAWSON, FR_FELIX_HAAS, FR_DSAI]

# ── Class fields (7) ──────────────────────────────────────────────────────

F_CS_180 = sid("uni/field/cs-180")
FR_CS_180 = sid("uni/field-resource/cs-180")
F_CS_182 = sid("uni/field/cs-182")
FR_CS_182 = sid("uni/field-resource/cs-182")
F_CS_242 = sid("uni/field/cs-242")
FR_CS_242 = sid("uni/field-resource/cs-242")
F_CS_251 = sid("uni/field/cs-251")
FR_CS_251 = sid("uni/field-resource/cs-251")
F_CS_373 = sid("uni/field/cs-373")
FR_CS_373 = sid("uni/field-resource/cs-373")
F_CS_381 = sid("uni/field/cs-381")
FR_CS_381 = sid("uni/field-resource/cs-381")
F_CS_422 = sid("uni/field/cs-422")
FR_CS_422 = sid("uni/field-resource/cs-422")

CLASS_FIELDS = [F_CS_180, F_CS_182, F_CS_242, F_CS_251, F_CS_373, F_CS_381, F_CS_422]
CLASS_FIELD_RESOURCES = [FR_CS_180, FR_CS_182, FR_CS_242, FR_CS_251, FR_CS_373, FR_CS_381, FR_CS_422]

# ── Document Type fields (8) ──────────────────────────────────────────────

F_HOMEWORK = sid("uni/field/homework")
FR_HOMEWORK = sid("uni/field-resource/homework")
F_LAB = sid("uni/field/lab")
FR_LAB = sid("uni/field-resource/lab")
F_LECTURE = sid("uni/field/lecture")
FR_LECTURE = sid("uni/field-resource/lecture")
F_MIDTERM = sid("uni/field/midterm")
FR_MIDTERM = sid("uni/field-resource/midterm")
F_POLICY = sid("uni/field/policy")
FR_POLICY = sid("uni/field-resource/policy")
F_PROJECT = sid("uni/field/project")
FR_PROJECT = sid("uni/field-resource/project")
F_QUIZ = sid("uni/field/quiz")
FR_QUIZ = sid("uni/field-resource/quiz")
F_SYLLABUS = sid("uni/field/syllabus")
FR_SYLLABUS = sid("uni/field-resource/syllabus")

DOCUMENT_TYPE_FIELDS = [
    F_HOMEWORK,
    F_LAB,
    F_LECTURE,
    F_MIDTERM,
    F_POLICY,
    F_PROJECT,
    F_QUIZ,
    F_SYLLABUS,
]
DOCUMENT_TYPE_FIELD_RESOURCES = [    FR_HOMEWORK,
    FR_LAB,
    FR_LECTURE,
    FR_MIDTERM,
    FR_POLICY,
    FR_PROJECT,
    FR_QUIZ,
    FR_SYLLABUS,
]
DOCUMENT_TYPE_FIELD_RESOURCES = [
    FR_HOMEWORK,
    FR_LAB,
    FR_LECTURE,
    FR_MIDTERM,
    FR_POLICY,
    FR_PROJECT,
    FR_QUIZ,
    FR_SYLLABUS,
]

# ── Concepts fields (5) ──────────────────────────────────────────────────

F_ANNUAL_FERPA = sid("uni/field/annual-ferpa-rights-notification")
FR_ANNUAL_FERPA = sid("uni/field-resource/annual-ferpa-rights-notification")
F_CONSENT_DISCLOSURES = sid("uni/field/consent-vs-no-consent-disclosures")
FR_CONSENT_DISCLOSURES = sid("uni/field-resource/consent-vs-no-consent-disclosures")
F_EDUCATION_RECORDS = sid("uni/field/education-records-exceptions")
FR_EDUCATION_RECORDS = sid("uni/field-resource/education-records-exceptions")
F_RECORD_AMENDMENT = sid("uni/field/record-amendment-process")
FR_RECORD_AMENDMENT = sid("uni/field-resource/record-amendment-process")
F_STUDENT_ACCESS = sid("uni/field/student-access-rights")
FR_STUDENT_ACCESS = sid("uni/field-resource/student-access-rights")

CONCEPTS_FIELDS = [
    F_ANNUAL_FERPA,
    F_CONSENT_DISCLOSURES,
    F_EDUCATION_RECORDS,
    F_RECORD_AMENDMENT,
    F_STUDENT_ACCESS,
]
CONCEPTS_FIELD_RESOURCES = [    FR_ANNUAL_FERPA,
    FR_CONSENT_DISCLOSURES,
    FR_EDUCATION_RECORDS,
    FR_RECORD_AMENDMENT,
    FR_STUDENT_ACCESS,
]
CONCEPTS_FIELD_RESOURCES = [
    FR_ANNUAL_FERPA,
    FR_CONSENT_DISCLOSURES,
    FR_EDUCATION_RECORDS,
    FR_RECORD_AMENDMENT,
    FR_STUDENT_ACCESS,
]

# ── Role fields (3) ──────────────────────────────────────────────────────

F_STUDENT = sid("uni/field/student")
FR_STUDENT = sid("uni/field-resource/student")
F_PROFESSOR = sid("uni/field/professor")
FR_PROFESSOR = sid("uni/field-resource/professor")
F_INSTRUCTIONAL_STAFF = sid("uni/field/instructional-staff")
FR_INSTRUCTIONAL_STAFF = sid("uni/field-resource/instructional-staff")

ROLE_FIELDS = [F_STUDENT, F_PROFESSOR, F_INSTRUCTIONAL_STAFF]
ROLE_FIELD_RESOURCES = [FR_STUDENT, FR_PROFESSOR, FR_INSTRUCTIONAL_STAFF]

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

fields = [
    # ── Temperament ────────────────────────────────────────────────────────
    dict(
        id=F_AGGRESSIVE,
        resource_id=sid("uni/field-resource/aggressive"),
        name="aggressive",
        description="Pushes back on ideas and challenges assumptions",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CONFUSED,
        resource_id=sid("uni/field-resource/confused"),
        name="confused",
        description="Seeks to understand by asking questions and exploring ideas",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_HAPPY,
        resource_id=sid("uni/field-resource/happy"),
        name="happy",
        description="Provides uplifting feedback and cheerful responses",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_PASSIVE,
        resource_id=sid("uni/field-resource/passive"),
        name="passive",
        description="Low engagement and tendency to avoid conflict or assertiveness",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Persona Type ──────────────────────────────────────────────────────
    dict(
        id=F_EMOTION,
        resource_id=sid("uni/field-resource/emotion"),
        name="Emotion",
        description="Personas with emotional temperaments (aggressive, passive, confused, happy)",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_NEUTRAL,
        resource_id=sid("uni/field-resource/neutral"),
        name="Neutral",
        description="Personas with neutral roles (Student, Professor, Instructional Staff)",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Intensity ─────────────────────────────────────────────────────────
    dict(
        id=F_VERY_CALM_1,
        resource_id=sid("uni/field-resource/very-calm-1"),
        name="Very Calm (1)",
        description="The conversation is relaxed, with no signs of stress or urgency.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CALM_2,
        resource_id=sid("uni/field-resource/calm-2"),
        name="Calm (2)",
        description="The conversation is easygoing, with minimal tension or pressure.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_MILD_3,
        resource_id=sid("uni/field-resource/mild-3"),
        name="Mild (3)",
        description="The conversation is mostly relaxed, but with occasional hints of concern or focus.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_SLIGHTLY_TENSE_4,
        resource_id=sid("uni/field-resource/slightly-tense-4"),
        name="Slightly Tense (4)",
        description="There is some urgency or emotional energy, but it remains manageable.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_MODERATE_5,
        resource_id=sid("uni/field-resource/moderate-5"),
        name="Moderate (5)",
        description="The conversation is active, with clear engagement and some stress or excitement.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_NOTICEABLY_INTENSE_6,
        resource_id=sid("uni/field-resource/noticeably-intense-6"),
        name="Noticeably Intense (6)",
        description="The conversation is energetic, with raised voices or strong emotions.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_TENSE_7,
        resource_id=sid("uni/field-resource/tense-7"),
        name="Tense (7)",
        description="The conversation is heated, with clear signs of frustration, urgency, or pressure.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_VERY_TENSE_8,
        resource_id=sid("uni/field-resource/very-tense-8"),
        name="Very Tense (8)",
        description="The conversation is highly charged, with strong emotions and little calm.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_EXTREMELY_INTENSE_9,
        resource_id=sid("uni/field-resource/extremely-intense-9"),
        name="Extremely Intense (9)",
        description="The conversation is on the verge of conflict, with high stress and urgency.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_MAXIMUM_INTENSITY_10,
        resource_id=sid("uni/field-resource/maximum-intensity-10"),
        name="Maximum Intensity (10)",
        description="The conversation is explosive, with overwhelming emotion or confrontation.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Crowdedness ───────────────────────────────────────────────────────
    dict(
        id=F_ALMOST_EMPTY_1,
        resource_id=sid("uni/field-resource/almost-empty-1"),
        name="Almost Empty (1)",
        description="There are almost no students present; the room is quiet and you can get help immediately.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_VERY_FEW_STUDENTS_2,
        resource_id=sid("uni/field-resource/very-few-students-2"),
        name="Very Few Students (2)",
        description="Only a couple of students are present; no wait for help.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_SPARSE_3,
        resource_id=sid("uni/field-resource/sparse-3"),
        name="Sparse (3)",
        description="A few students scattered around; very short or no wait.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_SOME_STUDENTS_4,
        resource_id=sid("uni/field-resource/some-students-4"),
        name="Some Students (4)",
        description="Several students are present, but it is still easy to get help.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_MODERATELY_BUSY_5,
        resource_id=sid("uni/field-resource/moderately-busy-5"),
        name="Moderately Busy (5)",
        description="A moderate number of students; you may have to wait a bit for help.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_BUSY_6,
        resource_id=sid("uni/field-resource/busy-6"),
        name="Busy (6)",
        description="The room is active with many students; expect a noticeable wait.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_VERY_BUSY_7,
        resource_id=sid("uni/field-resource/very-busy-7"),
        name="Very Busy (7)",
        description="There is a line of students waiting for help; the room feels crowded.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CROWDED_8,
        resource_id=sid("uni/field-resource/crowded-8"),
        name="Crowded (8)",
        description="The room is packed, and you will have to wait a significant amount of time.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_EXTREMELY_CROWDED_9,
        resource_id=sid("uni/field-resource/extremely-crowded-9"),
        name="Extremely Crowded (9)",
        description="There are many students and a long line; it is difficult to get help.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_HECTIC_10,
        resource_id=sid("uni/field-resource/hectic-10"),
        name="Hectic (10)",
        description="The room is overflowing with students, with a hectic atmosphere and a very long wait.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Deadline ──────────────────────────────────────────────────────────
    dict(
        id=F_NO_DEADLINE,
        resource_id=sid("uni/field-resource/no-deadline"),
        name="No deadline",
        description="There is no specific deadline. The situation is relaxed and stress-free.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_END_OF_WEEK,
        resource_id=sid("uni/field-resource/end-of-week"),
        name="End of week",
        description="Deadline is at the end of the week. Ample time remains; stress is minimal.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_COUPLE_OF_DAYS,
        resource_id=sid("uni/field-resource/couple-of-days"),
        name="Couple of days",
        description="Deadline is in a couple of days. Some urgency, but stress is low.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_NEXT_DAY,
        resource_id=sid("uni/field-resource/next-day"),
        name="Next day",
        description="Deadline is tomorrow. Prompt help is needed; this is a moderate-stress situation.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_FEW_HOURS,
        resource_id=sid("uni/field-resource/few-hours"),
        name="Few hours",
        description="Deadline is in a few hours. Immediate help is required; this is a high-stress situation.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Time ──────────────────────────────────────────────────────────────
    dict(
        id=F_900_AM,
        resource_id=sid("uni/field-resource/900-am"),
        name="9:00 AM",
        description="Early morning session, students may be tired but focused.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_1000_AM,
        resource_id=sid("uni/field-resource/1000-am"),
        name="10:00 AM",
        description="Mid-morning session, good energy levels.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_1100_AM,
        resource_id=sid("uni/field-resource/1100-am"),
        name="11:00 AM",
        description="Late morning session, students are alert and engaged.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_1200_PM,
        resource_id=sid("uni/field-resource/1200-pm"),
        name="12:00 PM",
        description="Lunch time session, students may be hungry or rushed.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_100_PM,
        resource_id=sid("uni/field-resource/100-pm"),
        name="1:00 PM",
        description="Early afternoon session, post-lunch energy dip possible.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_200_PM,
        resource_id=sid("uni/field-resource/200-pm"),
        name="2:00 PM",
        description="Mid-afternoon session, good focus time.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_300_PM,
        resource_id=sid("uni/field-resource/300-pm"),
        name="3:00 PM",
        description="Late afternoon session, sustained energy needed.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_400_PM,
        resource_id=sid("uni/field-resource/400-pm"),
        name="4:00 PM",
        description="Evening session, students may be tired from the day.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_500_PM,
        resource_id=sid("uni/field-resource/500-pm"),
        name="5:00 PM",
        description="End of day session, students eager to finish.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Location ──────────────────────────────────────────────────────────
    dict(
        id=F_LAWSON,
        resource_id=sid("uni/field-resource/lawson-computer-science-building"),
        name="Lawson Computer Science Building",
        description="An open, collaborative space in the Lawson building with high foot traffic.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_FELIX_HAAS,
        resource_id=sid("uni/field-resource/felix-haas-hall"),
        name="Felix Haas Hall",
        description="A quiet, focused study environment in the lower level of the HAAS building.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_DSAI,
        resource_id=sid("uni/field-resource/data-science-and-ai-building"),
        name="Data Science and Artificial Intelligence Building",
        description="A specialized tech-focused lab environment in the basement of the Data Science/AI building.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Class ─────────────────────────────────────────────────────────────
    dict(
        id=F_CS_180,
        resource_id=sid("uni/field-resource/cs-180"),
        name="CS 180",
        description="Problem solving and algorithms, implementation of algorithms in a high level programming language.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CS_182,
        resource_id=sid("uni/field-resource/cs-182"),
        name="CS 182",
        description="Logic and proofs; sets, functions, relations, sequences and summations; counting; analysis of algorithms.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CS_242,
        resource_id=sid("uni/field-resource/cs-242"),
        name="CS 242",
        description="Data Science",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CS_251,
        resource_id=sid("uni/field-resource/cs-251"),
        name="CS 251",
        description="Running time analysis of algorithms, data structures, trees, heaps, sorting, hash tables, graphs.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CS_373,
        resource_id=sid("uni/field-resource/cs-373"),
        name="CS 373",
        description="Introduction to machine learning algorithms, neural networks, feature engineering, and model evaluation.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CS_381,
        resource_id=sid("uni/field-resource/cs-381"),
        name="CS 381",
        description="Techniques for analyzing time and space requirements of algorithms. Sorting, searching, graph problems, NP-hard problems.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CS_422,
        resource_id=sid("uni/field-resource/cs-422"),
        name="CS 422",
        description="Network protocols, socket programming, network security, distributed systems, and network performance analysis.",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Document Type ─────────────────────────────────────────────────────
    dict(
        id=F_HOMEWORK,
        resource_id=sid("uni/field-resource/homework"),
        name="homework",
        description="Assignments, problem sets, exercises",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_LAB,
        resource_id=sid("uni/field-resource/lab"),
        name="lab",
        description="Laboratory exercises, practical work",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_LECTURE,
        resource_id=sid("uni/field-resource/lecture"),
        name="lecture",
        description="Lecture notes, slides, presentations",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_MIDTERM,
        resource_id=sid("uni/field-resource/midterm"),
        name="midterm",
        description="Midterm exams, major tests",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_POLICY,
        resource_id=sid("uni/field-resource/policy"),
        name="policy",
        description="Policy documents, guidelines, and regulations",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_PROJECT,
        resource_id=sid("uni/field-resource/project"),
        name="project",
        description="Large assignments, final projects, group work",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_QUIZ,
        resource_id=sid("uni/field-resource/quiz"),
        name="quiz",
        description="Short assessments, pop quizzes",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_SYLLABUS,
        resource_id=sid("uni/field-resource/syllabus"),
        name="syllabus",
        description="Course syllabus, course outline",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Concepts (FERPA) ──────────────────────────────────────────────────
    dict(
        id=F_ANNUAL_FERPA,
        resource_id=sid("uni/field-resource/annual-ferpa-rights-notification"),
        name="Annual FERPA Rights Notification",
        description="Annual notification requirements for FERPA rights",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_CONSENT_DISCLOSURES,
        resource_id=sid("uni/field-resource/consent-vs-no-consent-disclosures"),
        name="Consent vs. No-Consent Disclosures",
        description="Understanding when consent is required vs. when disclosure is allowed without consent",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_EDUCATION_RECORDS,
        resource_id=sid("uni/field-resource/education-records-exceptions"),
        name="Education Records & Exceptions",
        description="Understanding what constitutes education records and exceptions under FERPA",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_RECORD_AMENDMENT,
        resource_id=sid("uni/field-resource/record-amendment-process"),
        name="Record Amendment Process",
        description="Process for students to request amendment of education records",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_STUDENT_ACCESS,
        resource_id=sid("uni/field-resource/student-access-rights"),
        name="Student Access Rights",
        description="Rights students have to access their education records",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    # ── Role ──────────────────────────────────────────────────────────────
    dict(
        id=F_STUDENT,
        resource_id=sid("uni/field-resource/student"),
        name="Student",
        description="Represents a typical student perspective",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_PROFESSOR,
        resource_id=sid("uni/field-resource/professor"),
        name="Professor",
        description="Represents a faculty member perspective",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
    dict(
        id=F_INSTRUCTIONAL_STAFF,
        resource_id=sid("uni/field-resource/instructional-staff"),
        name="Instructional Staff",
        description="Represents teaching assistants and instructional support staff",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    ),
]
