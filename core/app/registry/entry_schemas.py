"""Per-entry-type column schemas for tool-targetable entries.

Only includes entry types reachable via entry_tools_relation or tool_bindings_junction.
Business columns only — excludes system columns (id, created_at, active, generated, mcp).

Entry type keys match the entry_type enum values (unprefixed).
For highlights/replacements, columns come from the standalone tables (not attempt_* variants).

Type strings: text, int, float, numeric, bool, uuid, array, enum, timestamp
"""

ENTRY_SCHEMAS: dict[str, dict[str, str]] = {
    "analyses": {
        "grade_id": "uuid",
        "content": "text",
        "updated_at": "timestamp",
        "call_id": "uuid",
    },
    "contents": {
        "message_id": "uuid",
        "updated_at": "timestamp",
        "content": "text",
        "call_id": "uuid",
        "persona_id": "uuid",
    },
    "feedbacks": {
        "grade_id": "uuid",
        "total": "int",
        "feedback": "text",
        "updated_at": "timestamp",
        "call_id": "uuid",
    },
    "grades": {
        "chat_id": "uuid",
        "run_id": "uuid",
        "updated_at": "timestamp",
        "passed": "bool",
        "score": "int",
        "time_taken": "int",
    },
    "highlights": {
        "strength_id": "uuid",
        "section": "text",
        "idx": "int",
        "updated_at": "timestamp",
    },
    "hints": {
        "message_id": "uuid",
        "hint": "text",
        "updated_at": "timestamp",
        "call_id": "uuid",
    },
    "improvements": {
        "grade_id": "uuid",
        "message_id": "uuid",
        "name": "text",
        "description": "text",
        "updated_at": "timestamp",
        "call_id": "uuid",
    },
    "replacements": {
        "improvement_id": "uuid",
        "section": "text",
        "replace": "text",
        "idx": "int",
        "updated_at": "timestamp",
    },
    "attempt_responses": {
        "chat_id": "uuid",
        "updated_at": "timestamp",
        "call_id": "uuid",
    },
    "strengths": {
        "grade_id": "uuid",
        "message_id": "uuid",
        "name": "text",
        "description": "text",
        "updated_at": "timestamp",
        "call_id": "uuid",
    },
}
