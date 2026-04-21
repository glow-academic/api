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
    # Test (namespaced)
    test,
)
