"""Role resource seeds.

7 rows defining user roles with their permissions, icon/color associations,
level hierarchy, and request limits.

Level: 0 = highest privilege (superadmin), higher = less privilege.
"""

from uuid import UUID

from database.seeds.ids import sid
from database.seeds.resources.permissions import PERMISSION_IDS

_READ_OPS = ["get", "search", "docs", "refresh", "export"]
_WRITE_OPS = ["create", "update", "delete", "duplicate", "draft", "drafts"]
_ALL_CRUD = _READ_OPS + _WRITE_OPS
_MEDIA_OPS = [
    "image_upload", "image_download",
    "video_upload", "video_download",
    "text_upload", "text_download",
    "file_upload", "file_download", "file_preview",
    "audio_upload", "audio_download",
    "audio_start", "audio_frame", "audio_stop", "audio_mute",
]

# Request limit IDs (from request_limits seeds)
DAILY_LIMIT_10 = UUID("019bb553-e77f-797c-ae44-544fbe10351b")


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
        id=UUID("019bbabc-5a3b-7481-bbf5-a7c2193bc5e4"),
        level=0,
        name="Super Administrator",
        description="Full system access to all data and permissions",
        icon_id=UUID("019bb3ba-adb7-703a-b547-c08bb5bf1d86"),
        color_id=UUID("019b9eb0-c7ab-7e82-99e7-a4bdcf523add"),
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
            + _pids(["scenario", "document", "attempt"], _MEDIA_OPS)
        ),
    ),
    # ── Admin (level 1): CRUD on most, read on system artifacts ──
    dict(
        id=UUID("019bbabc-5a36-76d3-8fc3-8415fe308cd3"),
        level=1,
        name="Administrator",
        description="Manages all content and users within departments",
        icon_id=UUID("019b9eb0-c7ac-7a45-965e-a51bb3cc5eb6"),
        color_id=UUID("019b995b-52f6-7746-a592-fbc338f61f5f"),
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
            + _pids(["scenario", "document", "attempt"], _MEDIA_OPS)
        ),
    ),
    # ── Instructional (level 2): CRUD on training, read on analytics ──
    dict(
        id=UUID("019bbabc-5a3b-741e-bad3-474cc6c05fd6"),
        level=2,
        name="Instructional Staff",
        description="Manages training content, cohorts, and simulations",
        icon_id=UUID("019b995b-52f7-752e-b5df-c8ff97d35ae7"),
        color_id=UUID("019b995b-52f6-7750-8e0d-a4a37ff9ad13"),
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
            + _pids(["scenario", "document", "attempt"], _MEDIA_OPS)
        ),
    ),
    # ── GTA (level 3): read + practice ──
    dict(
        id=UUID("019bf21d-4d50-74fc-8c81-be446d602de2"),
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
        id=UUID("019bf21d-4d50-7039-b5ba-4aea69013072"),
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
        id=UUID("019bbabc-5a37-7028-8b98-728b7aa54d0d"),
        level=4,
        name="Guest",
        description="Limited access, not logged in or not registered",
        icon_id=UUID("019b995b-52f7-7525-b425-73423c427909"),
        color_id=UUID("019b995b-52f1-7d09-889a-b24887bd2cb2"),
        permission_ids=(
            _pids(["practice", "chat", "attempt"])
            + _pids(["attempt"], _MEDIA_OPS)
        ),
        request_limit_ids=[DAILY_LIMIT_10],
    ),
    # ── Benchmark (level 3): system benchmarking access ──
    dict(
        id=UUID("019bdb94-b279-70c0-a610-6b9696fb5c94"),
        level=3,
        name="Benchmark",
        description="Benchmark access role",
        icon_id=UUID("019bb3ba-adb7-7045-884f-ee58692da3d1"),
        color_id=UUID("019b9eb0-c7ab-7dce-a088-16018f3dbf37"),
        permission_ids=_pids(["benchmark", "invocation", "test"], _ALL_CRUD),
    ),
]
