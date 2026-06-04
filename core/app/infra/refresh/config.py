"""Per-MV refresh interval config — hotness tiers + full target registry.

Every entry table that owns a `*_mv` materialized view is registered here.
The MVRefresher uses this registry at lifespan startup to spawn one
background worker per target. Each worker debounces concurrent enqueues
into one REFRESH MATERIALIZED VIEW per interval, with a Redis lock so
multiple replicas serialize on the same MV.

Hotness tiers (rules of thumb):
  Hot     (~2s)  — read on every page load, naming/identity projections
  Warm    (~5s)  — per-feature reads (chat, conversation history)
  Cool    (~10s) — list views, drafts, generic projections
  Glacial (~30s) — auth/permission-derived, audit, rate-keeping
"""

from __future__ import annotations

_HOT_S = 2.0
_WARM_S = 5.0
_COOL_S = 10.0
_GLACIAL_S = 30.0


# (entries_dir, refresh_fn_name, interval_s)
# entries_dir is the package under app/tools/entries/ that owns the
# refresh primitive — used by the lifespan to import dynamically without
# 100+ explicit imports in server.py.
MV_REGISTRY: dict[str, tuple[str, str, float]] = {
    "activity_mv": ("activity", "refresh_activity", _COOL_S),
    "agent_drafts_mv": ("agent_drafts", "refresh_agent_drafts", _COOL_S),
    "attempt_analysis_mv": ("attempt_analysis", "refresh_attempt_analysis", _COOL_S),
    "attempt_archive_mv": ("attempt_archive", "refresh_attempt_archive", _COOL_S),
    "attempt_chat_bridge_mv": ("attempt_chat_bridge", "refresh_attempt_chat_bridge", _COOL_S),
    "attempt_chat_completion_mv": ("attempt_chat_completion", "refresh_attempt_chat_completion", _WARM_S),
    "attempt_chat_mv": ("attempt_chat", "refresh_attempt_chat", _WARM_S),
    "attempt_completion_mv": ("attempt_completion", "refresh_attempt_completion", _COOL_S),
    "attempt_content_mv": ("attempt_content", "refresh_attempt_content", _COOL_S),
    "attempt_conversation_completion_mv": ("attempt_conversation_completion", "refresh_attempt_conversation_completion", _WARM_S),
    "attempt_conversations_mv": ("attempt_conversations", "refresh_attempt_conversations", _WARM_S),
    "attempt_feedback_mv": ("attempt_feedback", "refresh_attempt_feedback", _COOL_S),
    "attempt_grade_mv": ("attempt_grade", "refresh_attempt_grade", _COOL_S),
    "attempt_highlight_mv": ("attempt_highlight", "refresh_attempt_highlight", _COOL_S),
    "attempt_hint_mv": ("attempt_hint", "refresh_attempt_hint", _COOL_S),
    "attempt_home_mv": ("attempt_home", "refresh_attempt_home", _COOL_S),
    "attempt_improvement_mv": ("attempt_improvement", "refresh_attempt_improvement", _COOL_S),
    "attempt_message_completion_mv": ("attempt_message_completion", "refresh_attempt_message_completion", _WARM_S),
    "attempt_message_mv": ("attempt_message", "refresh_attempt_message", _WARM_S),
    "attempt_message_tree_mv": ("attempt_message_tree", "refresh_attempt_message_tree", _COOL_S),
    "attempt_mv": ("attempt", "refresh_attempt", _COOL_S),
    "attempt_practice_mv": ("attempt_practice", "refresh_attempt_practice", _COOL_S),
    "attempt_replacement_mv": ("attempt_replacement", "refresh_attempt_replacement", _COOL_S),
    "attempt_responses_mv": ("attempt_responses", "refresh_attempt_responses", _WARM_S),
    "attempt_strength_mv": ("attempt_strength", "refresh_attempt_strength", _COOL_S),
    "audio_completion_mv": ("audio_completion", "refresh_audio_completion", _COOL_S),
    "audio_uploads_mv": ("audio_uploads", "refresh_audio_uploads", _COOL_S),
    "audios_mv": ("audios", "refresh_audios_internal", _COOL_S),
    "auth_drafts_mv": ("auth_drafts", "refresh_auth_drafts", _COOL_S),
    "benchmark_mv": ("benchmark", "refresh_benchmark", _COOL_S),
    "benchmark_test_mv": ("benchmark_test", "refresh_benchmark_test", _COOL_S),
    "call_uploads_mv": ("call_uploads", "refresh_call_uploads", _COOL_S),
    "calls_mv": ("calls", "refresh_calls_internal", _HOT_S),
    "chat_drafts_mv": ("chat_drafts", "refresh_chat_drafts", _COOL_S),
    "chat_mv": ("chat", "refresh_chat", _WARM_S),
    "cohort_drafts_mv": ("cohort_drafts", "refresh_cohort_drafts", _COOL_S),
    "department_drafts_mv": ("department_drafts", "refresh_department_drafts", _COOL_S),
    "document_drafts_mv": ("document_drafts", "refresh_document_drafts", _COOL_S),
    "emulations_mv": ("emulations", "refresh_emulations", _COOL_S),
    "eval_drafts_mv": ("eval_drafts", "refresh_eval_drafts", _COOL_S),
    "field_drafts_mv": ("field_drafts", "refresh_field_drafts", _COOL_S),
    "file_completion_mv": ("file_completion", "refresh_file_completion", _COOL_S),
    "file_uploads_mv": ("file_uploads", "refresh_file_uploads", _COOL_S),
    "files_mv": ("files", "refresh_files_internal", _COOL_S),
    "grant_consumptions_mv": ("grant_consumptions", "refresh_grant_consumptions", _GLACIAL_S),
    "grants_mv": ("grants", "refresh_grants_internal", _GLACIAL_S),
    "group_names_mv": ("group_names", "refresh_group_names", _HOT_S),
    # `refresh_groups` refreshes group_names_mv THEN groups_mv (dependency
    # ordering is enforced inside the primitive). Registering it for groups_mv
    # only — group_names_mv has its own slimmer refresh primitive above.
    "groups_mv": ("groups", "refresh_groups", _HOT_S),
    "health_mv": ("health", "refresh_health_internal", _GLACIAL_S),
    "home_chat_mv": ("home_chat", "refresh_home_chat", _WARM_S),
    "home_mv": ("home", "refresh_home", _COOL_S),
    "image_completion_mv": ("image_completion", "refresh_image_completion", _COOL_S),
    "image_uploads_mv": ("image_uploads", "refresh_image_uploads", _COOL_S),
    "images_mv": ("images", "refresh_images_internal", _COOL_S),
    "invocation_drafts_mv": ("invocation_drafts", "refresh_invocation_drafts", _COOL_S),
    "invocation_mv": ("invocation", "refresh_invocations", _COOL_S),
    "logins_mv": ("logins", "refresh_logins", _GLACIAL_S),
    "logouts_mv": ("logouts", "refresh_logouts", _GLACIAL_S),
    "message_uploads_mv": ("message_uploads", "refresh_message_uploads", _COOL_S),
    "messages_mv": ("messages", "refresh_messages_internal", _HOT_S),
    "metrics_mv": ("metrics", "refresh_metrics_internal", _GLACIAL_S),
    "model_drafts_mv": ("model_drafts", "refresh_model_drafts", _COOL_S),
    "parameter_drafts_mv": ("parameter_drafts", "refresh_parameter_drafts", _COOL_S),
    "persona_drafts_mv": ("persona_drafts", "refresh_persona_drafts", _COOL_S),
    "personas_mv": ("personas", "refresh_personas", _COOL_S),
    "practice_chat_mv": ("practice_chat", "refresh_practice_chat", _WARM_S),
    "practice_mv": ("practice", "refresh_practice", _COOL_S),
    "problems_mv": ("problems", "refresh_problems", _COOL_S),
    "profile_drafts_mv": ("profile_drafts", "refresh_profile_drafts", _COOL_S),
    "provider_drafts_mv": ("provider_drafts", "refresh_provider_drafts", _COOL_S),
    "refreshes_mv": ("refreshes", "refresh_refreshes_internal", _GLACIAL_S),
    "resolves_mv": ("resolves", "refresh_resolves", _GLACIAL_S),
    "rubric_drafts_mv": ("rubric_drafts", "refresh_rubric_drafts", _COOL_S),
    "run_pricing_mv": ("run_pricing", "refresh_run_pricing_internal", _COOL_S),
    "runs_mv": ("runs", "refresh_runs_internal", _HOT_S),
    "scenario_drafts_mv": ("scenario_drafts", "refresh_scenario_drafts", _COOL_S),
    "sessions_mv": ("sessions", "refresh_sessions", _GLACIAL_S),
    "setting_drafts_mv": ("setting_drafts", "refresh_setting_drafts", _COOL_S),
    "simulation_drafts_mv": ("simulation_drafts", "refresh_simulation_drafts", _COOL_S),
    "soft_calls_mv": ("soft_calls", "refresh_soft_calls", _HOT_S),
    "test_archive_mv": ("test_archive", "refresh_test_archive", _COOL_S),
    "test_completion_mv": ("test_completion", "refresh_test_completion", _COOL_S),
    "test_feedback_mv": ("test_feedback", "refresh_test_feedback", _COOL_S),
    "test_grade_mv": ("test_grade", "refresh_test_grade", _COOL_S),
    "test_invocation_bridge_mv": ("test_invocation_bridge", "refresh_test_invocation_bridge", _COOL_S),
    "test_invocation_completion_mv": ("test_invocation_completion", "refresh_test_invocation_completion", _COOL_S),
    "test_invocation_traces_completion_mv": ("test_invocation_traces_completion", "refresh_test_invocation_traces_completion", _COOL_S),
    "test_invocation_traces_mv": ("test_invocation_traces", "refresh_test_invocation_traces", _COOL_S),
    "test_invocation_mv": ("test_invocation", "refresh_test_invocation", _COOL_S),
    "test_invocation_runs_completion_mv": ("test_invocation_runs_completion", "refresh_test_invocation_runs_completion", _COOL_S),
    "test_invocation_runs_mv": ("test_invocation_runs", "refresh_test_invocation_runs", _COOL_S),
    "test_mv": ("test", "refresh_test", _COOL_S),
    "text_completion_mv": ("text_completion", "refresh_text_completion", _COOL_S),
    "text_uploads_mv": ("text_uploads", "refresh_text_uploads", _COOL_S),
    "texts_mv": ("texts", "refresh_texts_internal", _COOL_S),
    "tokens_mv": ("tokens", "refresh_tokens", _GLACIAL_S),
    "tool_drafts_mv": ("tool_drafts", "refresh_tool_drafts", _COOL_S),
    "upload_completion_mv": ("upload_completion", "refresh_upload_completion", _COOL_S),
    "uploads_mv": ("uploads", "refresh_uploads_internal", _COOL_S),
    "video_completion_mv": ("video_completion", "refresh_video_completion", _COOL_S),
    "video_uploads_mv": ("video_uploads", "refresh_video_uploads", _COOL_S),
    "videos_mv": ("videos", "refresh_videos_internal", _COOL_S),
}


# Convenience flat dict (mv_name → interval_s) for callers who only need
# the timing config without the import metadata.
MV_REFRESH_INTERVALS_S: dict[str, float] = {
    mv: interval for mv, (_d, _fn, interval) in MV_REGISTRY.items()
}


# Default if a target is requested that isn't in the registry — should
# never happen in practice but keeps the worker resilient to typos.
DEFAULT_INTERVAL_S: float = _COOL_S
