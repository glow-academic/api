"""University scenario content — objectives, questions, and options.

These are resource-level creates that must run BEFORE scenarios,
since scenarios reference them via objective_ids, question_ids, option_ids.

Options are linked to their parent question via question_id.
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

# ── Academic Integrity Objectives ──────────────────────────────────────────

AI_OBJ_IDENTIFY = sid("uni/objective/ai-identify-violation")
AI_OBJ_COMMUNICATE = sid("uni/objective/ai-communicate-consequences")
AI_OBJ_APPLY_POLICY = sid("uni/objective/ai-apply-policy")

# ── FERPA Objectives ──────────────────────────────────────────────────────

FERPA_OBJ_IDENTIFY = sid("uni/objective/ferpa-identify-violation")
FERPA_OBJ_REMEDIATE = sid("uni/objective/ferpa-remediate")
FERPA_OBJ_EXPLAIN = sid("uni/objective/ferpa-explain-rights")

# ── Upset Student Objectives ──────────────────────────────────────────────

UPSET_OBJ_LISTEN = sid("uni/objective/upset-active-listening")
UPSET_OBJ_DEESCALATE = sid("uni/objective/upset-deescalate")
UPSET_OBJ_RESOLVE = sid("uni/objective/upset-resolve")

# ── Academic Integrity Questions ──────────────────────────────────────────

AI_Q_FIRST_STEP = sid("uni/question/ai-first-step")
AI_Q_CONSEQUENCE = sid("uni/question/ai-consequence")

# ── FERPA Questions ───────────────────────────────────────────────────────

FERPA_Q_WHAT_IS = sid("uni/question/ferpa-what-is")
FERPA_Q_VIOLATION = sid("uni/question/ferpa-violation-example")

# ── Upset Student Questions ───────────────────────────────────────────────

UPSET_Q_FIRST_RESPONSE = sid("uni/question/upset-first-response")
UPSET_Q_TECHNIQUE = sid("uni/question/upset-technique")

# ── Academic Integrity Options ────────────────────────────────────────────

AI_OPT_FIRST_STEP_A = sid("uni/option/ai-first-step-a")
AI_OPT_FIRST_STEP_B = sid("uni/option/ai-first-step-b")
AI_OPT_FIRST_STEP_C = sid("uni/option/ai-first-step-c")
AI_OPT_CONSEQUENCE_A = sid("uni/option/ai-consequence-a")
AI_OPT_CONSEQUENCE_B = sid("uni/option/ai-consequence-b")
AI_OPT_CONSEQUENCE_C = sid("uni/option/ai-consequence-c")

# ── FERPA Options ─────────────────────────────────────────────────────────

FERPA_OPT_WHAT_IS_A = sid("uni/option/ferpa-what-is-a")
FERPA_OPT_WHAT_IS_B = sid("uni/option/ferpa-what-is-b")
FERPA_OPT_WHAT_IS_C = sid("uni/option/ferpa-what-is-c")
FERPA_OPT_VIOLATION_A = sid("uni/option/ferpa-violation-a")
FERPA_OPT_VIOLATION_B = sid("uni/option/ferpa-violation-b")
FERPA_OPT_VIOLATION_C = sid("uni/option/ferpa-violation-c")

# ── Upset Student Options ─────────────────────────────────────────────────

UPSET_OPT_FIRST_A = sid("uni/option/upset-first-a")
UPSET_OPT_FIRST_B = sid("uni/option/upset-first-b")
UPSET_OPT_FIRST_C = sid("uni/option/upset-first-c")
UPSET_OPT_TECHNIQUE_A = sid("uni/option/upset-technique-a")
UPSET_OPT_TECHNIQUE_B = sid("uni/option/upset-technique-b")
UPSET_OPT_TECHNIQUE_C = sid("uni/option/upset-technique-c")

# ---------------------------------------------------------------------------
# Grouped IDs for convenient import by scenarios.py
# ---------------------------------------------------------------------------

ACADEMIC_INTEGRITY_OBJECTIVES = [
    AI_OBJ_IDENTIFY,
    AI_OBJ_COMMUNICATE,
    AI_OBJ_APPLY_POLICY,
]
ACADEMIC_INTEGRITY_QUESTIONS = [AI_Q_FIRST_STEP, AI_Q_CONSEQUENCE]
ACADEMIC_INTEGRITY_OPTIONS = [
    AI_OPT_FIRST_STEP_A,
    AI_OPT_FIRST_STEP_B,
    AI_OPT_FIRST_STEP_C,
    AI_OPT_CONSEQUENCE_A,
    AI_OPT_CONSEQUENCE_B,
    AI_OPT_CONSEQUENCE_C,
]

FERPA_OBJECTIVES = [FERPA_OBJ_IDENTIFY, FERPA_OBJ_REMEDIATE, FERPA_OBJ_EXPLAIN]
FERPA_QUESTIONS = [FERPA_Q_WHAT_IS, FERPA_Q_VIOLATION]
FERPA_OPTIONS = [
    FERPA_OPT_WHAT_IS_A,
    FERPA_OPT_WHAT_IS_B,
    FERPA_OPT_WHAT_IS_C,
    FERPA_OPT_VIOLATION_A,
    FERPA_OPT_VIOLATION_B,
    FERPA_OPT_VIOLATION_C,
]

UPSET_STUDENT_OBJECTIVES = [UPSET_OBJ_LISTEN, UPSET_OBJ_DEESCALATE, UPSET_OBJ_RESOLVE]
UPSET_STUDENT_QUESTIONS = [UPSET_Q_FIRST_RESPONSE, UPSET_Q_TECHNIQUE]
UPSET_STUDENT_OPTIONS = [
    UPSET_OPT_FIRST_A,
    UPSET_OPT_FIRST_B,
    UPSET_OPT_FIRST_C,
    UPSET_OPT_TECHNIQUE_A,
    UPSET_OPT_TECHNIQUE_B,
    UPSET_OPT_TECHNIQUE_C,
]

# ---------------------------------------------------------------------------
# Objective definitions
# ---------------------------------------------------------------------------

objectives = [
    # Academic Integrity
    dict(
        id=AI_OBJ_IDENTIFY,
        objective="Identify indicators of academic integrity violations during examinations",
    ),
    dict(
        id=AI_OBJ_COMMUNICATE,
        objective="Communicate consequences of academic dishonesty clearly and professionally",
    ),
    dict(
        id=AI_OBJ_APPLY_POLICY,
        objective="Apply the institution's academic integrity policy accurately",
    ),
    # FERPA
    dict(
        id=FERPA_OBJ_IDENTIFY,
        objective="Identify situations that constitute FERPA violations",
    ),
    dict(
        id=FERPA_OBJ_REMEDIATE,
        objective="Take immediate corrective action when a privacy breach occurs",
    ),
    dict(
        id=FERPA_OBJ_EXPLAIN,
        objective="Explain student privacy rights under FERPA clearly",
    ),
    # Upset Student
    dict(
        id=UPSET_OBJ_LISTEN,
        objective="Demonstrate active listening when a student expresses frustration",
    ),
    dict(
        id=UPSET_OBJ_DEESCALATE,
        objective="Apply de-escalation techniques to reduce emotional tension",
    ),
    dict(
        id=UPSET_OBJ_RESOLVE,
        objective="Guide the conversation toward a constructive resolution",
    ),
]

# ---------------------------------------------------------------------------
# Question definitions
# ---------------------------------------------------------------------------

questions = [
    # Academic Integrity
    dict(
        id=AI_Q_FIRST_STEP,
        question_text="What is the appropriate first step when you observe a potential academic integrity violation?",
        time=60,
    ),
    dict(
        id=AI_Q_CONSEQUENCE,
        question_text="Which of the following is an appropriate consequence for a first-time academic integrity offense?",
        time=60,
    ),
    # FERPA
    dict(
        id=FERPA_Q_WHAT_IS,
        question_text="What does FERPA protect?",
        time=45,
    ),
    dict(
        id=FERPA_Q_VIOLATION,
        question_text="Which of the following scenarios constitutes a FERPA violation?",
        time=60,
    ),
    # Upset Student
    dict(
        id=UPSET_Q_FIRST_RESPONSE,
        question_text="A student arrives at your office visibly upset about a grade. What should your first response be?",
        time=60,
    ),
    dict(
        id=UPSET_Q_TECHNIQUE,
        question_text="Which de-escalation technique is most appropriate when a student raises their voice?",
        time=60,
    ),
]

# ---------------------------------------------------------------------------
# Option definitions (linked to parent questions)
# ---------------------------------------------------------------------------

options = [
    # Academic Integrity — First Step
    dict(
        id=AI_OPT_FIRST_STEP_A,
        option_text="Document the observation and report to the department chair",
        question_id=AI_Q_FIRST_STEP,
    ),
    dict(
        id=AI_OPT_FIRST_STEP_B,
        option_text="Immediately confront the student in front of the class",
        question_id=AI_Q_FIRST_STEP,
    ),
    dict(
        id=AI_OPT_FIRST_STEP_C,
        option_text="Ignore it unless you have definitive proof",
        question_id=AI_Q_FIRST_STEP,
    ),
    # Academic Integrity — Consequence
    dict(
        id=AI_OPT_CONSEQUENCE_A,
        option_text="A formal warning and required academic integrity seminar",
        question_id=AI_Q_CONSEQUENCE,
    ),
    dict(
        id=AI_OPT_CONSEQUENCE_B,
        option_text="Immediate expulsion from the university",
        question_id=AI_Q_CONSEQUENCE,
    ),
    dict(
        id=AI_OPT_CONSEQUENCE_C,
        option_text="No action unless the student admits to cheating",
        question_id=AI_Q_CONSEQUENCE,
    ),
    # FERPA — What is
    dict(
        id=FERPA_OPT_WHAT_IS_A,
        option_text="The privacy of student education records",
        question_id=FERPA_Q_WHAT_IS,
    ),
    dict(
        id=FERPA_OPT_WHAT_IS_B,
        option_text="Faculty employment contracts",
        question_id=FERPA_Q_WHAT_IS,
    ),
    dict(
        id=FERPA_OPT_WHAT_IS_C,
        option_text="University financial records",
        question_id=FERPA_Q_WHAT_IS,
    ),
    # FERPA — Violation
    dict(
        id=FERPA_OPT_VIOLATION_A,
        option_text="Discussing a student's grades with their parent without consent",
        question_id=FERPA_Q_VIOLATION,
    ),
    dict(
        id=FERPA_OPT_VIOLATION_B,
        option_text="Posting anonymous assignment feedback on the LMS",
        question_id=FERPA_Q_VIOLATION,
    ),
    dict(
        id=FERPA_OPT_VIOLATION_C,
        option_text="Sharing aggregated class performance statistics",
        question_id=FERPA_Q_VIOLATION,
    ),
    # Upset Student — First Response
    dict(
        id=UPSET_OPT_FIRST_A,
        option_text="Acknowledge their feelings and invite them to share their concerns",
        question_id=UPSET_Q_FIRST_RESPONSE,
    ),
    dict(
        id=UPSET_OPT_FIRST_B,
        option_text="Explain the grading rubric before they finish speaking",
        question_id=UPSET_Q_FIRST_RESPONSE,
    ),
    dict(
        id=UPSET_OPT_FIRST_C,
        option_text="Tell them to come back when they have calmed down",
        question_id=UPSET_Q_FIRST_RESPONSE,
    ),
    # Upset Student — Technique
    dict(
        id=UPSET_OPT_TECHNIQUE_A,
        option_text="Speak calmly, lower your voice, and use open body language",
        question_id=UPSET_Q_TECHNIQUE,
    ),
    dict(
        id=UPSET_OPT_TECHNIQUE_B,
        option_text="Match their volume to show you take them seriously",
        question_id=UPSET_Q_TECHNIQUE,
    ),
    dict(
        id=UPSET_OPT_TECHNIQUE_C,
        option_text="Ask them to leave and send an email instead",
        question_id=UPSET_Q_TECHNIQUE,
    ),
]
