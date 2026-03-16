"""Tool definition generator — discovers tools from API routes.

Walks server/app/routes/v5/api/main/{artifact}/{operation}.py, introspects
the Pydantic request models, and produces tool definitions with args.

This is a GENERATION UTILITY, not used at seed time.
The runner imports static data from tools_data.py instead.

To regenerate tools_data.py after adding/removing API routes:
    python database/scripts/generate_tools.py
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Known IDs — from seeds/resources/operations.py and migration 116
# ---------------------------------------------------------------------------

OPERATIONS: dict[str, UUID] = {
    "get": UUID("019d0000-0001-7000-8000-000000000001"),
    "create": UUID("019d0000-0001-7000-8000-000000000002"),
    "update": UUID("019d0000-0001-7000-8000-000000000003"),
    "search": UUID("019d0000-0001-7000-8000-000000000004"),
    "docs": UUID("019d0000-0001-7000-8000-000000000005"),
    "delete": UUID("019d0000-0001-7000-8000-000000000006"),
    "duplicate": UUID("019d0000-0001-7000-8000-000000000007"),
    "draft": UUID("019d0000-0001-7000-8000-000000000008"),
    "drafts": UUID("019d0000-0001-7000-8000-000000000032"),
    "export": UUID("019d0000-0001-7000-8000-000000000010"),
    "refresh": UUID("019d0000-0001-7000-8000-000000000011"),
    "start": UUID("019d0000-0001-7000-8000-000000000012"),
    "next": UUID("019d0000-0001-7000-8000-000000000013"),
    "end": UUID("019d0000-0001-7000-8000-000000000014"),
    "end_all": UUID("019d0000-0001-7000-8000-000000000015"),
    "message": UUID("019d0000-0001-7000-8000-000000000016"),
    "grade": UUID("019d0000-0001-7000-8000-000000000017"),
    "stop": UUID("019d0000-0001-7000-8000-000000000018"),
    "response": UUID("019d0000-0001-7000-8000-000000000019"),
    "use_previous": UUID("019d0000-0001-7000-8000-000000000020"),
    "audio": UUID("019d0000-0001-7000-8000-000000000021"),
    "archive": UUID("019d0000-0001-7000-8000-000000000022"),
    "events": UUID("019d0000-0001-7000-8000-000000000023"),
    "run": UUID("019d0000-0001-7000-8000-000000000024"),
    "generate": UUID("019d0000-0001-7000-8000-000000000025"),
    "problem": UUID("019d0000-0001-7000-8000-000000000026"),
    "resolve": UUID("019d0000-0001-7000-8000-000000000027"),
    "emulate": UUID("019d0000-0001-7000-8000-000000000028"),
    "context": UUID("019d0000-0001-7000-8000-000000000029"),
    "decrypt": UUID("019d0000-0001-7000-8000-000000000030"),
    "unemulate": UUID("019d0000-0001-7000-8000-000000000031"),
}

ARTIFACTS: dict[str, UUID] = {
    "activity": UUID("019d0000-0002-7000-8000-000000000001"),
    "agent": UUID("019d0000-0002-7000-8000-000000000002"),
    "attempt": UUID("019d0000-0002-7000-8000-000000000003"),
    "auth": UUID("019d0000-0002-7000-8000-000000000004"),
    "benchmark": UUID("019d0000-0002-7000-8000-000000000005"),
    "chat": UUID("019d0000-0002-7000-8000-000000000006"),
    "cohort": UUID("019d0000-0002-7000-8000-000000000007"),
    "dashboard": UUID("019d0000-0002-7000-8000-000000000008"),
    "department": UUID("019d0000-0002-7000-8000-000000000009"),
    "document": UUID("019d0000-0002-7000-8000-000000000010"),
    "eval": UUID("019d0000-0002-7000-8000-000000000011"),
    "field": UUID("019d0000-0002-7000-8000-000000000012"),
    "group": UUID("019d0000-0002-7000-8000-000000000013"),
    "health": UUID("019d0000-0002-7000-8000-000000000014"),
    "home": UUID("019d0000-0002-7000-8000-000000000015"),
    "invocation": UUID("019d0000-0002-7000-8000-000000000016"),
    "leaderboard": UUID("019d0000-0002-7000-8000-000000000017"),
    "model": UUID("019d0000-0002-7000-8000-000000000018"),
    "parameter": UUID("019d0000-0002-7000-8000-000000000019"),
    "persona": UUID("019d0000-0002-7000-8000-000000000020"),
    "practice": UUID("019d0000-0002-7000-8000-000000000021"),
    "pricing": UUID("019d0000-0002-7000-8000-000000000022"),
    "profile": UUID("019d0000-0002-7000-8000-000000000023"),
    "provider": UUID("019d0000-0002-7000-8000-000000000024"),
    "record": UUID("019d0000-0002-7000-8000-000000000025"),
    "reports": UUID("019d0000-0002-7000-8000-000000000026"),
    "rubric": UUID("019d0000-0002-7000-8000-000000000027"),
    "scenario": UUID("019d0000-0002-7000-8000-000000000028"),
    "session": UUID("019d0000-0002-7000-8000-000000000029"),
    "setting": UUID("019d0000-0002-7000-8000-000000000030"),
    "simulation": UUID("019d0000-0002-7000-8000-000000000031"),
    "test": UUID("019d0000-0002-7000-8000-000000000032"),
    "tool": UUID("019d0000-0002-7000-8000-000000000033"),
}

# Files that are NOT operations (skip during discovery)
SKIP_FILES = {"__init__", "types", "docs", "events", "filter_helpers"}

# Deterministic ID namespace for tools and args
TOOL_NS = UUID("019d1000-0000-7000-8000-000000000000")
ARG_NS = UUID("019d2000-0000-7000-8000-000000000000")


# ---------------------------------------------------------------------------
# Type mapping — Python type annotations → args_resource field_type strings
# ---------------------------------------------------------------------------


def _python_type_to_field_type(annotation: Any) -> str:
    """Map a Python type annotation to an args_resource field_type string."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return "string"

    origin = get_origin(annotation)

    # Direct type checks (before origin-based checks)
    if annotation is str:
        return "string"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is UUID:
        return "uuid"

    # Handle list[X]
    if origin is list:
        inner_args = get_args(annotation)
        if inner_args:
            inner = _python_type_to_field_type(inner_args[0])
            return f"{inner}[]"
        return "string[]"

    # Handle dict
    if origin is dict:
        return "object"

    # Handle Union / Optional (X | None, Union[X, None])
    import types as _types

    if origin is _types.UnionType or getattr(origin, "__origin__", None) is type(None):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_field_type(non_none[0])

    # typing.Union fallback
    args = get_args(annotation)
    if args and any(a is type(None) for a in args):
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_field_type(non_none[0])

    # Pydantic model or complex type → "object"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return "object"

    return "string"


