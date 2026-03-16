"""Output events — what the server sends."""

from . import (  # noqa: F401
    # Activity (namespaced)
    activity,
    # Agent (namespaced)
    agent,
    # Attempt (namespaced)
    attempt,
    # Auth (namespaced)
    auth,
    # Benchmark (namespaced)
    benchmark,
    # Chat (namespaced)
    chat,
    # Cohort (namespaced)
    cohort,
    # Dashboard (namespaced)
    dashboard,
    # Department (namespaced)
    department,
    # Document (namespaced)
    document,
    # Eval (namespaced)
    eval,
    # Field (namespaced)
    field,
    # Group (namespaced)
    group,
    # Health (namespaced)
    health,
    # Home (namespaced)
    home,
    # Invocation (namespaced)
    invocation,
    # Leaderboard (namespaced)
    leaderboard,
    # Model (namespaced)
    model,
    # Parameter (namespaced)
    parameter,
    # Persona (namespaced)
    persona,
    # Practice (namespaced)
    practice,
    # Pricing (namespaced)
    pricing,
    # Profile (namespaced)
    profile,
    # Provider (namespaced)
    provider,
    # Record (namespaced)
    record,
    # Reports (namespaced)
    reports,
    # Rubric (namespaced)
    rubric,
    # Scenario (namespaced)
    scenario,
    # Session (namespaced)
    session,
    # Setting (namespaced)
    setting,
    # Simulation (namespaced)
    simulation,
    # Tool (namespaced)
    tool,
    # Connect/disconnect (top-level)
    connected,
    disconnected,
    # Non-artifact actions (top-level)
    context,
    emulate,
    unemulate,
    problem,
    docs,
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
    generation_channel_complete,
    generation_channel_error,
    generation_channel_saved,
    generation_channel_media_progress,
    generation_channel_media_complete,
    # Test (namespaced)
    test,
)
