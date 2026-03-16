"""Pure helper functions extracted from the generation pipeline.

No I/O, no globals — safe to import anywhere.
"""

from __future__ import annotations

from typing import Any


def aggregate_tool_results(
    all_tool_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build resource_actions and entry_actions from accumulated tool results.

    Returns: (resource_actions, entry_actions)

    resource_actions: {resource_type: {"resource_id": id}}
    entry_actions:    {entry_type: [{"entry_id": id}]}  (list, since multiple entries per type)
    """
    resource_actions: dict[str, Any] = {}
    entry_actions: dict[str, Any] = {}

    for tr in all_tool_results:
        if not isinstance(tr, dict):
            continue
        result = tr.get("result") if isinstance(tr.get("result"), dict) else tr

        # Resources
        rt = tr.get("resource_type") or result.get("resource_type")
        rid = tr.get("resource_id") or result.get("resource_id")
        if rt and rid:
            resource_actions[rt] = {"resource_id": rid}

        # Entries
        et = tr.get("entry_type") or result.get("entry_type")
        eid = tr.get("entry_id") or result.get("entry_id")
        if et and eid:
            entry_actions.setdefault(et, []).append({"entry_id": eid})

    return resource_actions, entry_actions