def _is_required(field_info: Any) -> bool:
    """Check if a Pydantic field is required (no default)."""
    from pydantic.fields import FieldInfo

    if isinstance(field_info, FieldInfo):
        return field_info.is_required()
    return False


def _get_default(field_info: Any) -> str:
    """Get the default value as a string, or empty string if none."""
    from pydantic.fields import FieldInfo

    if isinstance(field_info, FieldInfo):
        if field_info.default is not None and not isinstance(
            field_info.default, type(...)
        ):
            return str(field_info.default)
    return ""


# ---------------------------------------------------------------------------
# Deterministic UUID generation
# ---------------------------------------------------------------------------


def _tool_id(artifact: str, operation: str) -> UUID:
    """Generate a deterministic UUID for a tool based on artifact + operation."""
    import uuid

    return uuid.uuid5(TOOL_NS, f"{artifact}.{operation}")


def _arg_id(artifact: str, operation: str, field_name: str) -> UUID:
    """Generate a deterministic UUID for an arg based on tool + field."""
    import uuid

    return uuid.uuid5(ARG_NS, f"{artifact}.{operation}.{field_name}")


# ---------------------------------------------------------------------------
# Request type discovery
# ---------------------------------------------------------------------------


def _find_request_type(handler_module: Any) -> type[BaseModel] | None:
    """Find the Pydantic request model from a handler module.

    Looks for the route handler function's `request` parameter type annotation.
    Falls back to finding any BaseModel subclass with 'Request' in the name.
    """
    # Strategy 1: Find the route handler via router.routes
    router = getattr(handler_module, "router", None)
    if router and hasattr(router, "routes"):
        for route in router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint:
                sig = inspect.signature(endpoint)
                for param_name, param in sig.parameters.items():
                    if (
                        param_name == "request"
                        and param.annotation is not inspect.Parameter.empty
                    ):
                        ann = param.annotation
                        if isinstance(ann, type) and issubclass(ann, BaseModel):
                            return ann

    # Strategy 2: Find BaseModel subclasses with "Request" in name
    request_classes = []
    for name, obj in inspect.getmembers(handler_module, inspect.isclass):
        if (
            issubclass(obj, BaseModel)
            and obj is not BaseModel
            and "Request" in name
            and obj.__module__ == handler_module.__name__
        ):
            request_classes.append(obj)

    # If exactly one, use it. Otherwise try to find one matching common patterns.
    if len(request_classes) == 1:
        return request_classes[0]

    return None


