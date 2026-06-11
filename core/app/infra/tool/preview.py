"""Tool preview — render Jinja output templates against mock arg values.

Used by the unified Arguments step card on Tool.tsx. Returns per-output
compiled text (or per-template error), plus per-arg usage hints (which args
are referenced and which Jinja filters are applied to them) and the list of
undeclared variables referenced by templates but not declared as args.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from jinja2 import TemplateError, TemplateSyntaxError, meta, nodes
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.tool.types import (
    PreviewToolApiRequest,
    PreviewToolApiResponse,
    ToolPreviewArgHint,
    ToolPreviewOutputResult,
)
from app.utils.templates.sandbox import make_sandboxed_env


def _coerce_mock(value: str, field_type: str) -> Any:
    """Coerce the user-supplied mock string into the declared field_type.

    Falls back to the raw string on any parse error. The preview is
    advisory — the goal is to surface what the template would render with a
    plausible value, not to enforce strict typing.
    """
    if value is None:
        return ""
    if field_type == "number":
        try:
            return int(value) if value.isdigit() else float(value)
        except (ValueError, AttributeError):
            return value
    if field_type == "boolean":
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if field_type == "array":
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


def _collect_filters_for_arg(parsed: nodes.Template, arg_name: str) -> list[str]:
    """Walk a parsed Jinja AST and collect filters applied to `arg_name`."""
    filters: list[str] = []
    for filter_node in parsed.find_all(nodes.Filter):
        # Filter applies to its `node` chain — recurse to find the leaf Name.
        target: Any = filter_node.node
        while isinstance(target, nodes.Filter):
            target = target.node
        if isinstance(target, nodes.Name) and target.name == arg_name:
            filters.append(filter_node.name)
    return filters


async def preview_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: Any,
    request: PreviewToolApiRequest,
    bypass_cache: bool = False,
) -> PreviewToolApiResponse:
    """Render the supplied output templates against the mock arg values.

    Steps:
      1. Identity check — same canonical guard as decrypt.
      2. Build a Jinja env, render each template; collect compiled text or error.
      3. Parse each template's AST once to derive per-arg filter hints + the
         set of undeclared variable names (referenced but not in args).
    """
    # Identity check — minimal canonical guard (no permission gate; preview
    # is read-only against client-supplied data).
    with timed("profile"):
        await resolve_profile_identity_context(
            pool,
            profile_id=profile_id,
            redis=redis,
            bypass_cache=bypass_cache,
        )

    arg_names: set[str] = {a.name for a in request.args if a.name}
    mock_context: dict[str, Any] = {}
    for arg in request.args:
        raw = request.mock.get(arg.name, arg.default_value or "")
        mock_context[arg.name] = _coerce_mock(raw, arg.field_type or "string")

    # Sandboxed: ``template_str`` is fully client-supplied. A plain
    # Environment would let ``{{ ...__globals__... }}`` reach os.popen (RCE).
    env = make_sandboxed_env(autoescape=False, keep_trailing_newline=False)

    # Per-arg accumulators.
    used_args: set[str] = set()
    filters_by_arg: dict[str, set[str]] = {a.name: set() for a in request.args}
    undeclared_set: set[str] = set()

    output_results: list[ToolPreviewOutputResult] = []
    with timed("render"):
     for output in request.outputs:
        template_str = output.template or ""
        try:
            parsed = env.parse(template_str)
        except TemplateSyntaxError as exc:
            output_results.append(
                ToolPreviewOutputResult(
                    name=output.name,
                    compiled=None,
                    error=f"syntax error: {exc.message}",
                )
            )
            continue

        # Hints — derived per template and merged into the per-arg sets.
        referenced = meta.find_undeclared_variables(parsed)
        for ref in referenced:
            if ref in arg_names:
                used_args.add(ref)
            else:
                undeclared_set.add(ref)
        for arg_name in arg_names:
            for f in _collect_filters_for_arg(parsed, arg_name):
                filters_by_arg.setdefault(arg_name, set()).add(f)

        # Render.
        try:
            compiled = env.from_string(template_str).render(mock_context)
            output_results.append(
                ToolPreviewOutputResult(
                    name=output.name, compiled=compiled, error=None,
                )
            )
        except TemplateError as exc:
            output_results.append(
                ToolPreviewOutputResult(
                    name=output.name,
                    compiled=None,
                    error=f"render error: {exc!s}",
                )
            )

    type_hints = [
        ToolPreviewArgHint(
            name=arg.name,
            used=arg.name in used_args,
            filters=sorted(filters_by_arg.get(arg.name, set())),
        )
        for arg in request.args
        if arg.name
    ]

    return PreviewToolApiResponse(
        outputs=output_results,
        type_hints=type_hints,
        undeclared=sorted(undeclared_set),
    )
