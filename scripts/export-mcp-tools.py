#!/usr/bin/env python3
"""Export MCP tool definitions to mcp-tools.json.

Walks the tool graph, imports each route handler, extracts the Pydantic
request model, and outputs structured JSON that docs pipelines consume.

Usage:
    cd core && python ../scripts/export-mcp-tools.py [output_path]
"""

import json
import os
import sys

# core/ must be on the path for app.* imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from app.infra.mcp.tool_graph import get_mcp_tool_graph
from app.infra.mcp.register import _import_handler, _get_request_model, _build_tool_args


def export_tools() -> dict:
    tools = []
    errors = []

    for artifact, operation in get_mcp_tool_graph():
        module_path = f"app.routes.{artifact}.{operation}"
        try:
            handler = _import_handler(module_path)
            model = _get_request_model(handler) if handler else None
            parameters = _build_tool_args(model) if model else []
            # Strip verbose nested schema — docs only need name/type/required/description
            for p in parameters:
                p.pop("schema", None)
            description = ((handler.__doc__ or "").strip()) if handler else ""
        except Exception as e:
            errors.append(f"{operation}_{artifact}: {e}")
            parameters = []
            description = ""

        tools.append({
            "name": f"{operation}_{artifact}",
            "description": description or f"{operation} {artifact}",
            "parameters": parameters,
            "artifact": artifact,
            "operation": operation,
        })

    if errors:
        print(f"Warnings ({len(errors)}):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)

    return {"name": "Glow", "tool_count": len(tools), "tools": tools}


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "mcp-tools.json"
    data = export_tools()
    with open(output, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported {data['tool_count']} tools → {output}")