def _extract_args_from_model(
    model_cls: type[BaseModel], artifact: str, operation: str
) -> list[dict]:
    """Extract arg definitions from a Pydantic model's fields."""
    args = []
    for field_name, field_info in model_cls.model_fields.items():
        field_type = _python_type_to_field_type(field_info.annotation)
        required = _is_required(field_info)
        default_value = _get_default(field_info)
        description = ""
        if field_info.description:
            description = field_info.description

        args.append(
            dict(
                id=_arg_id(artifact, operation, field_name),
                name=field_name,
                field_type=field_type,
                description=description,
                required=required,
                default_value=default_value,
            )
        )

    return args


# ---------------------------------------------------------------------------
# Main discovery
# ---------------------------------------------------------------------------

ROUTES_DIR = (
    Path(__file__).parent.parent.parent
    / "server"
    / "app"
    / "routes"
    / "v5"
    / "api"
    / "main"
)


def discover_tools() -> list[dict]:
    """Walk v5/api/main/ and introspect request types to build tool definitions.

    Returns a list of dicts, each with:
        - id: deterministic UUID
        - name: "{Artifact} {Operation}" (title case)
        - description: "{operation} {artifact}" or from docstring
        - artifact: folder name
        - operation: file name (without .py)
        - operation_id: UUID from OPERATIONS map
        - artifact_id: UUID from ARTIFACTS map
        - args: list of arg dicts (id, name, field_type, required, default_value, description)
    """
    tools = []
    errors = []

    if not ROUTES_DIR.exists():
        print(f"  WARNING: Routes directory not found: {ROUTES_DIR}")
        return tools

    for artifact_dir in sorted(ROUTES_DIR.iterdir()):
        if not artifact_dir.is_dir() or artifact_dir.name.startswith("_"):
            continue

        artifact = artifact_dir.name

        if artifact not in ARTIFACTS:
            errors.append(f"  WARNING: Unknown artifact '{artifact}', skipping")
            continue

        for handler_file in sorted(artifact_dir.glob("*.py")):
            operation = handler_file.stem

            if operation in SKIP_FILES:
                continue

            if operation not in OPERATIONS:
                errors.append(
                    f"  WARNING: Unknown operation '{artifact}/{operation}', skipping"
                )
                continue

            # Try to import the handler module
            module_path = f"app.routes.v5.api.main.{artifact}.{operation}"
            try:
                mod = importlib.import_module(module_path)
            except Exception as e:
                errors.append(f"  WARNING: Could not import {module_path}: {e}")
                continue

            # Find the request type and extract args
            request_type = _find_request_type(mod)
            args = []
            if request_type:
                args = _extract_args_from_model(request_type, artifact, operation)

            # Build human-readable name
            artifact_title = artifact.replace("_", " ").title()
            operation_title = operation.replace("_", " ").title()
            name = f"{artifact_title} {operation_title}"
            description = f"{operation_title} operation for {artifact_title}"

            tools.append(
                dict(
                    id=_tool_id(artifact, operation),
                    name=name,
                    description=description,
                    artifact=artifact,
                    operation=operation,
                    operation_id=OPERATIONS[operation],
                    artifact_id=ARTIFACTS[artifact],
                    args=args,
                )
            )

    # Print any warnings
    for err in errors:
        print(err)

    return tools


def generate_static_file() -> None:
    """Run discovery and write database/seeds/tools.py."""
    tools = discover_tools()

    output = Path(__file__).parent.parent / "seeds" / "tools.py"

    lines = [
        '"""Tool definitions for seeding.',
        "",
        "Regenerate with: python database/scripts/generate_tools.py",
        '"""',
        "",
        "from uuid import UUID",
        "",
        "",
        "tools = [",
    ]

    for t in tools:
        lines.append("    dict(")
        lines.append(f'        id=UUID("{t["id"]}"),')
        lines.append(f'        name="{t["name"]}",')
        lines.append(f'        description="{t["description"]}",')
        lines.append(f'        operation_id=UUID("{t["operation_id"]}"),')
        lines.append(f'        artifact_id=UUID("{t["artifact_id"]}"),')
        if t["args"]:
            lines.append("        args=[")
            for a in t["args"]:
                desc = a["description"].replace('"', '\\"') if a["description"] else ""
                default = (
                    a["default_value"].replace('"', '\\"') if a["default_value"] else ""
                )
                lines.append(
                    f'            dict(id=UUID("{a["id"]}"), name="{a["name"]}", '
                    f'field_type="{a["field_type"]}", description="{desc}", '
                    f'required={a["required"]}, default_value="{default}"),'
                )
            lines.append("        ],")
        else:
            lines.append("        args=[],")
        lines.append("    ),")

    lines.append("]")
    lines.append("")

    output.write_text("\n".join(lines))
    print(
        f"Wrote {output} ({len(tools)} tools, {sum(len(t['args']) for t in tools)} args)"
    )


if __name__ == "__main__":
    import sys

    # server/ must be on path for route module imports
    server_dir = str(Path(__file__).parent.parent.parent / "server")
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)
    generate_static_file()
