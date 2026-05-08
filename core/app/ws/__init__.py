"""WebSocket event handlers.

Input handlers (per-artifact + root-level connect/disconnect) live as
peer subpackages of this module. They subscribe to their own specific
events and run real workflow logic.

``output`` is the single catch-all forwarder that fans every
``internal_sio`` event to the matching client rooms and stamps the
call receipt — replaces the previous 1600+ per-event ``ws/output/``
tree. Custom workflow logic that used to live in a few of those
output handlers has been inlined at the corresponding emit sites.
"""

from . import (  # noqa: F401
    # Sub-artifacts live under their parent dir (e.g. attempt/chat/,
    # test/benchmark/) — no top-level import needed.
    # 16 canonical CRUD artifacts
    agent,
    # Operational parents
    attempt,  # attempt.* events
    auth,
    cohort,
    # Root-level lifecycle handlers
    connect,
    department,
    disconnect,
    document,
    eval,
    field,
    model,
    # Catch-all forwarder for everything the server emits.
    output,
    parameter,
    persona,
    profile,
    provider,
    rubric,
    scenario,
    setting,
    simulation,
    system,  # system.* events
    test,  # test.* events
    tool,
)
