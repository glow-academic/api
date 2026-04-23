"""Flag resource seeds.

Every flag type is seeded as a **pair**: one row with `value=True` and one row
with `value=False`, so the server and UI can represent both states explicitly
rather than encoding "off" as the absence of a junction row.

Deterministic sid convention:
    - True  variant: sid(f"flag/{slug}")          ← canonical; existing refs use this
    - False variant: sid(f"flag/{slug}/false")    ← new

Callers that look up "the active/on/true version of flag X" MUST disambiguate
by `value=True`, since `search_flags(flag_type=...)` now returns two rows.
"""

from database.seeds.ids import sid


def _flag_pair(
    slug: str,
    *,
    name: str,
    description: str,
    type_: str,
    icon_id,
) -> list[dict]:
    """Emit True + False variants of a flag type with deterministic sids."""
    common = dict(
        name=name,
        description=description,
        type=type_,
        icon_id=icon_id,
    )
    return [
        dict(id=sid(f"flag/{slug}"), value=True, **common),
        dict(id=sid(f"flag/{slug}/false"), value=False, **common),
    ]


flags = [
    *_flag_pair(
        "active",
        name="active",
        description="Active flag",
        type_="active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "guest-login-enabled",
        name="guest_login_enabled",
        description="Guest login enabled",
        type_="guest_login_enabled",
        icon_id=sid("icon/user-check"),
    ),
    *_flag_pair(
        "practice",
        name="Practice",
        description="Practice flag",
        type_="practice",
        icon_id=sid("icon/target"),
    ),
    *_flag_pair(
        "video",
        name="Video",
        description="Video enabled",
        type_="video_enabled",
        icon_id=sid("icon/film"),
    ),
    *_flag_pair(
        "problem-statement",
        name="Problem Statement",
        description="Problem statement enabled",
        type_="problem_statement_enabled",
        icon_id=sid("icon/message-square"),
    ),
    *_flag_pair(
        "objectives",
        name="Objectives",
        description="Objectives enabled",
        type_="objectives_enabled",
        icon_id=sid("icon/target"),
    ),
    *_flag_pair(
        "questions",
        name="Questions",
        description="Questions enabled",
        type_="questions_enabled",
        icon_id=sid("icon/help-circle"),
    ),
    *_flag_pair(
        "images",
        name="Images",
        description="Images enabled",
        type_="images_enabled",
        icon_id=sid("icon/image"),
    ),
    *_flag_pair(
        "groups",
        name="groups",
        description="Groups flag",
        type_="groups",
        icon_id=sid("icon/users"),
    ),
    *_flag_pair(
        "dynamic",
        name="dynamic",
        description="Dynamic flag",
        type_="dynamic",
        icon_id=sid("icon/zap"),
    ),
    *_flag_pair(
        "template",
        name="template",
        description="Template flag",
        type_="template",
        icon_id=sid("icon/clipboard"),
    ),
    *_flag_pair(
        "audio-enabled",
        name="Audio Enabled",
        description="Audio enabled flag for simulation scenario",
        type_="audio_enabled",
        icon_id=sid("icon/volume"),
    ),
    *_flag_pair(
        "text-enabled",
        name="Text Enabled",
        description="Text enabled flag for simulation scenario",
        type_="text_enabled",
        icon_id=sid("icon/file-text"),
    ),
    *_flag_pair(
        "show-problem-statement",
        name="Show Problem Statement",
        description="Show problem statement flag for simulation scenario",
        type_="show_problem_statement",
        icon_id=sid("icon/message-square"),
    ),
    *_flag_pair(
        "show-objectives",
        name="Show Objectives",
        description="Show objectives flag for simulation scenario",
        type_="show_objectives",
        icon_id=sid("icon/target"),
    ),
    *_flag_pair(
        "show-images",
        name="Show Images",
        description="Show images flag for simulation scenario",
        type_="show_images",
        icon_id=sid("icon/image"),
    ),
    *_flag_pair(
        "hints-enabled",
        name="Hints Enabled",
        description="Hints enabled flag for simulation scenario",
        type_="hints_enabled",
        icon_id=sid("icon/lightbulb"),
    ),
    *_flag_pair(
        "copy-paste-allowed",
        name="Copy Paste Allowed",
        description="Copy paste allowed flag for simulation scenario",
        type_="copy_paste_allowed",
        icon_id=sid("icon/copy"),
    ),
    *_flag_pair(
        "use-templates",
        name="use_templates",
        description="Use templates flag for scenarios",
        type_="use_templates",
        icon_id=sid("icon/clipboard"),
    ),
    *_flag_pair(
        "mcp",
        name="mcp",
        description="Enable or disable the use of the MCP server",
        type_="mcp",
        icon_id=sid("icon/server"),
    ),
    *_flag_pair(
        "scenario-active",
        name="Active",
        description="Controls whether this scenario is published and available for simulations",
        type_="scenario_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "field-active",
        name="field_active",
        description="Controls whether this field is visible and editable in forms",
        type_="field_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "model-active",
        name="model_active",
        description="Controls whether this AI model is available for selection by agents",
        type_="model_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "profile-active",
        name="profile_active",
        description="Controls whether this user profile is active and can access the system",
        type_="profile_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "provider-active",
        name="provider_active",
        description="Controls whether this AI provider is available for use",
        type_="provider_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "rubric-active",
        name="rubric_active",
        description="Controls whether this rubric is available for grading simulations",
        type_="rubric_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "setting-active",
        name="setting_active",
        description="Controls whether this setting is enabled and applied",
        type_="setting_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "tool-active",
        name="tool_active",
        description="Controls whether this tool is available for use by AI agents",
        type_="tool_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "cohort-active",
        name="Active",
        description="Controls whether this cohort is active and can run simulations",
        type_="cohort_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "persona-active",
        name="Active",
        description="Controls whether this persona is available for use in scenarios",
        type_="persona_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "simulation-active",
        name="Active",
        description="Controls whether this simulation is active and can be started",
        type_="simulation_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "agent-active",
        name="agent_active",
        description="Controls whether this AI agent is available for use in simulations",
        type_="agent_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "auth-active",
        name="auth_active",
        description="Controls whether this authentication method is enabled for login",
        type_="auth_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "department-active",
        name="department_active",
        description="Controls whether this department is visible in the organization structure",
        type_="department_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "document-active",
        name="document_active",
        description="Controls whether this document is available for reference in scenarios",
        type_="document_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "eval-active",
        name="eval_active",
        description="Controls whether this evaluation configuration is active and can be used",
        type_="eval_active",
        icon_id=sid("icon/power"),
    ),
    *_flag_pair(
        "simulation-rubric",
        name="simulation_rubric",
        description="Rubric used for simulation grading",
        type_="simulation_rubric",
        icon_id=sid("icon/clipboard"),
    ),
    *_flag_pair(
        "video-rubric",
        name="video_rubric",
        description="Rubric used for video grading",
        type_="video_rubric",
        icon_id=sid("icon/film"),
    ),
    *_flag_pair(
        "infinite-mode",
        name="Infinite Mode",
        description="Enable infinite mode for unlimited attempts",
        type_="infinite_mode",
        icon_id=sid("icon/infinity"),
    ),
    *_flag_pair(
        "strengths-enabled",
        name="Strengths Enabled",
        description="Enable strengths feedback for scenarios",
        type_="strengths_enabled",
        icon_id=sid("icon/star"),
    ),
    *_flag_pair(
        "use-custom",
        name="Use Custom",
        description="Allow custom configuration for scenarios",
        type_="use_custom",
        icon_id=sid("icon/settings"),
    ),
    *_flag_pair(
        "analyses-enabled",
        name="Analyses Enabled",
        description="Enable analysis feedback for scenarios",
        type_="analyses_enabled",
        icon_id=sid("icon/bar-chart"),
    ),
    *_flag_pair(
        "use-previous",
        name="Use Previous",
        description="Use previous attempt context for scenarios",
        type_="use_previous",
        icon_id=sid("icon/rewind"),
    ),
    *_flag_pair(
        "improvements-enabled",
        name="Improvements Enabled",
        description="Enable improvements feedback for scenarios",
        type_="improvements_enabled",
        icon_id=sid("icon/trending-up"),
    ),
]
