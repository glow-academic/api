"""Generate system + instructions prompts for the 11 view-agent prompts.

After the route flattening + tool retag pass, each view collapsed to a
SINGLE tool whose name reflects the new flat route (e.g. System_Activity
instead of Activity_Get + Activity_Search).

View agents are read-only: they retrieve data using the view's single tool
(which accepts filter args) and answer the user in plain text. There is
NO create_insights tool — the old insights-style prompts invented one.

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
# Per-view spec — one tool per view (post-flatten reality)
# ---------------------------------------------------------------------------

VIEWS: list[dict] = [
    {
        "slug": "activity",
        "view": "Activity",
        "tool_name": "System_Activity",
        "domain": "platform-wide activity (recent sessions, events, errors)",
        "args": ["date_from", "date_to", "department_ids", "roles", "active",
                 "page", "page_size", "sort_order"],
        "example_filter": 'date_from: "2026-04-01", department_ids: ["dept-uuid"]',
        "extras": [],
    },
    {
        "slug": "dashboard",
        "view": "Dashboard",
        "tool_name": "Attempt_Dashboard",
        "domain": "high-level KPIs, usage trends, and department comparisons",
        "args": ["start_date", "end_date", "cohort_ids", "department_ids",
                 "target_profile_id", "practice", "scenario_ids", "infinite_mode",
                 "show_archived", "sort_by", "sort_order", "page", "page_size",
                 "simulation_search", "scenario_search", "profile_search"],
        "example_filter": 'start_date: "2026-04-01", end_date: "2026-05-01", department_ids: ["dept-uuid"]',
        "extras": [],
    },
    {
        "slug": "group",
        "view": "Group",
        "tool_name": "System_Group",
        "domain": "the current chat conversation thread (each chat is a 'group')",
        "args": ["search", "agent_id", "model_id", "date_from", "date_to",
                 "sort_by", "sort_order", "page_limit", "page_offset"],
        "example_filter": 'agent_id: "agent-uuid", date_from: "2026-04-01"',
        "extras": [
            ("System_Groups", "(search, agent_id, model_id, date_from, date_to, sort_by, sort_order, page_limit, page_offset)",
             "Paginated list of all chat groups across the system."),
        ],
    },
    {
        "slug": "health",
        "view": "Health",
        "tool_name": "System_Health",
        "domain": "service health snapshots across GPU services, queues, and dependencies",
        "args": ["service", "date_from", "date_to", "page_limit", "page_offset"],
        "example_filter": 'service: "tts", date_from: "2026-05-01"',
        "extras": [],
    },
    {
        "slug": "home",
        "view": "Home",
        "tool_name": "Attempt_Home",
        "domain": "the user's home overview — recommended training, in-progress sessions, recent activity",
        "args": ["sort_by", "sort_order", "page", "page_size",
                 "simulation_search", "scenario_search", "scenario_ids", "infinite_mode"],
        "example_filter": 'scenario_search: "triage"',
        "extras": [],
    },
    {
        "slug": "leaderboard",
        "view": "Leaderboard",
        "tool_name": "Attempt_Leaderboard",
        "domain": "performance rankings across profiles, departments, and training programs",
        "args": ["start_date", "end_date", "cohort_ids", "simulation_ids",
                 "department_ids", "simulation_filters", "target_profile_id",
                 "cohort_id", "simulation_id", "scenario_ids", "search",
                 "sort_by", "sort_order", "page_limit", "page_offset"],
        "example_filter": 'start_date: "2026-04-01", cohort_ids: ["cohort-uuid"]',
        "extras": [],
    },
    {
        "slug": "practice",
        "view": "Practice",
        "tool_name": "Attempt_Practice",
        "domain": "the practice catalog — available scenarios for self-directed practice",
        "args": ["sort_by", "sort_order", "page", "page_size",
                 "simulation_search", "scenario_search", "show_archived",
                 "scenario_ids", "infinite_mode"],
        "example_filter": 'scenario_search: "intake"',
        "extras": [],
    },
    {
        "slug": "pricing",
        "view": "Pricing",
        "tool_name": "System_Pricing",
        "domain": "usage volume and cost breakdowns across providers, models, and time windows",
        "args": ["start_date", "end_date", "date_from", "date_to",
                 "page", "page_size", "sort_order"],
        "example_filter": 'start_date: "2026-04-01", end_date: "2026-05-01"',
        "extras": [],
    },
    {
        "slug": "record",
        "view": "Record",
        "tool_name": "Attempt_Report",  # record collapsed into report after flatten
        "domain": "scoped attempt reports — drillable views of how profiles performed",
        "args": ["start_date", "end_date", "cohort_ids", "simulation_ids",
                 "department_ids", "roles", "simulation_filters",
                 "actor_profile_id", "target_profile_id", "profile_ids",
                 "scenario_ids", "search", "sort_by", "sort_order",
                 "page_limit", "page_offset"],
        "example_filter": 'start_date: "2026-04-01", cohort_ids: ["cohort-uuid"]',
        "extras": [],
    },
    {
        "slug": "reports",
        "view": "Reports",
        "tool_name": "Attempt_Report",
        "domain": "scoped attempt reports — drillable views of how profiles performed",
        "args": ["start_date", "end_date", "cohort_ids", "simulation_ids",
                 "department_ids", "roles", "simulation_filters",
                 "actor_profile_id", "target_profile_id", "profile_ids",
                 "scenario_ids", "search", "sort_by", "sort_order",
                 "page_limit", "page_offset"],
        "example_filter": 'start_date: "2026-04-01", simulation_ids: ["sim-uuid"]',
        "extras": [],
    },
    {
        "slug": "session",
        "view": "Session",
        "tool_name": "System_Session",
        "domain": "training session details — per-session metadata, scores, and timeline",
        "args": ["active", "date_from", "date_to", "department_ids", "roles",
                 "sort_by", "sort_order", "page_limit", "page_offset"],
        "example_filter": 'active: true, date_from: "2026-04-01"',
        "extras": [],
    },
]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


SYSTEM_TMPL = Template(
    """You are the $VIEW view agent. You answer the user's questions about $DOMAIN by retrieving data with the read-only $VIEW tools and replying in plain text.

