"""Role resource seeds.

7 rows defining user roles with their permissions, icon/color associations,
level hierarchy, and request limits.

Level: 0 = highest privilege (superadmin), higher = less privilege.

Post-consolidation (migration 30): VIEW artifacts folded into parents:
  attempt ← home, practice, chat, dashboard, leaderboard, reports, record
  test    ← invocation, benchmark
  system  ← activity, session, pricing, group, health
"""

from database.seeds.ids import sid
from database.seeds.resources.permissions import PERMISSION_IDS

_READ_OPS = ["get", "search", "docs", "refresh", "export", "generations", "context"]
_WRITE_OPS = ["create", "update", "delete", "duplicate", "draft", "drafts", "generate", "name", "grade", "feedback", "group", "problem", "csv"]
_LIFECYCLE_OPS = ["start", "complete", "stop", "join", "leave", "response", "archive", "resolve", "chat_get", "chat_create", "chat_message", "chat_audio", "chat_stop", "chat_complete", "chat_grade", "chat_voice", "chat_mute", "chat_silence", "chat_response", "chat_feedback", "chat_strengths", "chat_improvements", "chat_analyses", "chat_hints"]
_ALL_CRUD = _READ_OPS + _WRITE_OPS + _LIFECYCLE_OPS
_MEDIA_OPS = [
    "image_upload", "image_download",
    "video_upload", "video_download",
    "text_upload", "text_download",
    "file_upload", "file_download", "file_preview",
    "audio_upload", "audio_download",
    "call_download",
    "audio_start", "audio_frame", "audio_stop", "audio_mute",
]

# VIEW children consolidated under parent artifacts
_ATTEMPT_VIEWS = ["home", "practice", "chat", "dashboard", "leaderboard", "reports", "record"]
_TEST_VIEWS = ["invocation", "benchmark"]
_SYSTEM_VIEWS = ["activity", "session", "pricing", "group", "health"]

# Broad superset of VIEW operations — _pids filter keeps only valid combos
_VIEW_ALL_OPS = [
    "context", "create", "export", "generate", "generations", "get", "group", "problem", "refresh", "search",
    "draft", "drafts", "decrypt", "resolve", "name",
    "audio_download", "call_download", "file_download", "file_preview",
    "image_download", "text_download", "video_download",
]

# Request limit IDs (from request_limits seeds)
DAILY_LIMIT_10 = sid("request-limit/daily-10")


def _pids(artifact_names: list[str], ops: list[str] | None = None) -> list:
    """Build permission_ids from artifact names x operations.

    If ops is None, uses READ_OPS only (backward compat).
    Pass _ALL_CRUD for full CRUD, or a custom list.
    """
    operations = ops or _READ_OPS
    return [
        PERMISSION_IDS[(a, op)]
        for a in artifact_names
        for op in operations
        if (a, op) in PERMISSION_IDS
    ]


def _child_ops(children: list[str], ops: list[str] | None = None) -> list[str]:
    """Compound operation names for VIEW children under a parent artifact.

    _child_ops(["home", "practice"]) → ["home_context", ..., "practice_context", ...]
    _child_ops(["chat"], _READ_OPS)  → ["chat_get", "chat_search", ...]
    """
    base = ops or _VIEW_ALL_OPS
    return [f"{child}_{op}" for child in children for op in base]


