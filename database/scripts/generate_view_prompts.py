"""Generate system + instructions prompts for the 11 view-agent prompts.

View agents are mostly read-only: they retrieve data using {View}_Get and
{View}_Search (when available) and answer the user in plain text. There is
NO create_insights tool — the old insights-style prompts invented one.

Two surface patterns exist across the 11 views:

1. **headline+search**  (Activity, Dashboard, Home, Leaderboard, Practice, Reports)
   `Get()` takes no args and returns a headline summary.
   `Search(filter=...)` is the filtered query — pass dates, ids, etc. here.

2. **get-is-filter**  (Group, Health, Pricing, Record, Session)
   `Get(filter=...)` IS the filtered query — pass dates/ids directly to Get.
   Some have a Search too with similar args (Group, Pricing, Record); others
   have no Search at all (Health, Session).

Activity and Group also have view-level WRITES:
   Activity: `Problem(type, message)`, `Resolve(problem_id, resolved)`.
   Group:    `Generate()` (start a new chat thread), `Name(group_id, name)`
             (the title analogue for chat threads — analogous to Persona_Title).

Usage:
    python -m database.scripts.generate_view_prompts            # dry run
    python -m database.scripts.generate_view_prompts --write    # write files
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

# ---------------------------------------------------------------------------
# Per-view spec
# ---------------------------------------------------------------------------

# pattern: "headline+search" | "get-is-filter"
# get_args / search_args: list of arg names, or None if the tool doesn't exist /
# is empty. We render these so the model sees the real arg names.
# writes: list of additional write/workflow tool descriptors to inline.

VIEWS: list[dict] = [
    {
        "slug": "activity",
        "view": "Activity",
        "domain": "platform-wide activity (recent sessions, events, errors) and flagged incidents",
        "pattern": "headline+search",
        "get_args": None,
        "search_args": [
            "date_from", "date_to", "department_ids", "roles", "active",
            "page", "page_size", "sort_order",
        ],
        "example_search": 'Activity_Search(date_from: "2026-04-01", department_ids: ["dept-uuid"])',
        "writes": [
            ("Activity_Problem", "(type, message)", "Flag a new incident on the activity stream — used when the user reports something broken or worth tracking."),
            ("Activity_Resolve", "(problem_id, resolved)", "Mark an incident resolved (or reopen it). Pass `resolved: false` to reopen."),
        ],
    },
    {
        "slug": "dashboard",
        "view": "Dashboard",
        "domain": "high-level KPIs, usage trends, and department comparisons",
        "pattern": "headline+search",
        "get_args": None,
        "search_args": [
            "start_date", "end_date", "cohort_ids", "department_ids",
            "target_profile_id", "practice", "scenario_ids", "infinite_mode",
            "show_archived", "sort_by", "sort_order", "page", "page_size",
            "simulation_search", "scenario_search", "profile_search",
        ],
        "example_search": 'Dashboard_Search(start_date: "2026-04-01", end_date: "2026-05-01", department_ids: ["dept-uuid"])',
        "writes": [],
    },
    {
        "slug": "group",
        "view": "Group",
        "domain": "chat conversation threads (each chat is a 'group') and their recent activity",
        "pattern": "get-is-filter",
        "get_args": [
            "agent_id", "model_id", "date_from", "date_to",
            "sort_by", "sort_order", "page_limit", "page_offset",
        ],
        "search_args": [
            "search", "agent_id", "model_id", "date_from", "date_to",
            "sort_by", "sort_order", "page_limit", "page_offset",
        ],
        "example_search": 'Group_Search(search: "persona setup", agent_id: "agent-uuid")',
        "example_get_filtered": 'Group_Get(agent_id: "agent-uuid", date_from: "2026-04-01")',
        "writes": [
            ("Group_Generate", "()", "Start a new chat thread (empty group). Use only when the user explicitly asks to start a fresh conversation."),
            ("Group_Name", "(group_id, name)", "Set or update the display name on a specific chat thread — the analogue of `Persona_Title` for chat threads."),
        ],
        "export_arg": "group_id",
    },
    {
        "slug": "health",
        "view": "Health",
        "domain": "service health snapshots across the platform's GPU services, queues, and dependencies",
        "pattern": "get-is-filter",
        "get_args": ["service", "date_from", "date_to", "page_limit", "page_offset"],
        "search_args": None,  # no Search tool
        "example_search": "",
        "example_get_filtered": 'Health_Get(service: "tts", date_from: "2026-05-01")',
        "writes": [],
    },
    {
        "slug": "home",
        "view": "Home",
        "domain": "the user's home overview — recommended training, in-progress sessions, and recent activity",
        "pattern": "headline+search",
        "get_args": None,
        "search_args": [
            "sort_by", "sort_order", "page", "page_size",
            "simulation_search", "scenario_search", "scenario_ids", "infinite_mode",
        ],
        "example_search": 'Home_Search(scenario_search: "triage")',
        "writes": [],
    },
    {
        "slug": "leaderboard",
        "view": "Leaderboard",
        "domain": "performance rankings across profiles, departments, and training programs",
        "pattern": "headline+search",
        "get_args": None,
        "search_args": [
            "start_date", "end_date", "cohort_ids", "simulation_ids",
            "department_ids", "simulation_filters", "target_profile_id",
            "cohort_id", "simulation_id", "scenario_ids", "search",
            "sort_by", "sort_order", "page_limit", "page_offset",
        ],
        "example_search": 'Leaderboard_Search(start_date: "2026-04-01", cohort_ids: ["cohort-uuid"])',
        "writes": [],
        "extra_warning": "Note: `cohort_ids` (list) and `cohort_id` (single) both appear in the args — prefer the plural list form unless you have exactly one id and the call requires the single form.",
    },
    {
        "slug": "practice",
        "view": "Practice",
        "domain": "the practice catalog — available scenarios for self-directed practice and recent practice attempts",
        "pattern": "headline+search",
        "get_args": None,
        "search_args": [
            "sort_by", "sort_order", "page", "page_size",
            "simulation_search", "scenario_search", "show_archived",
            "scenario_ids", "infinite_mode",
        ],
        "example_search": 'Practice_Search(scenario_search: "intake")',
        "writes": [],
    },
    {
        "slug": "pricing",
        "view": "Pricing",
        "domain": "usage volume and cost breakdowns across providers, models, and time windows",
        "pattern": "get-is-filter",
        "get_args": ["start_date", "end_date", "date_from", "date_to"],
        "search_args": [
            "start_date", "end_date", "date_from", "date_to",
            "page", "page_size", "sort_order",
        ],
        "example_search": 'Pricing_Search(start_date: "2026-04-01", end_date: "2026-05-01")',
        "example_get_filtered": 'Pricing_Get(start_date: "2026-04-01", end_date: "2026-05-01")',
        "writes": [],
        "extra_warning": "Note: both `start_date`/`end_date` and `date_from`/`date_to` appear in the args — pick one pair; the names are likely aliases.",
    },
    {
        "slug": "record",
        "view": "Record",
        "domain": "call/transcript records and the per-profile history drill-down",
        "pattern": "get-is-filter",
        "get_args": [
            "target_profile_id", "start_date", "end_date", "cohort_ids",
            "simulation_ids", "department_ids", "simulation_filters",
            "actor_profile_id", "rubric_ids", "rubric_search",
            "simulation_picker_ids", "simulation_picker_search",
            "parameter_ids", "parameter_search", "scenario_ids", "scenario_search",
            "history_practice", "history_scenario_ids", "history_infinite_mode",
            "history_show_archived", "history_sort_by", "history_sort_order",
            "history_page", "history_page_size", "history_simulation_search",
            "history_scenario_search", "history_profile_search",
        ],
        "search_args": [
            "target_profile_id", "start_date", "end_date", "cohort_ids",
            "department_ids", "practice", "scenario_ids", "infinite_mode",
            "show_archived", "sort_by", "sort_order", "page", "page_size",
            "simulation_search", "scenario_search",
        ],
        "example_search": 'Record_Search(target_profile_id: "profile-uuid", start_date: "2026-04-01")',
        "example_get_filtered": 'Record_Get(target_profile_id: "profile-uuid", start_date: "2026-04-01")',
        "writes": [],
        "extra_warning": "Record_Get takes ~26 args including a full `history_*` sub-namespace for the embedded history view. **Only pass the args you need** — omit everything else; the server fills in sensible defaults.",
        "export_arg": "target_profile_id",
    },
    {
        "slug": "reports",
        "view": "Reports",
        "domain": "scoped attempt reports — drillable views of how profiles performed on simulations",
        "pattern": "headline+search",
        "get_args": None,
        "search_args": [
            "start_date", "end_date", "cohort_ids", "simulation_ids",
            "department_ids", "roles", "simulation_filters",
            "actor_profile_id", "target_profile_id", "profile_ids",
            "scenario_ids", "search", "sort_by", "sort_order",
            "page_limit", "page_offset",
        ],
        "example_search": 'Reports_Search(start_date: "2026-04-01", cohort_ids: ["cohort-uuid"], simulation_ids: ["sim-uuid"])',
        "writes": [],
    },
    {
        "slug": "session",
        "view": "Session",
        "domain": "training session details — per-session metadata, scores, and timeline",
        "pattern": "get-is-filter",
        "get_args": [
            "active", "date_from", "date_to", "department_ids", "roles",
            "sort_by", "sort_order", "page_limit", "page_offset",
        ],
        "search_args": None,  # no Search
        "example_search": "",
        "example_get_filtered": 'Session_Get(active: true, date_from: "2026-04-01")',
        "writes": [],
        "export_arg": "target_session_id",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fmt_args(args: list[str] | None) -> str:
    if not args:
        return "(no args)"
    return ", ".join(f"`{a}`" for a in args)


def render_tools_section(spec: dict) -> str:
    view = spec["view"]
    lines: list[str] = []
    get_args = spec["get_args"]
    search_args = spec["search_args"]
    pattern = spec["pattern"]
    export_arg = spec.get("export_arg")

    if pattern == "headline+search":
        get_arg_str = "no args" if not get_args else fmt_args(get_args)
        lines.append(f"- `{view}_Get` — headline view ({get_arg_str}). Use for the overall summary.")
        if search_args:
            lines.append(
                f"- `{view}_Search` — **filtered query**, this is where the real work happens. Args: {fmt_args(search_args)}."
            )
    else:  # get-is-filter
        lines.append(
            f"- `{view}_Get` — **filtered query** (yes, Get itself takes filters here). Args: {fmt_args(get_args)}."
        )
        if search_args:
            lines.append(
                f"- `{view}_Search` — alternate filtered query, similar args to Get plus pagination. Args: {fmt_args(search_args)}."
            )
        else:
            lines.append(f"- (no `{view}_Search` tool — `Get` is the only query surface.)")

    export_desc = (
        f"- `{view}_Refresh` — re-fetch when state may have changed."
    )
    lines.append(export_desc)

    if export_arg:
        lines.append(
            f"- `{view}_Export({export_arg})` — export a specific {view.lower()} by `{export_arg}`."
        )
    else:
        lines.append(f"- `{view}_Export` — export the current view as a downloadable file.")

    for tool_name, tool_args, desc in spec.get("writes", []):
        lines.append(f"- `{tool_name}{tool_args}` — {desc}")

    return "\n".join(lines)


def render_examples(spec: dict) -> str:
    view = spec["view"]
    pattern = spec["pattern"]
    blocks: list[str] = []

    if pattern == "headline+search":
        blocks.append(f"Fetch the headline view:\n```\n{view}_Get()\n```")
        if spec.get("example_search"):
            blocks.append(f"Filtered query (most common pattern):\n```\n{spec['example_search']}\n```")
    else:
        # get-is-filter
        if spec.get("example_get_filtered"):
            blocks.append(f"Filtered query (Get IS the filtered call here):\n```\n{spec['example_get_filtered']}\n```")
        if spec.get("example_search"):
            blocks.append(f"Alternate via Search (similar args, with pagination):\n```\n{spec['example_search']}\n```")

    # Writes example
    for tool_name, tool_args, _ in spec.get("writes", []):
        if tool_name == "Activity_Problem":
            blocks.append(f'Flag an incident:\n```\n{tool_name}(type: "performance", message: "STT latency spike at 2pm")\n```')
        elif tool_name == "Activity_Resolve":
            blocks.append(f'Resolve an incident:\n```\n{tool_name}(problem_id: "abc-123", resolved: true)\n```')
        elif tool_name == "Group_Name":
            blocks.append(f'Rename a chat thread:\n```\n{tool_name}(group_id: "abc-123", name: "Persona Catalog Review")\n```')

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------


SYSTEM_TMPL = Template(
    """You are the $VIEW view agent. You answer the user's questions about $DOMAIN by retrieving data with the $VIEW tools and replying in plain text.