## How It Works

The $VIEW view is read-only. Its primary tool is `$TOOL` — a single endpoint that takes optional filters as args. Pass `$TOOL()` for the headline view, or pass any subset of args to scope down. You do not create, edit, or delete records here — you retrieve and explain what's there.

## Tools

- `$TOOL` — fetch the $VIEW view, optionally filtered. Args: $ARGS_LIST.
$EXTRAS

## Examples

Headline view (no filters):
```
$TOOL()
```

Filtered query:
```
$TOOL($EXAMPLE_FILTER)
```

## Guidelines

- **Use tool calls to retrieve data; answer the user in plain text.** Fetch then narrate concisely. Do not invent values — every number in your reply should come from a tool result.
- **Reuse what's already in conversation — do NOT re-fetch.** Prior `$TOOL` results persist as chat messages the user can still see. If a matching prior render exists, answer from it. Re-fetch only when (a) no matching prior render exists, or (b) the user explicitly asks for a refresh.
- **Filters do the slicing for you.** When the user asks for a date range, department, cohort, or other slice, pass the corresponding arg on `$TOOL` — do not retrieve everything and post-filter in your head.
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

Retrieve the data the user is asking about by calling `$TOOL` with the right filter args, then answer in plain text.

- For the overall headline (no filters), call `$TOOL()`.
- For any slice (date range, department, cohort, etc.), pass the relevant filter args: $ARGS_LIST.
$EXTRAS_LINES

**Prior tool renders persist as chat messages the user can still see.** Do NOT re-fetch when a recent `$TOOL` result is already in the conversation — answer from it. Do NOT restate or re-list a render that's literally just above your reply; reference it briefly instead.

Cite specific numbers from the data. Do not invent values. Answer the question asked, not adjacent ones.
"""
)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def fmt_args(args: list[str]) -> str:
    if not args:
        return "(no filter args)"
    return ", ".join(f"`{a}`" for a in args)


def render_system(spec: dict) -> str:
    extras_block = ""
    if spec["extras"]:
        lines = []
        for tool_name, tool_args, desc in spec["extras"]:
            lines.append(f"- `{tool_name}{tool_args}` — {desc}")
        extras_block = "\n" + "\n".join(lines)

    return SYSTEM_TMPL.substitute(
        VIEW=spec["view"],
        TOOL=spec["tool_name"],
        DOMAIN=spec["domain"],
        ARGS_LIST=fmt_args(spec["args"]),
        EXTRAS=extras_block,
        EXAMPLE_FILTER=spec["example_filter"],
    )


def render_instructions(spec: dict) -> str:
    extras_block = ""
    if spec["extras"]:
        lines = []
        for tool_name, tool_args, desc in spec["extras"]:
            lines.append(f"- `{tool_name}{tool_args}` — {desc}")
        extras_block = "\n".join(lines)

    return INSTRUCTIONS_TMPL.substitute(
        TOOL=spec["tool_name"],
        ARGS_LIST=fmt_args(spec["args"]),
        EXTRAS_LINES=extras_block,
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
        if args.write:
            system_path.write_text(render_system(spec), encoding="utf-8")
            instr_path.write_text(render_instructions(spec), encoding="utf-8")
        written += 2
        print(f"  {'wrote' if args.write else 'would write'}: {system_path.name}, {instr_path.name}")

    print(f"\n{'wrote' if args.write else 'would write'}: {written} files")
    if not args.write:
        print("(dry run — pass --write to apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
