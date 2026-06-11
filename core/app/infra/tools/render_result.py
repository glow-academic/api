"""Layer 3 — render an InfraOperationResult list into the LLM-facing string.

The tool_def's ``_instruction_template`` is the canonical Jinja template
seeded at ``database/seeds/tool_instructions/<slug>.jinja``. The template
is rendered against a wrapped result dict — ``{success, results, result}``
— where ``result`` is an alias for the whole wrapper so templates can
reference either top-level keys or nested ``result.results[0]...``.

Shared by the generate pipeline (replaces the inline block at
execute.py:606–649) and the MCP dispatch handler.

``render_tool_result`` returns a plain ``str`` for backward compatibility
with the MCP path, which only cares about the LLM-facing payload.

``render_tool_result_with_meta`` returns ``RenderedToolResult`` carrying
both the rendered string and the structured wrapper (``success`` plus
per-target results). The generate pipeline uses this so it can emit the
true success state on ``{artifact}.generate.call.complete`` even when the
rendered LLM-facing string is plain text/markdown that won't parse back
to JSON. Without it, every templated tool was emitted as ``success=False``
because the WS emit re-parsed the rendered string and fell back to the
parse-failure default.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderedToolResult:
    """LLM-facing string plus the structured wrapper used to derive it."""

    rendered: str
    wrapped: dict[str, Any]

    @property
    def success(self) -> bool:
        return bool(self.wrapped.get("success", True))


def render_tool_result_with_meta(
    td: dict[str, Any] | None,
    results: list[Any],
) -> RenderedToolResult:
    """Return the LLM-facing string AND the wrapper dict it was built from."""
    dumped = [_dump_result(r) for r in results]
    wrapped: dict[str, Any] = {
        "success": all(_effective_success(r, d) for r, d in zip(results, dumped)),
        "results": dumped,
    }

    template = (td or {}).get("_instruction_template")
    if template:
        try:
            from jinja2 import Undefined

            from app.utils.templates.sandbox import make_sandboxed_env

            # Sandboxed — ``template`` is the persisted, user-authored
            # ``_instruction_template``; a plain env would allow SSTI→RCE.
            env = make_sandboxed_env(autoescape=False, undefined=Undefined)
            template_ctx = {**wrapped, "result": wrapped}
            rendered = env.from_string(template).render(**template_ctx).strip()
            if rendered:
                return RenderedToolResult(rendered=rendered, wrapped=wrapped)
        except Exception:
            # Any render failure falls through to the JSON dump. Matches the
            # defensive handling in generate's execute loop — the LLM sees
            # something useful even if the template is malformed.
            pass

    return RenderedToolResult(rendered=json.dumps(wrapped), wrapped=wrapped)


def render_tool_result(
    td: dict[str, Any] | None,
    results: list[Any],
) -> str:
    """Backward-compatible wrapper — returns only the LLM-facing string."""
    return render_tool_result_with_meta(td, results).rendered


def _dump_result(r: Any) -> Any:
    """Coerce an InfraOperationResult (or dict) to a JSON-serializable dict."""
    if hasattr(r, "model_dump"):
        return r.model_dump(mode="json")
    if isinstance(r, dict):
        return r
    return {"value": r}


def _effective_success(r: Any, dumped: Any) -> bool:
    """Outer success AND every nested inner success.

    Bulk handlers (create/update/delete) return ``result={"results": [...]}``
    where each inner entry has its own ``success`` flag. The outer
    InfraOperationResult is ``success=True`` whenever dispatch reached the
    handler without raising — even when every inner item failed validation.
    AND in the inner flags so the LLM-facing wrapper reflects actual outcome.
    """
    if not getattr(r, "success", False):
        return False
    body = dumped.get("result") if isinstance(dumped, dict) else None
    if isinstance(body, dict):
        inner = body.get("results")
        if isinstance(inner, list) and inner:
            return all(
                (item.get("success", True) if isinstance(item, dict) else True)
                for item in inner
            )
    return True
