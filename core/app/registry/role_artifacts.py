"""role → artifacts accessible to that role.

After consolidation (migration 30), VIEW artifacts are folded into 3 parents:
  attempt ← home, practice, chat, dashboard, leaderboard, reports, record
  test    ← invocation, benchmark
  system  ← activity, session, pricing, group, health

The 17 CRUD artifacts remain unchanged.
"""

from __future__ import annotations

ROLE_ARTIFACTS: dict[str, frozenset[str]] = {
    "admin": frozenset(
        {
            "agent",
            "attempt",
            "cohort",
            "document",
            "field",
            "model",
            "parameter",
            "persona",
            "profile",
            "provider",
            "scenario",
            "setting",
            "simulation",
            "system",
            "test",
            "tool",
        }
    ),
    "guest": frozenset({"attempt"}),
    "instructional": frozenset(
        {
            "attempt",
            "cohort",
            "document",
            "field",
            "parameter",
            "persona",
            "scenario",
            "simulation",
            "system",
            "test",
        }
    ),
    "member": frozenset(
        {
            "attempt",
        }
    ),
    "superadmin": frozenset(
        {
            "agent",
            "attempt",
            "auth",
            "cohort",
            "department",
            "document",
            "eval",
            "field",
            "model",
            "parameter",
            "persona",
            "profile",
            "provider",
            "rubric",
            "scenario",
            "setting",
            "simulation",
            "system",
            "test",
            "tool",
        }
    ),
}
