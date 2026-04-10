"""Shared args_output resource seeds.

Each args_output maps an input arg to an API field via a Jinja template.
Tools reference args_outputs by key instead of defining them inline.

Naming convention:
  - Payload outputs: named after the API field they target (e.g., "name", "description")
  - Routing outputs: "artifact" and "operation" determine which infra function to call

Routing variants:
  - *_passthrough: template="{{ x }}" — LLM explicitly specifies the value
  - *_<value>:     template="<value>" — hardcoded constant for single-permission tools
"""

from database.seeds.ids import sid

# The args_id for routing outputs points to the shared "artifact" and "operation" args.
_ARTIFACT_ARG_ID = sid("arg/artifact")
_OPERATION_ARG_ID = sid("arg/operation")

SHARED_ARGS_OUTPUTS = {
    # --- Routing: pass-through (for multi-permission tools) ---
    "artifact_passthrough": dict(
        id=sid("args_output/artifact_passthrough"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="{{ artifact }}",
    ),
    "operation_passthrough": dict(
        id=sid("args_output/operation_passthrough"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="{{ operation }}",
    ),
    # --- Routing: hardcoded operations ---
    "operation_create": dict(
        id=sid("args_output/operation_create"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="create",
    ),
    "operation_update": dict(
        id=sid("args_output/operation_update"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="update",
    ),
    "operation_delete": dict(
        id=sid("args_output/operation_delete"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="delete",
    ),
    "operation_search": dict(
        id=sid("args_output/operation_search"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="search",
    ),
    "operation_get": dict(
        id=sid("args_output/operation_get"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="get",
    ),
    # --- Routing: hardcoded artifacts ---
    "artifact_agent": dict(
        id=sid("args_output/artifact_agent"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="agent",
    ),
    "artifact_persona": dict(
        id=sid("args_output/artifact_persona"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="persona",
    ),
    "artifact_scenario": dict(
        id=sid("args_output/artifact_scenario"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="scenario",
    ),
    "artifact_simulation": dict(
        id=sid("args_output/artifact_simulation"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="simulation",
    ),
    "artifact_document": dict(
        id=sid("args_output/artifact_document"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="document",
    ),
    "artifact_rubric": dict(
        id=sid("args_output/artifact_rubric"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="rubric",
    ),
    "artifact_cohort": dict(
        id=sid("args_output/artifact_cohort"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="cohort",
    ),
    "artifact_eval": dict(
        id=sid("args_output/artifact_eval"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="eval",
    ),
    "artifact_department": dict(
        id=sid("args_output/artifact_department"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="department",
    ),
    "artifact_model": dict(
        id=sid("args_output/artifact_model"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="model",
    ),
    "artifact_provider": dict(
        id=sid("args_output/artifact_provider"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="provider",
    ),
    "artifact_tool": dict(
        id=sid("args_output/artifact_tool"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="tool",
    ),
    "artifact_setting": dict(
        id=sid("args_output/artifact_setting"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="setting",
    ),
    "artifact_auth": dict(
        id=sid("args_output/artifact_auth"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="auth",
    ),
    "artifact_field": dict(
        id=sid("args_output/artifact_field"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="field",
    ),
    "artifact_parameter": dict(
        id=sid("args_output/artifact_parameter"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="parameter",
    ),
    "artifact_profile": dict(
        id=sid("args_output/artifact_profile"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="profile",
    ),
    "artifact_scenario_image": dict(
        id=sid("args_output/artifact_scenario_image"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="scenario_image",
    ),
    "artifact_scenario_video": dict(
        id=sid("args_output/artifact_scenario_video"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="scenario_video",
    ),
    "artifact_document_text": dict(
        id=sid("args_output/artifact_document_text"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="document_text",
    ),
    "artifact_document_file": dict(
        id=sid("args_output/artifact_document_file"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="document_file",
    ),
    "artifact_attempt_audio": dict(
        id=sid("args_output/artifact_attempt_audio"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="attempt_audio",
    ),
    # --- Payload: universal fields (all/most create operations) ---
    "name": dict(
        id=sid("args_output/name"),
        args_id=sid("arg/name"),
        name="name",
        template="{{ name }}",
    ),
    "description": dict(
        id=sid("args_output/description"),
        args_id=sid("arg/description"),
        name="description",
        template="{{ description }}",
    ),
    # --- Payload: content-specific fields ---
    "instructions": dict(
        id=sid("args_output/instructions"),
        args_id=sid("arg/instructions"),
        name="instructions",
        template="{{ instructions }}",
    ),
    "color": dict(
        id=sid("args_output/color"),
        args_id=sid("arg/color"),
        name="color",
        template="{{ color }}",
    ),
    "icon": dict(
        id=sid("args_output/icon"),
        args_id=sid("arg/icon"),
        name="icon",
        template="{{ icon }}",
    ),
    "image": dict(
        id=sid("args_output/image"),
        args_id=sid("arg/image"),
        name="image",
        template="{{ image }}",
    ),
    "video": dict(
        id=sid("args_output/video"),
        args_id=sid("arg/video"),
        name="video",
        template="{{ video }}",
    ),
    "audio": dict(
        id=sid("args_output/audio"),
        args_id=sid("arg/audio"),
        name="audio",
        template="{{ audio }}",
    ),
    "content": dict(
        id=sid("args_output/content"),
        args_id=sid("arg/content"),
        name="content",
        template="{{ content }}",
    ),
    "file": dict(
        id=sid("args_output/file"),
        args_id=sid("arg/file"),
        name="file",
        template="{{ file }}",
    ),
    "image_id": dict(
        id=sid("args_output/image_id"),
        args_id=sid("arg/image_id"),
        name="image_id",
        template="{{ image_id }}",
    ),
    "video_id": dict(
        id=sid("args_output/video_id"),
        args_id=sid("arg/video_id"),
        name="video_id",
        template="{{ video_id }}",
    ),
    "audio_id": dict(
        id=sid("args_output/audio_id"),
        args_id=sid("arg/audio_id"),
        name="audio_id",
        template="{{ audio_id }}",
    ),
    "text_id": dict(
        id=sid("args_output/text_id"),
        args_id=sid("arg/text_id"),
        name="text_id",
        template="{{ text_id }}",
    ),
    "file_id": dict(
        id=sid("args_output/file_id"),
        args_id=sid("arg/file_id"),
        name="file_id",
        template="{{ file_id }}",
    ),
    "problem_statement": dict(
        id=sid("args_output/problem_statement"),
        args_id=sid("arg/problem_statement"),
        name="problem_statement",
        template="{{ problem_statement }}",
    ),
    # --- Payload: search/browse fields ---
    "search": dict(
        id=sid("args_output/search"),
        args_id=sid("arg/search"),
        name="search",
        template="{{ search }}",
    ),
    "page": dict(
        id=sid("args_output/page"),
        args_id=sid("arg/page"),
        name="page",
        template="{{ page }}",
    ),
    "page_size": dict(
        id=sid("args_output/page_size"),
        args_id=sid("arg/page_size"),
        name="page_size",
        template="{{ page_size }}",
    ),
    # --- Payload: session/audio fields ---
    "chat_id": dict(
        id=sid("args_output/chat_id"),
        args_id=sid("arg/chat_id"),
        name="chat_id",
        template="{{ chat_id }}",
    ),
    "length_seconds": dict(
        id=sid("args_output/length_seconds"),
        args_id=sid("arg/length_seconds"),
        name="length_seconds",
        template="{{ length_seconds }}",
    ),
    "muted": dict(
        id=sid("args_output/muted"),
        args_id=sid("arg/muted"),
        name="muted",
        template="{{ muted }}",
    ),
    # --- Payload: ID reference fields ---
    "agent_id": dict(
        id=sid("args_output/agent_id"),
        args_id=sid("arg/artifact"),
        name="agent_id",
        template="{{ agent_id }}",
    ),
    "attempt_id": dict(
        id=sid("args_output/attempt_id"),
        args_id=sid("arg/attempt_id"),
        name="attempt_id",
        template="{{ attempt_id }}",
    ),
    "simulation_id": dict(
        id=sid("args_output/simulation_id"),
        args_id=sid("arg/simulation_id"),
        name="simulation_id",
        template="{{ simulation_id }}",
    ),
    "test_id": dict(
        id=sid("args_output/test_id"),
        args_id=sid("arg/test_id"),
        name="test_id",
        template="{{ test_id }}",
    ),
    "draft_id": dict(
        id=sid("args_output/draft_id"),
        args_id=sid("arg/draft_id"),
        name="draft_id",
        template="{{ draft_id }}",
    ),
    # --- Payload: attempt/test fields ---
    "message": dict(
        id=sid("args_output/message"),
        args_id=sid("arg/message"),
        name="message",
        template="{{ message }}",
    ),
    "feedback": dict(
        id=sid("args_output/feedback"),
        args_id=sid("arg/feedback"),
        name="feedback",
        template="{{ feedback }}",
    ),
    "grade": dict(
        id=sid("args_output/grade"),
        args_id=sid("arg/grade"),
        name="grade",
        template="{{ grade }}",
    ),
    "score": dict(
        id=sid("args_output/score"),
        args_id=sid("arg/score"),
        name="score",
        template="{{ score }}",
    ),
    # --- Routing: additional hardcoded operations ---
    "operation_start": dict(
        id=sid("args_output/operation_start"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="start",
    ),
    "operation_end": dict(
        id=sid("args_output/operation_end"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="end",
    ),
    "operation_next": dict(
        id=sid("args_output/operation_next"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="next",
    ),
    "operation_message": dict(
        id=sid("args_output/operation_message"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="message",
    ),
    "operation_grade": dict(
        id=sid("args_output/operation_grade"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="grade",
    ),
    "operation_stop": dict(
        id=sid("args_output/operation_stop"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="stop",
    ),
    "operation_export": dict(
        id=sid("args_output/operation_export"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="export",
    ),
    "operation_refresh": dict(
        id=sid("args_output/operation_refresh"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="refresh",
    ),
    "operation_image_upload": dict(
        id=sid("args_output/operation_image_upload"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="image_upload",
    ),
    "operation_image_download": dict(
        id=sid("args_output/operation_image_download"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="image_download",
    ),
    "operation_video_upload": dict(
        id=sid("args_output/operation_video_upload"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="video_upload",
    ),
    "operation_video_download": dict(
        id=sid("args_output/operation_video_download"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="video_download",
    ),
    "operation_text_upload": dict(
        id=sid("args_output/operation_text_upload"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="text_upload",
    ),
    "operation_text_download": dict(
        id=sid("args_output/operation_text_download"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="text_download",
    ),
    "operation_file_upload": dict(
        id=sid("args_output/operation_file_upload"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="file_upload",
    ),
    "operation_file_download": dict(
        id=sid("args_output/operation_file_download"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="file_download",
    ),
    "operation_file_preview": dict(
        id=sid("args_output/operation_file_preview"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="file_preview",
    ),
    "operation_audio_upload": dict(
        id=sid("args_output/operation_audio_upload"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="audio_upload",
    ),
    "operation_audio_download": dict(
        id=sid("args_output/operation_audio_download"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="audio_download",
    ),
    "operation_audio_start": dict(
        id=sid("args_output/operation_audio_start"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="audio_start",
    ),
    "operation_audio_frame": dict(
        id=sid("args_output/operation_audio_frame"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="audio_frame",
    ),
    "operation_audio_stop": dict(
        id=sid("args_output/operation_audio_stop"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="audio_stop",
    ),
    "operation_audio_mute": dict(
        id=sid("args_output/operation_audio_mute"),
        args_id=_OPERATION_ARG_ID,
        name="operation",
        template="audio_mute",
    ),
    # --- Routing: additional hardcoded artifacts ---
    "artifact_attempt": dict(
        id=sid("args_output/artifact_attempt"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="attempt",
    ),
    "artifact_test": dict(
        id=sid("args_output/artifact_test"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="test",
    ),
    "artifact_dashboard": dict(
        id=sid("args_output/artifact_dashboard"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="dashboard",
    ),
    "artifact_reports": dict(
        id=sid("args_output/artifact_reports"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="reports",
    ),
    "artifact_leaderboard": dict(
        id=sid("args_output/artifact_leaderboard"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="leaderboard",
    ),
    "artifact_activity": dict(
        id=sid("args_output/artifact_activity"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="activity",
    ),
    "artifact_health": dict(
        id=sid("args_output/artifact_health"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="health",
    ),
    "artifact_benchmark": dict(
        id=sid("args_output/artifact_benchmark"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="benchmark",
    ),
    "artifact_home": dict(
        id=sid("args_output/artifact_home"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="home",
    ),
    "artifact_practice": dict(
        id=sid("args_output/artifact_practice"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="practice",
    ),
    "artifact_pricing": dict(
        id=sid("args_output/artifact_pricing"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="pricing",
    ),
    "artifact_record": dict(
        id=sid("args_output/artifact_record"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="record",
    ),
    "artifact_session": dict(
        id=sid("args_output/artifact_session"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="session",
    ),
    "artifact_chat": dict(
        id=sid("args_output/artifact_chat"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="chat",
    ),
    "artifact_invocation": dict(
        id=sid("args_output/artifact_invocation"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="invocation",
    ),
    "artifact_group": dict(
        id=sid("args_output/artifact_group"),
        args_id=_ARTIFACT_ARG_ID,
        name="artifact",
        template="group",
    ),
}

# Flat list for seeding
args_outputs = list(SHARED_ARGS_OUTPUTS.values())
