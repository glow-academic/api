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
from jinja2 import TemplateError
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.events.audit import run_artifact_operation_with_audit
from app.registry.operations import (
    INFRA_OPS,
    get_accepted_fields,
    is_write_operation,
    resolve_callable,
    resolve_item_class,
    resolve_request_class,
)
from app.utils.logging.db_logger import get_logger
from app.utils.templates.sandbox import make_sandboxed_env

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
    run_id: UUID | None = Field(default=None, description="Run context")
    draft_id: UUID | None = Field(default=None, description="Draft context")
    sid: str = Field(default="", description="Socket ID for event emission")
    soft: bool = Field(default=False, description="Create dormant records (active=False) for generation pipeline")
    accept: bool | None = Field(default=None, description="Ack phase: True=promote dormant state, False=reject (no-op or restore for delete)")
    eval: bool = Field(default=False, description="When True, soft_calls_entry rows for this operation are tagged ``eval=true`` so UI surfaces filter them out. Set by trace-driven benchmark runs (see prepare.py).")
    operation_key: UUID | None = Field(default=None, description="Universal key for call dedup — idempotency_key for writes, snapshot_key for reads")
    instruction_template: str | None = Field(default=None, description="Tool response template (Layer 3) for rendered saves")
    call_id: UUID | None = Field(default=None, description="Pre-minted UUID for the calls_entry row — reused by create_call so the same id flows through streaming progress events, audit .started/.completed/.failed, and the DB call record")


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

