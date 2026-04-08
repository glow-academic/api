"""Resolve a tool_def dict + LLM inputs into an InfraOperationSpec.

Assembly layer that reads pre-enriched data from the tool_def dict
(populated by prepare_pipeline.py) — zero DB calls.

    tool_def["_args_outputs"]  → output_map
    tool_def["_permissions"]   → targets
    arguments_dict             → inputs
"""

from __future__ import annotations

from typing import Any

from app.infra.tools.execute_infra_operation import (
    InfraOperationSpec,
    InfraTarget,
)


def resolve_tool_spec(
    tool_def: dict[str, Any],
    inputs: dict[str, Any],
) -> InfraOperationSpec:
    """Assemble an InfraOperationSpec from a pre-enriched tool_def dict.

    Args:
        tool_def: Tool definition dict with _args_outputs and _permissions
            (enriched by prepare_pipeline.py).
        inputs: Arbitrary key-value pairs from the LLM tool call.

    Returns:
        A ready-to-execute InfraOperationSpec.

    Raises:
        ValueError: If the tool is misconfigured (missing outputs or permissions).
    """
    tool_name = tool_def.get("name", "unknown")
    args_outputs = tool_def.get("_args_outputs")
    permissions = tool_def.get("_permissions")

    if not args_outputs:
        raise ValueError(f"Tool '{tool_name}' has no output mappings (_args_outputs)")

    if not permissions:
        raise ValueError(f"Tool '{tool_name}' has no permissions (_permissions)")

    # Build output_map: {field_name: jinja_template}
    output_map: dict[str, str] = {}
    for ao in args_outputs:
        name = ao.get("name")
        template = ao.get("template")
        if name and template:
            output_map[name] = template

    if not output_map:
        raise ValueError(f"Tool '{tool_name}' has no valid output mappings")

    # Build targets: [(artifact, operation)]
    targets: list[InfraTarget] = []
    for perm in permissions:
        artifact = perm.get("artifact")
        operation = perm.get("operation")
        if artifact and operation:
            targets.append(InfraTarget(artifact=artifact, operation=operation))

    if not targets:
        raise ValueError(f"Tool '{tool_name}' has no valid permission targets")

    return InfraOperationSpec(
        inputs=inputs,
        output_map=output_map,
        targets=targets,
    )
