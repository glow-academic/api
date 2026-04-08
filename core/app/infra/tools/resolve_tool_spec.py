"""Resolve a tool_def dict + LLM inputs into an InfraOperationSpec.

Assembly layer that reads pre-enriched data from the tool_def dict
(populated by prepare_pipeline.py) — zero DB calls.

The LLM specifies intent via `artifact` and `operation` fields in its
inputs. These are auto-added to every tool's input schema. If the tool
has only one permission, they default to that permission's values.

Resolution logic:
  1. Extract artifact + operation from inputs (or default if single permission)
  2. Validate (artifact, operation) is in the tool's _permissions
  3. Build a single-target InfraOperationSpec
  4. Strip artifact + operation from inputs before rendering
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
        inputs: LLM tool call arguments. May include `artifact` and
            `operation` to specify intent.

    Returns:
        A ready-to-execute InfraOperationSpec with a single target.

    Raises:
        ValueError: If the tool is misconfigured or the requested
            (artifact, operation) is not permitted.
    """
    tool_name = tool_def.get("name", "unknown")
    args_outputs = tool_def.get("_args_outputs")
    permissions = tool_def.get("_permissions")

    if not args_outputs:
        raise ValueError(f"Tool '{tool_name}' has no output mappings (_args_outputs)")

    if not permissions:
        raise ValueError(f"Tool '{tool_name}' has no permissions (_permissions)")

    # --- Resolve target (artifact, operation) from inputs ---
    # Make a mutable copy so we can strip the routing fields
    inputs = dict(inputs)
    req_artifact = inputs.pop("artifact", None)
    req_operation = inputs.pop("operation", None)

    # Build the allowed set from permissions
    allowed = {
        (p["artifact"], p["operation"])
        for p in permissions
        if p.get("artifact") and p.get("operation")
    }

    if not allowed:
        raise ValueError(f"Tool '{tool_name}' has no valid permission targets")

    if req_artifact and req_operation:
        # LLM specified intent — validate it's allowed
        target_pair = (req_artifact, req_operation)
        if target_pair not in allowed:
            raise ValueError(
                f"Tool '{tool_name}': ({req_artifact}, {req_operation}) not permitted. "
                f"Allowed: {sorted(allowed)}"
            )
    elif len(allowed) == 1:
        # Single permission — default to it
        target_pair = next(iter(allowed))
    else:
        # Multiple permissions but LLM didn't specify — error
        raise ValueError(
            f"Tool '{tool_name}' has {len(allowed)} permissions but inputs "
            f"did not specify 'artifact' and 'operation'. "
            f"Allowed: {sorted(allowed)}"
        )

    # --- Build output_map from args_outputs ---
    output_map: dict[str, str] = {}
    for ao in args_outputs:
        name = ao.get("name")
        template = ao.get("template")
        if name and template:
            output_map[name] = template

    if not output_map:
        raise ValueError(f"Tool '{tool_name}' has no valid output mappings")

    return InfraOperationSpec(
        inputs=inputs,
        output_map=output_map,
        targets=[InfraTarget(artifact=target_pair[0], operation=target_pair[1])],
    )