# Sandboxed — ``template_str`` in render_output_map comes from persisted,
# user-authored tool ``output_map`` templates; a plain env would allow
# SSTI→RCE. autoescape off because this renders into JSON, not HTML.
_jinja_env = make_sandboxed_env(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _to_json_filter(value: Any) -> str:
    """Pydantic-friendly JSON serialization for Jinja's ``| tojson`` filter.

    ``{{ list }}`` in stock Jinja renders Python's ``repr`` (``[UUID('...')]``)
    which downstream ``TypeAdapter`` can't coerce back. Tools that pass
    ``list[UUID]`` / dict / non-scalar values through Jinja must use
    ``{{ field | tojson }}`` so the rendered string is parseable JSON.
    """
    import json
    from datetime import date, datetime
    from uuid import UUID

    def _default(o: Any) -> Any:
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(value, default=_default)


_jinja_env.filters["tojson"] = _to_json_filter


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
# Kwargs-path type coercion (read operations)
# ---------------------------------------------------------------------------


def _filter_ctx_kwargs_to_signature(
    fn: Any,
    ctx_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Drop context kwargs the handler's signature doesn't accept.

    Different infra handlers take different system-provided context
    (some accept ``session_id``, some don't). Passing them indiscriminately
    breaks handlers without ``**_kwargs``. Keep only what the handler
    explicitly declares OR what it absorbs via ``VAR_KEYWORD``.
    """
    import inspect

    try:
        sig = inspect.signature(fn)
    except Exception:
        return ctx_kwargs

    accepts_var_kw = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    if accepts_var_kw:
        return ctx_kwargs

    return {k: v for k, v in ctx_kwargs.items() if k in sig.parameters}


def _coerce_kwargs_to_signature(
    fn: Any,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Coerce rendered-string kwargs back to the target function's declared types.

    render_output_map always produces strings (Jinja's behaviour). For the
    kwargs-path callables (reads like get/search/etc.), the declared types
    matter — ``page: int``, ``active: bool``, ``persona_id: UUID``. Pydantic's
    TypeAdapter handles every standard coercion (int, bool, UUID, list[UUID],
    Optional[T], Literal, etc.) without per-type branching.

    Values that can't be coerced are kept as-is; downstream Pydantic
    validation or the handler itself will surface the actual error. Missing
    type hints also pass through unchanged.
    """
    import inspect
    from typing import get_type_hints

    from pydantic import TypeAdapter

    try:
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
    except Exception:
        return kwargs

    coerced: dict[str, Any] = {}
    for name, value in kwargs.items():
        if value is None or name not in sig.parameters:
            coerced[name] = value
            continue
        expected = hints.get(name)
        if expected is None:
            coerced[name] = value
            continue
        adapter = TypeAdapter(expected)
        # Lists/dicts arrive from Jinja's ``| tojson`` filter as JSON strings —
        # try the JSON parser first for those, then fall back to validate_python
        # for scalar coercion (uuid-string → UUID, "1" → int, etc.).
        if isinstance(value, str) and value[:1] in ("[", "{"):
            try:
                coerced[name] = adapter.validate_json(value)
                continue
            except Exception:
                pass
        try:
            coerced[name] = adapter.validate_python(value)
        except Exception:
            coerced[name] = value
    return coerced


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

            # Determine soft/accept behavior from registry — only write operations
            # can be soft (pending ack). Read operations always execute immediately.
            is_write = is_write_operation(target.operation)
            soft = ctx.soft and is_write
            accept = ctx.accept if is_write else None

            # Check if this operation has a Pydantic item type (structured input)
            # or should pass args as kwargs directly (read operations like get/search)
            accepted = get_accepted_fields(target.artifact, target.operation)

            if accepted is not None:
                # Structured path: filter → sanitize → build item → wrap in request → execute
                filtered = filter_to_accepted(rendered, target.artifact, target.operation)
                from app.infra.tools.sanitize import sanitize_model_kwargs
                filtered = sanitize_model_kwargs(filtered)
                fields_used = list(filtered.keys())
                item = build_item(filtered, target.artifact, target.operation)

                # Construct the request object
                request_cls = resolve_request_class(target.artifact, target.operation)
                if request_cls is not None:
                    # Batch-style (create/update): wrap item in the request's list field
                    list_field = next(
                        k for k, v in request_cls.model_fields.items()
                        if "list" in str(v.annotation)
                    )
                    request_obj = request_cls(**{list_field: [item]})
                else:
                    # Flat-style (draft): the item IS the request
                    request_obj = item

                async def _runner() -> Any:
                    return await fn(
                        ctx.pool,
                        ctx.redis,
                        profile_id=ctx.profile_id,
                        request=request_obj,
                        session_id=ctx.session_id,
                        draft_id=ctx.draft_id,
                        group_id=ctx.group_id,
                        soft=soft,
                        accept=accept,
                        # Canonical ack key: the calls_entry row id of this
                        # tool call. The impl uses it to look up its
                        # ``soft_calls_entry`` ledger row at ack time. Was
                        # ``operation_key`` before — see soft_calls_entry
                        # pattern memory entry.
                        idempotency_key=ctx.call_id,
                    )
            else:
                # Kwargs path: pass rendered args as kwargs directly
                # Sanitize: strip empty strings, coerce string booleans
                from app.infra.tools.sanitize import sanitize_model_kwargs
                kwargs = sanitize_model_kwargs(rendered)

                # Coerce Jinja-stringified values (e.g. "1" → 1, "true" → True,
                # uuid-string → UUID) to the target function's declared types.
                # render_output_map always returns strings; the structured path
                # gets type coercion for free via its Pydantic item, but the
                # kwargs path would otherwise hand strings to handlers whose
                # signatures declare int/bool/UUID.
                kwargs = _coerce_kwargs_to_signature(fn, kwargs)

                fields_used = list(kwargs.keys())

                # Context fields — system-provided, model doesn't know about these
                # draft_id is NOT here — it's a task-level arg the model passes explicitly
                ctx_defaults = {
                    "profile_id": ctx.profile_id,
                    "session_id": ctx.session_id,
                    "group_id": ctx.group_id,
                    "run_id": ctx.run_id,
                    # Parent's live socket id. Nested impls (notably
                    # ``generate_*_impl``) thread ``sid`` into the
                    # ``prepare → execute → media-emit`` chain so emitted
                    # events carry the originating socket. Without this
                    # the nested impl falls back to
                    # ``get_socket_owner(profile_id)``, which picks a
                    # non-deterministic sid from the profile's multi-
                    # socket set — frequently a stale/ghost socket that
                    # the WS fan-out then targets, silently bypassing
                    # the user's actual connections.
                    "sid": ctx.sid,
                    "soft": soft,
                    "accept": accept,
                    # Canonical ack key — see structured-path comment above.
                    "idempotency_key": ctx.call_id,
                    # Override for generate impls. In the tool-driven path
                    # the parent LLM crafted ``instructions`` as a tool
                    # argument — the persisted messages should be
                    # role=assistant, not role=user (the default for
                    # FE-direct flows). Only generate impls declare this
                    # kwarg; the ``_filter_ctx_kwargs_to_signature`` step
                    # below drops it for everyone else.
                    "instructions_role": "assistant",
                }
                # Only pass context kwargs the handler's signature actually
                # declares. Handlers vary in which context they take — some
                # use **_kwargs and absorb anything, others (like
                # search_scenario_impl) TypeError on unknown args. Filtering
                # by signature makes the dispatch safe against that variance
                # without forcing every handler to add **_kwargs defensively.
                ctx_kwargs = _filter_ctx_kwargs_to_signature(
                    fn,
                    {k: v for k, v in ctx_defaults.items() if k not in kwargs},
                )

                async def _runner() -> Any:
                    return await fn(
                        ctx.pool,
                        ctx.redis,
                        **ctx_kwargs,
                        **kwargs,
                    )

            # WS fan-out targets the profile_id room every socket joined
            # at connect time (``ws/connect.py``: ``sio.enter_room(sid,
            # profile_id)``), not a single sid. A user may have multiple
            # tabs/reloads sharing one profile room; emitting to one sid
            # silently misses the others (and any stale/ghost sid would
            # miss everyone). Profile-room broadcast keeps every active
            # connection in sync for free.
            rooms = [str(ctx.profile_id)] if ctx.profile_id else []
            result = await run_artifact_operation_with_audit(
                ctx.pool,
                ctx.redis,
                artifact=target.artifact,
                operation=target.operation,
                profile_id=ctx.profile_id,
                session_id=ctx.session_id,
                group_id=ctx.group_id,
                draft_id=ctx.draft_id,
                run_id=ctx.run_id,
                sid=ctx.sid,
                rooms=rooms,
                runner=_runner,
                # Recorded arguments are the LLM's own kwargs only.
                # Lifecycle flags (soft / accept) live in
                # ``soft_calls_entry`` and are surfaced to the client via
                # ``GroupCall.ledger_status`` — the call JSON itself stays
                # a clean record of what the model asked for.
                arguments=kwargs if accepted is None else filtered,
                instruction_template=ctx.instruction_template,
                operation_key=ctx.operation_key,
                call_id=ctx.call_id,
                # The model is the actor here — this path runs only when
                # an LLM generate loop picked the tool. Every other caller
                # (HTTP routes, socket impls) inherits the "user" default.
                role="assistant",
                # ``.started`` fires unconditionally — the client dedups
                # by ``call_id``, so the audit's started arriving alongside
                # the pipeline's ``generate.call.start`` (same id, both
                # pre-minted to match) collapses to one bubble. The
                # audit's emit additionally carries the ``tool`` envelope
                # which the pipeline event doesn't have, so the bubble
                # gets its registered-tool metadata symmetrically with
                # SSR/user-side audit calls.
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
