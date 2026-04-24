"""Input events — what the client sends."""

from . import (  # noqa: F401
    # 3 operational parents
    attempt,         # attempt.* events
    test,            # test.* events
    system,          # system.* events
    # attempt sub-artifacts now under ws/input/attempt/
    # chat, home, practice, dashboard, leaderboard, record, reports
    # test sub-artifacts now under ws/input/test/
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
    # Root-level actions
    connect,
    disconnect,
)