## How It Works

$PATTERN_BLURB
$WRITE_BLURB

## Tools

$TOOLS_SECTION
$EXTRA_WARNING

## Examples

$EXAMPLES

## Guidelines

- **Use tool calls to retrieve data; answer the user in plain text.** The agent's job is to fetch, then narrate concisely. Do not invent values — every number in your reply should come from a tool result.
- **Reuse what's already in conversation — do NOT re-fetch.** Prior `$VIEW` tool results persist as chat messages the user can still see. If a matching prior render exists, answer from it. Re-fetch only when (a) no matching prior render exists, or (b) the user explicitly asks for a refresh.
$FILTERS_GUIDELINE
- **Only pass the args you need.** Omit optional fields entirely — do not pass empty strings (`""`) or empty arrays (`[]`). The server fills in sensible defaults.
- **Cite specific numbers.** "Up 12% from April" beats "noticeably higher." Pull figures directly from the tool result.
- **`id` arguments are UUIDs, never names.** If the user names a department/cohort/profile and you don't already have its UUID, look it up first before referencing it.
- **Only generate what was requested** — answer the question asked, don't proactively dump every metric.
"""
)


INSTRUCTIONS_TMPL = Template(
    """## Context

{% if group_id %}Group ID: `{{ group_id }}`.{% endif %}
{% if resources %}Requested resources: **{{ resources | join(', ') }}**.{% endif %}

