"""Role resource seeds.

7 rows defining user roles with their permissions, icon/color associations,
level hierarchy, and request limits.

Level: 0 = highest privilege (superadmin), higher = less privilege.
"""

from database.seeds.ids import sid
from database.seeds.resources.permissions import PERMISSION_IDS

_READ_OPS = ["get", "search", "docs", "refresh", "export", "generations", "context"]
_WRITE_OPS = ["create", "update", "delete", "duplicate", "draft", "drafts", "generate", "name", "grade", "feedback", "group", "problem", "csv"]
_LIFECYCLE_OPS = ["start", "end", "end_all", "stop", "join", "leave", "next", "previous", "response", "archive", "resolve"]
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
            _pids([
                "home", "practice", "leaderboard", "chat", "attempt",
                "dashboard", "reports", "record", "activity", "session",
                "pricing", "group", "cohort", "simulation", "scenario",
                "persona", "benchmark", "invocation", "test", "profile",
                "document", "parameter", "field", "agent", "model",
                "provider", "tool", "health", "setting", "department",
                "rubric", "eval", "auth",
            ], _ALL_CRUD)
            + _pids(["scenario", "document", "attempt", "group", "test"], _MEDIA_OPS)
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
            # Read-only on analytics/views
            + _pids([
                "home", "practice", "leaderboard", "chat", "attempt",
                "dashboard", "reports", "record", "activity", "session",
                "pricing", "group", "benchmark", "invocation", "test",
                "health",
            ])
            + _pids(["scenario", "document", "attempt", "group", "test"], _MEDIA_OPS)
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
            # Read-only on analytics/views
            + _pids([
                "home", "practice", "leaderboard", "chat", "attempt",
                "dashboard", "reports", "record", "activity", "session",
                "pricing", "group", "benchmark", "invocation", "test",
            ])
            + _pids(["scenario", "document", "attempt", "group", "test"], _MEDIA_OPS)
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
            _pids(["home", "practice", "leaderboard", "chat", "attempt"])
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
            _pids(["home", "practice", "leaderboard", "chat", "attempt"])
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
            _pids(["practice", "chat", "attempt"])
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
        permission_ids=_pids(["benchmark", "invocation", "test"], _ALL_CRUD),
    ),
]
