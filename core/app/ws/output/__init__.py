"""Output events — what the server sends."""

from . import (  # noqa: F401
    # 3 operational parents
    attempt,         # attempt.* events
    test,            # test.* events
    system,          # system.* events
    # attempt sub-artifacts now under ws/output/attempt/
    # home, practice, dashboard, leaderboard, record, reports
    chat,            # chat WS handlers (stays at top-level)
    # test sub-artifacts now under ws/output/test/
    # benchmark → test/benchmark/, invocation → test/invocation/
    # 16 canonical CRUD artifacts
    agent,
    auth,
    cohort,
    department,
    document,
    eval,
    field,
    model,
    parameter,
    persona,
    profile,
    provider,
    rubric,
    scenario,
    setting,
    simulation,
    tool,
    # Connect/disconnect (top-level)
    connected,
    disconnected,
    # Non-artifact actions (now under their artifact folders)
    # Generate pipeline
    generate_pipeline,
    generate_prepare,
    generate_artifact,
    # Generate call-level
    generate_call_start,
    generate_call_progress,
    generate_call_complete,
    generate_call_error,
    # Generate text
    generate_text_start,
    generate_text_progress,
    generate_text_complete,
    generate_text_error,
    # Generate image
    generate_image_start,
    generate_image_progress,
    generate_image_complete,
    # Generate video
    generate_video_start,
    generate_video_progress,
    generate_video_complete,
    # Generate audio
    generate_audio_session_start,
    generate_audio_progress,
    generate_audio_session_complete,
    generate_audio_user_speech_start,
    generate_audio_user_speech_delta,
    generate_audio_user_speech_complete,
    generate_audio_response_cancelled,
    generate_audio_error,
    # Generate run lifecycle
    generate_run_complete,
    generate_error,
    # Generation channel (aggregated, client-facing)
    generation_started,
    generation_channel_progress,
    generation_channel_chat,
    generation_channel_complete,
    generation_channel_error,
    generation_channel_saved,
    generation_channel_media_progress,
    generation_channel_media_complete,
    # Test (namespaced)
    test,
)
