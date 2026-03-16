"""Entry type → materialized view name mapping."""

ENTRY_VIEW_NAMES: dict[str, str] = {
    "analyses": "attempt_analysis_mv",
    "contents": "attempt_content_mv",
    "feedbacks": "attempt_feedback_mv",
    "grades": "attempt_grade_mv",
    "highlights": "attempt_highlight_mv",
    "hints": "attempt_hint_mv",
    "improvements": "attempt_improvement_mv",
    "replacements": "attempt_replacement_mv",
    "attempt_responses": "attempt_responses_mv",
    "strengths": "attempt_strength_mv",
}