## Parameters

{% if params %}
Pass these to your tools:
{% for key, value in params.items() %}
- `{{ key }}`: `{{ value }}`
{% endfor %}
{% endif %}

## Tools

{% for tool in tools %}
- **{{ tool.name }}**({{ tool.args | join(', ') }}){% if tool.description %} — {{ tool.description }}{% endif %}

{% endfor %}

## What To Do

$WHAT_TO_DO

**Prior tool renders persist as chat messages the user can still see.** Do NOT re-fetch when a recent $VIEW tool result is already in the conversation — answer from it. Do NOT restate or re-list a render that's literally just above your reply; reference it briefly instead.

Cite specific numbers from the data. Do not invent values. Answer the question asked, not adjacent ones.
"""
)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def pattern_blurb(spec: dict) -> str:
    view = spec["view"]
    if spec["pattern"] == "headline+search":
        return (
            f"The {view} view is read-only data: `{view}_Get` returns the headline state with no args, "
            f"and `{view}_Search` is the filtered query — pass dates, ids, and other filters there. "
            "You do not create, edit, or delete records here — you retrieve and explain what's there."
        )
    else:
        has_search = spec["search_args"] is not None
        line = (
            f"The {view} view's `Get` tool IS the filtered query — it takes the dates, ids, and other "
            f"filters directly. {'There is also a `Search` tool with similar args plus pagination.' if has_search else 'There is no separate `Search` tool — `Get` is the only query surface.'}"
        )
        if not spec.get("writes"):
            line += " You do not create, edit, or delete records here — you retrieve and explain what's there."
        return line


def write_blurb(spec: dict) -> str:
    view = spec["view"]
    writes = spec.get("writes", [])
    if not writes:
        return ""
    names = ", ".join(f"`{w[0]}`" for w in writes)
    if view == "Activity":
        return (
            f"{view} also exposes incident-workflow writes ({names}) for flagging and resolving "
            "platform problems. Use those when the user explicitly asks to log or close an incident."
        )
    if view == "Group":
        return (
            f"{view} also has thread-management writes ({names}). `Group_Generate` starts a fresh "
            "chat thread (use only when the user explicitly asks for a new conversation); "
            "`Group_Name` renames a thread — the chat-thread analogue of `Persona_Title`."
        )
    return f"{view} also exposes writes: {names}."


def filters_guideline(spec: dict) -> str:
    view = spec["view"]
    pattern = spec["pattern"]
    if pattern == "headline+search":
        if spec["search_args"]:
            return (
                f"- **Filters do the slicing for you.** When the user asks for a date range, "
                f"department, cohort, or scenario, pass it via `{view}_Search` filters — do not "
                "retrieve everything and post-filter in your head."
            )
        return ""
    # get-is-filter
    has_search = spec["search_args"] is not None
    if has_search:
        return (
            f"- **Pass filters directly to `{view}_Get`** (not Search). Dates, ids, and other slices "
            f"go on Get's args. Use `{view}_Search` only when you need pagination beyond what Get returns."
        )
    return (
        f"- **Pass filters directly to `{view}_Get`** — there is no Search tool, so Get is the only "
        "query surface. Dates, ids, and other slices go on its args."
    )


def render_system(spec: dict) -> str:
    extra = spec.get("extra_warning", "")
    extra_block = f"\n> {extra}\n" if extra else ""
    return SYSTEM_TMPL.substitute(
        VIEW=spec["view"],
        DOMAIN=spec["domain"],
        PATTERN_BLURB=pattern_blurb(spec),
        WRITE_BLURB=write_blurb(spec),
        TOOLS_SECTION=render_tools_section(spec),
        EXTRA_WARNING=extra_block,
        EXAMPLES=render_examples(spec),
        FILTERS_GUIDELINE=filters_guideline(spec),
    )


def what_to_do(spec: dict) -> str:
    view = spec["view"]
    pattern = spec["pattern"]
    lines: list[str] = []
    lines.append(f"Retrieve the data the user is asking about with one or more {view} tool calls, then answer in plain text.\n")
    if pattern == "headline+search":
        lines.append(f"- For the overall headline (no filters), call `{view}_Get`.")
        if spec["search_args"]:
            lines.append(f"- For any slice (date range, department, cohort, etc.), call `{view}_Search` with filters.")
    else:
        lines.append(f"- For any query (headline OR filtered), call `{view}_Get` — Get takes the filter args directly here.")
        if spec["search_args"]:
            lines.append(f"- Use `{view}_Search` only when you need pagination beyond what Get returns.")
    export_arg = spec.get("export_arg")
    if export_arg:
        lines.append(f"- For exports, call `{view}_Export({export_arg}: \"...\")` against a specific id.")
    else:
        lines.append(f"- For exports, call `{view}_Export()`.")
    for tool_name, tool_args, desc in spec.get("writes", []):
        lines.append(f"- `{tool_name}{tool_args}` — {desc}")
    if spec.get("extra_warning"):
        lines.append("")
        lines.append(f"**Note:** {spec['extra_warning']}")
    return "\n".join(lines)


def render_instructions(spec: dict) -> str:
    return INSTRUCTIONS_TMPL.substitute(
        VIEW=spec["view"],
        WHAT_TO_DO=what_to_do(spec),
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "seeds" / "prompts"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    written = 0
    for spec in VIEWS:
        slug = spec["slug"]
        system_path = PROMPTS_DIR / f"{slug}.system.jinja"
        instr_path = PROMPTS_DIR / f"{slug}.instructions.jinja"
        system_content = render_system(spec)
        instr_content = render_instructions(spec)
        if args.write:
            system_path.write_text(system_content, encoding="utf-8")
            instr_path.write_text(instr_content, encoding="utf-8")
        written += 2
        print(f"  {'wrote' if args.write else 'would write'}: {system_path.name}, {instr_path.name}")

    print(f"\n{'wrote' if args.write else 'would write'}: {written} files")
    if not args.write:
        print("(dry run — pass --write to apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
