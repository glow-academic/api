"""Output: test.* events."""

from . import (  # noqa: F401
    # Lifecycle
    started,
    ended,
    invocation_started,
    joined,
    stopped,
    # Run lifecycle
    run_started,
    run_complete,
    run_delta,
    # Grading
    grade_start,
    grade_progress,
    grade_complete,
    # Error
    error,
    # Pipeline hops (work handlers)
    proceed,
    run_internal,
    group_internal,
    group_complete,
    start_internal,
    end_internal,
    next_internal,
    stop_internal,
    # Bridge events (work handlers — call impls directly)
    progress_update,
    run_done,
    error_event,
    # Grade bridge (generate_call_complete → test grade)
    generate_grade,
)
