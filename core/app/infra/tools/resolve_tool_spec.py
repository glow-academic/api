"""Resolve a tool_def dict + LLM inputs into an InfraOperationSpec.

Assembly layer that reads pre-enriched data from the tool_def dict
(populated by prepare_pipeline.py) — zero DB calls.

Routing (artifact + operation) is determined from args_outputs, not
from special input fields. This means routing can be:
  - Hardcoded:    template="agent"                    (single-permission tools)
  - Pass-through: template="{{ artifact }}"           (multi-permission tools)
  - Conditional:  template="{% if x %}persona{% else %}scenario{% endif %}"

The args_outputs named "artifact" and "operation" are rendered first
to determine routing, then stripped from the output_map before execution.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment

from app.infra.tools.execute_infra_operation import (
    InfraOperationSpec,
    InfraTarget,
)

_jinja_env = Environment(
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def resolve_tool_spec(
    tool_def: dict[str, Any],
    inputs: dict[str, Any],
) -> InfraOperationSpec:
    """Assemble an InfraOperationSpec from a pre-enriched tool_def dict.

    Args:
        tool_def: Tool definition dict with _args_outputs and _permissions
            (enriched by prepare_pipeline.py).
        inputs: LLM tool call arguments.

    Returns:
        A ready-to-execute InfraOperationSpec with a single target.

    Raises:
        ValueError: If the tool is misconfigured or the resolved
            (artifact, operation) is not permitted.
    """
    tool_name = tool_def.get("name", "unknown")
    args_outputs = tool_def.get("_args_outputs")
    permissions = tool_def.get("_permissions")

    if not args_outputs:
        raise ValueError(f"Tool '{tool_name}' has no output mappings (_args_outputs)")

    if not permissions:
        raise ValueError(f"Tool '{tool_name}' has no permissions (_permissions)")

    # --- Separate routing outputs from payload outputs ---
    routing_templates: dict[str, str] = {}
    payload_outputs: dict[str, str] = {}

    for ao in args_outputs:
        name = ao.get("name")
        template = ao.get("template")
        if not name or not template:
            continue
        if name in ("artifact", "operation"):
            routing_templates[name] = template
        else:
            payload_outputs[name] = template

    # --- Resolve routing by rendering artifact + operation templates ---
    req_artifact = None
    req_operation = None

    if "artifact" in routing_templates:
        rendered = _jinja_env.from_string(routing_templates["artifact"]).render(**inputs)
        req_artifact = rendered.strip() if rendered.strip() else None

    if "operation" in routing_templates:
        rendered = _jinja_env.from_string(routing_templates["operation"]).render(**inputs)
        req_operation = rendered.strip() if rendered.strip() else None

    # --- Validate against permissions ---
    allowed = {
        (p["artifact"], p["operation"])
        for p in permissions
        if p.get("artifact") and p.get("operation")
    }

    if not allowed:
        raise ValueError(f"Tool '{tool_name}' has no valid permission targets")

    if req_artifact and req_operation:
        target_pair = (req_artifact, req_operation)
        if target_pair not in allowed:
            raise ValueError(
                f"Tool '{tool_name}': ({req_artifact}, {req_operation}) not permitted. "
                f"Allowed: {sorted(allowed)}"
            )
    elif len(allowed) == 1:
        target_pair = next(iter(allowed))
    else:
        raise ValueError(
            f"Tool '{tool_name}' has {len(allowed)} permissions but routing "
            f"could not be resolved. Ensure args_outputs include 'artifact' "
            f"and 'operation' templates. Allowed: {sorted(allowed)}"
        )

    # --- Build spec with payload outputs only ---
    if not payload_outputs:
        raise ValueError(f"Tool '{tool_name}' has no payload output mappings")

    return InfraOperationSpec(
        inputs=inputs,
        output_map=payload_outputs,
        targets=[InfraTarget(artifact=target_pair[0], operation=target_pair[1])],
    )