roles = [
    # ── Superadmin (level 0): full CRUD on everything ──
    dict(
        id=sid("role/super-administrator"),
        level=0,
        name="Super Administrator",
        description="Full system access to all data and permissions",
        icon_id=sid("icon/crown"),
        color_id=sid("color/amber"),
        permission_ids=(
            # Full CRUD on all 17 CRUD artifacts
            _pids([
                "cohort", "simulation", "scenario", "persona",
                "profile", "document", "parameter", "field",
                "agent", "model", "provider", "tool",
                "setting", "department", "rubric", "eval", "auth",
            ], _ALL_CRUD)
            # All direct ops on parent artifacts
            + _pids(["attempt", "test"], _ALL_CRUD)
            # All compound child ops under each parent
            + _pids(["attempt"], _child_ops(_ATTEMPT_VIEWS))
            + _pids(["test"], _child_ops(_TEST_VIEWS))
            + _pids(["system"], _child_ops(_SYSTEM_VIEWS))
            # Media ops
            + _pids(["scenario", "document", "attempt", "test", "system"], _MEDIA_OPS)
        ),
    ),
    # ── Admin (level 1): CRUD on most, read on system artifacts ──
    dict(
        id=sid("role/administrator"),
        level=1,
        name="Administrator",
        description="Manages all content and users within departments",
        icon_id=sid("icon/shield"),
        color_id=sid("color/blue"),
        permission_ids=(
            # CRUD on content + management artifacts
            _pids([
                "cohort", "simulation", "scenario", "persona",
                "profile", "document", "parameter", "field",
                "agent", "model", "provider", "tool", "setting",
            ], _ALL_CRUD)
            # Read-only on parent artifacts (direct ops)
            + _pids(["attempt", "test"], _READ_OPS)
            # Read-only compound child ops
            + _pids(["attempt"], _child_ops(_ATTEMPT_VIEWS, _READ_OPS))
            + _pids(["test"], _child_ops(_TEST_VIEWS, _READ_OPS))
            + _pids(["system"], _child_ops(_SYSTEM_VIEWS, _READ_OPS))
            # Media ops (group media now under system via compound ops)
            + _pids(["scenario", "document", "attempt", "test"], _MEDIA_OPS)
            + _pids(["system"], _MEDIA_OPS)
        ),
    ),
    # ── Instructional (level 2): CRUD on training, read on analytics ──
    dict(
        id=sid("role/instructional-staff"),
        level=2,
        name="Instructional Staff",
        description="Manages training content, cohorts, and simulations",
        icon_id=sid("icon/graduation-cap"),
        color_id=sid("color/violet"),
        permission_ids=(
            # CRUD on training artifacts
            _pids([
                "cohort", "simulation", "scenario", "persona",
                "document", "parameter", "field",
            ], _ALL_CRUD)
            # Read-only on parent artifacts (direct ops)
            + _pids(["attempt", "test"], _READ_OPS)
            # Read-only compound child ops (no health for instructional)
            + _pids(["attempt"], _child_ops(_ATTEMPT_VIEWS, _READ_OPS))
            + _pids(["test"], _child_ops(_TEST_VIEWS, _READ_OPS))
            + _pids(["system"], _child_ops(["activity", "session", "pricing", "group"], _READ_OPS))
            # Media ops
            + _pids(["scenario", "document", "attempt", "test"], _MEDIA_OPS)
            + _pids(["system"], _MEDIA_OPS)
        ),
    ),
    # ── GTA (level 3): read + practice ──
    dict(
        id=sid("role/gta"),
        level=3,
        name="GTA",
        description="Graduate Teaching Assistant",
        icon_id=None,
        color_id=None,
        permission_ids=(
            # Read ops on attempt (direct)
            _pids(["attempt"], _READ_OPS)
            # Read compound ops for home, practice, leaderboard, chat
            + _pids(["attempt"], _child_ops(["home", "practice", "leaderboard", "chat"], _READ_OPS))
            # Media ops on attempt
            + _pids(["attempt"], _MEDIA_OPS)
        ),
    ),
    # ── UTA (level 3): read + practice ──
    dict(
        id=sid("role/uta"),
        level=3,
        name="UTA",
        description="Undergraduate Teaching Assistant",
        icon_id=None,
        color_id=None,
        permission_ids=(
            _pids(["attempt"], _READ_OPS)
            + _pids(["attempt"], _child_ops(["home", "practice", "leaderboard", "chat"], _READ_OPS))
            + _pids(["attempt"], _MEDIA_OPS)
        ),
    ),
    # ── Guest (level 4): minimal access ──
    dict(
        id=sid("role/guest"),
        level=4,
        name="Guest",
        description="Limited access, not logged in or not registered",
        icon_id=sid("icon/user"),
        color_id=sid("color/gray"),
        permission_ids=(
            _pids(["attempt"], _READ_OPS)
            + _pids(["attempt"], _child_ops(["practice", "chat"], _READ_OPS))
            + _pids(["attempt"], _MEDIA_OPS)
        ),
        request_limit_ids=[DAILY_LIMIT_10],
    ),
    # ── Benchmark (level 3): system benchmarking access ──
    dict(
        id=sid("role/benchmark"),
        level=3,
        name="Benchmark",
        description="Benchmark access role",
        icon_id=sid("icon/flame"),
        color_id=sid("color/orange"),
        permission_ids=(
            _pids(["test"], _ALL_CRUD)
            + _pids(["test"], _child_ops(_TEST_VIEWS))
        ),
    ),
]
