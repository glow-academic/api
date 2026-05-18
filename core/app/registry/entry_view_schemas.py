"""Per-entry-type materialized view schemas.

Each tool-targetable entry type has a corresponding MV that consumers read from.
These schemas represent the SELECT columns of each MV — distinct from ENTRY_SCHEMAS
which represent the table columns tools write to.

Differences from ENTRY_SCHEMAS:
- IDs renamed: entry.id → {type}_id (e.g. analysis_id, content_id)
- Joined columns added (e.g. standard_id on feedbacks, question_id/option_id on attempt_responses)
- Computed columns (e.g. idx via ROW_NUMBER on contents/hints)
- Type casts (e.g. total::float on feedbacks, score::float on grades)
- Internal columns dropped (e.g. call_id, updated_at filtered out by most MVs)

MV name mapping:
  analyses       → attempt_analysis_mv
  contents       → attempt_content_mv
  feedbacks      → attempt_feedback_mv
  grades         → attempt_grade_mv
  highlights     → attempt_highlight_mv
  hints          → attempt_hint_mv
  improvements   → attempt_improvement_mv
  replacements   → attempt_replacement_mv
  attempt_responses → attempt_responses_mv
  strengths      → attempt_strength_mv

Type strings: text, int, float, numeric, bool, uuid, array, enum, timestamp
"""

ENTRY_VIEW_SCHEMAS: dict[str, dict[str, str]] = {
    "analyses": {
        "analysis_id": "uuid",
        "grade_id": "uuid",
        "content": "text",
        "created_at": "timestamp",
    },
    "contents": {
        "content_id": "uuid",
        "message_id": "uuid",
        "content": "text",
        "persona_entry_id": "uuid",
        "idx": "int",
        "created_at": "timestamp",
    },
    "feedbacks": {
        "feedback_id": "uuid",
        "grade_id": "uuid",
        "standard_id": "uuid",
        "total": "float",
        "feedback": "text",
        "created_at": "timestamp",
    },
    "grades": {
        "grade_id": "uuid",
        "chat_id": "uuid",
        "score": "float",
        "passed": "bool",
        "time_taken": "int",
        "total_points": "int",
        "pass_points": "int",
        "rubric_id": "uuid",
        "created_at": "timestamp",
    },
    "highlights": {
        "highlight_id": "uuid",
        "strength_id": "uuid",
        "section": "text",
        "idx": "int",
        "created_at": "timestamp",
    },
    "hints": {
        "hint_id": "uuid",
        "message_id": "uuid",
        "hint": "text",
        "idx": "int",
        "created_at": "timestamp",
    },
    "improvements": {
        "improvement_id": "uuid",
        "message_id": "uuid",
        "name": "text",
        "description": "text",
        "created_at": "timestamp",
    },
    "replacements": {
        "replacement_id": "uuid",
        "improvement_id": "uuid",
        "section": "text",
        "replace_text": "text",
        "idx": "int",
        "created_at": "timestamp",
    },
    "attempt_responses": {
        "response_id": "uuid",
        "chat_id": "uuid",
        "question_id": "uuid",
        "option_id": "uuid",
        "created_at": "timestamp",
    },
    "strengths": {
        "strength_id": "uuid",
        "message_id": "uuid",
        "grade_id": "uuid",
        "name": "text",
        "description": "text",
        "created_at": "timestamp",
    },
}
