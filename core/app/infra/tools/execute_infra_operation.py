"""Execute infra operations from arbitrary inputs + Jinja output mappings.

Black-box function that bridges tool artifacts to API-level infra functions:

  1. Render Jinja templates:  inputs + output_map  → rendered values (once)
  2. For each target (artifact, operation):
     a. Filter rendered values to accepted fields
     b. Construct Pydantic item
     c. Execute via run_artifact_operation_with_audit (canonical audit path)
  3. Return results

All three call paths (HTTP, WebSocket, Generation) go through the same
audit mechanism: run_artifact_operation_with_audit.

InfraContext bundles all system-provided infrastructure (pool, redis,
profile, session, etc.) — these are pass-throughs that the tool interface
never sees or controls.

Usage:
    ctx = InfraContext(pool=pool, redis=redis, profile_id=profile_id)

    spec = InfraOperationSpec(
        inputs={"topic": "Sales Training", "level": "beginner"},
        output_map={"name": "{{ topic }}", "description": "{{ topic }} at {{ level }} level"},
        targets=[
            InfraTarget(artifact="agent", operation="create"),
            InfraTarget(artifact="persona", operation="create"),
        ],
    )

    results = await execute_infra_operation(ctx, spec)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from jinja2 import Environment, TemplateError
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.events.audit import run_artifact_operation_with_audit
from app.registry.operations import (
    INFRA_OPS,
    get_accepted_fields,
    resolve_callable,
    resolve_item_class,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Infrastructure context — system-provided pass-throughs
# ---------------------------------------------------------------------------


class InfraContext(BaseModel):
    """System-provided infrastructure for infra function execution.

    These are pass-throughs that the tool interface never sees or controls.
    The orchestrator (generation pipeline, WebSocket handler, etc.) creates
    this once and passes it through.
    """

    model_config = {"arbitrary_types_allowed": True, "frozen": True}

    pool: Any = Field(description="asyncpg connection pool")
    redis: Any = Field(description="Redis client for caching")
    profile_id: UUID = Field(description="Authenticated user's profile ID")
    session_id: UUID | None = Field(default=None, description="Session context")
    group_id: UUID | None = Field(default=None, description="Group context")
    draft_id: UUID | None = Field(default=None, description="Draft context")
    sid: str = Field(default="", description="Socket ID for event emission")
    soft: bool = Field(default=False, description="Create dormant records (active=False) for generation pipeline")


# ---------------------------------------------------------------------------
# Operation spec — the tool interface
# ---------------------------------------------------------------------------


class InfraTarget(BaseModel):
    """A single (artifact, operation) target that receives rendered outputs."""

    model_config = {"frozen": True}

    artifact: str = Field(description="Artifact type, e.g. 'agent', 'persona'")
    operation: str = Field(description="Operation type, e.g. 'create', 'update'")


class InfraOperationSpec(BaseModel):
    """Complete specification for executing one or more infra operations.

    - inputs: Arbitrary key-value pairs from the caller (e.g., LLM tool args).
    - output_map: Jinja templates that transform inputs into standardized
      API field names. Rendered once, shared across all targets.
    - targets: List of (artifact, operation) pairs. Each target receives
      the subset of rendered outputs that it accepts.
    """

    model_config = {"frozen": True}

    inputs: dict[str, Any] = Field(
        description="Arbitrary input values, e.g. from LLM tool call arguments"
    )
    output_map: dict[str, str] = Field(
        description="Mapping of API field name → Jinja template over inputs"
    )
    targets: list[InfraTarget] = Field(
        description="Target (artifact, operation) pairs to execute"
    )


class InfraOperationResult(BaseModel):
    """Result from a single target execution."""

    artifact: str
    operation: str
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    error_stage: str | None = None
    fields_used: list[str] = Field(
        default_factory=list,
        description="Which rendered fields this target actually consumed",
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InfraOperationError(Exception):
    """Raised when an infra operation fails validation or execution."""

    def __init__(self, message: str, *, stage: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.stage = stage
        self.details = details or {}


# ---------------------------------------------------------------------------
# Jinja rendering
# ---------------------------------------------------------------------------

_jinja_env = Environment(
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_output_map(
    inputs: dict[str, Any],
    output_map: dict[str, str],
) -> dict[str, str]:
    """Render Jinja templates in output_map using inputs as context.

    Returns:
        field_name → rendered string value.

    Raises:
        InfraOperationError: If any template fails to render.
    """
    rendered: dict[str, str] = {}
    errors: list[str] = []

    for field_name, template_str in output_map.items():
        try:
            template = _jinja_env.from_string(template_str)
            rendered[field_name] = template.render(**inputs)
        except TemplateError as e:
            errors.append(f"{field_name}: {e}")

    if errors:
        raise InfraOperationError(
            f"Template rendering failed: {'; '.join(errors)}",
            stage="render",
            details={"errors": errors},
        )

    return rendered


# ---------------------------------------------------------------------------
# Per-target: filter, build
# ---------------------------------------------------------------------------


def filter_to_accepted(
    rendered: dict[str, Any],
    artifact: str,
    operation: str,
) -> dict[str, Any]:
    """Filter rendered values to only fields the target accepts.

    Returns the filtered dict. Silently drops fields the target doesn't
    recognize — this is expected since the same output_map serves
    multiple targets.

    Raises:
        InfraOperationError: If no item type is registered for this target.
    """
    accepted = get_accepted_fields(artifact, operation)
    if accepted is None:
        raise InfraOperationError(
            f"No item type registered for ({artifact}, {operation})",
            stage="validate",
            details={"artifact": artifact, "operation": operation},
        )

    return {k: v for k, v in rendered.items() if k in accepted}


def build_item(
    filtered: dict[str, Any],
    artifact: str,
    operation: str,
) -> Any:
    """Construct a Pydantic item from filtered rendered values.

    Skips empty strings — lets the Pydantic model apply its own defaults.

    Raises:
        InfraOperationError: On Pydantic validation failure.
    """
    cls = resolve_item_class(artifact, operation)
    if cls is None:
        raise InfraOperationError(
            f"No item class for ({artifact}, {operation})",
            stage="build",
        )

    # Filter out empty strings — treat as "not provided"
    non_empty = {k: v for k, v in filtered.items() if v != ""}

    try:
        return cls(**non_empty)
    except Exception as e:
        raise InfraOperationError(
            f"Failed to construct {cls.__name__}: {e}",
            stage="build",
            details={"class": cls.__name__, "values": non_empty},
        ) from e


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def execute_infra_operation(
    ctx: InfraContext,
    spec: InfraOperationSpec,
) -> list[InfraOperationResult]:
    """Execute infra operations from arbitrary inputs + Jinja output mappings.

    This is the black-box bridge between tool artifacts and API-level functions.
    Each target is executed through run_artifact_operation_with_audit — the
    same audit path used by HTTP routes and WebSocket handlers.

    Args:
        ctx: System-provided infrastructure (pool, redis, profile, session).
            Pass-throughs — the tool interface never sees them.
        spec: The tool interface — inputs, output mappings, and targets.

    Returns:
        One InfraOperationResult per target, in order.
    """
    # 1. Render Jinja templates (once, shared across all targets)
    rendered = render_output_map(spec.inputs, spec.output_map)
    logger.info(f"Rendered {len(rendered)} fields: {list(rendered.keys())}")

    # 2. Execute each target
    results: list[InfraOperationResult] = []

    for target in spec.targets:
        try:
            # Resolve infra function
            fn = resolve_callable(target.artifact, target.operation, INFRA_OPS)
            if fn is None:
                results.append(InfraOperationResult(
                    artifact=target.artifact,
                    operation=target.operation,
                    success=False,
                    error=f"No infra function for ({target.artifact}, {target.operation})",
                    error_stage="resolve",
                ))
                continue

            # Check if this operation has a Pydantic item type (write operations)
            # or should pass args as kwargs directly (read operations like get/search)
            accepted = get_accepted_fields(target.artifact, target.operation)

            if accepted is not None:
                # Write path: filter → build Pydantic item → execute with items=[item]
                filtered = filter_to_accepted(rendered, target.artifact, target.operation)
                fields_used = list(filtered.keys())
                item = build_item(filtered, target.artifact, target.operation)

                async def _runner() -> Any:
                    return await fn(
                        ctx.pool,
                        ctx.redis,
                        profile_id=ctx.profile_id,
                        items=[item],
                        session_id=ctx.session_id,
                        draft_id=ctx.draft_id,
                        group_id=ctx.group_id,
                        soft=ctx.soft,
                    )
            else:
                # Read path: pass rendered args as kwargs directly
                # Strip empty strings — the function uses None defaults
                kwargs = {k: v for k, v in rendered.items() if v != ""}
                fields_used = list(kwargs.keys())

                async def _runner() -> Any:
                    return await fn(
                        ctx.pool,
                        ctx.redis,
                        profile_id=ctx.profile_id,
                        session_id=ctx.session_id,
                        draft_id=ctx.draft_id,
                        group_id=ctx.group_id,
                        **kwargs,
                    )

            result = await run_artifact_operation_with_audit(
                ctx.pool,
                ctx.redis,
                artifact=target.artifact,
                operation=target.operation,
                profile_id=ctx.profile_id,
                session_id=ctx.session_id,
                group_id=ctx.group_id,
                draft_id=ctx.draft_id,
                sid=ctx.sid,
                rooms=[ctx.sid] if ctx.sid else [],
                runner=_runner,
                arguments=kwargs if accepted is None else filtered,
            )

            results.append(InfraOperationResult(
                artifact=target.artifact,
                operation=target.operation,
                success=True,
                result=result if isinstance(result, dict) else
                    result.model_dump(mode="json") if hasattr(result, "model_dump") else
                    {"result": str(result)},
                fields_used=fields_used,
            ))

        except InfraOperationError as e:
            results.append(InfraOperationResult(
                artifact=target.artifact,
                operation=target.operation,
                success=False,
                error=str(e),
                error_stage=e.stage,
            ))

        except Exception as e:
            results.append(InfraOperationResult(
                artifact=target.artifact,
                operation=target.operation,
                success=False,
                error=str(e),
                error_stage="execute",
            ))

    return results
