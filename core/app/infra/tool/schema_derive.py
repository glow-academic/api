"""Derive the valid tool field surface from a set of permissions.

One pure function, reused across the tool lifecycle:

  * tool editor / `resolve_tool_context` — can filter or tag args_output
    suggestions by whether the selected permissions actually accept them.
  * `create_tool_impl` / `patch_tool_draft_impl` — reject tools whose
    declared args_outputs don't map to any permission's handler surface.
  * seed runner (`_run_tool_module_seeds`) — fail CI on any seed tool
    whose args_outputs can't be satisfied by its permissions.
  * MCP / generate catalog build — could use this to auto-populate
    pass-through outputs in the future (not wired yet).

No DB, no I/O. Introspects `INFRA_OPS` callable signatures and
`INFRA_ITEM_TYPES` Pydantic item classes only.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.registry.operations import (
    INFRA_OPS,
    resolve_callable,
    resolve_item_class,
)

# Context kwargs injected by execute_infra_operation.  Handlers declare them
# explicitly; tools never surface them as user-facing args_outputs.
_CTX_KWARGS: frozenset[str] = frozenset({
    "profile_id",
    "session_id",
    "group_id",
    "run_id",
    "draft_id",
    "sid",
    "soft",
    "accept",
    "idempotency_key",
    "operation_key",
})

# Positional infrastructure — never accepted as args_outputs.
_INFRA_POSITIONAL: frozenset[str] = frozenset({"pool", "redis", "conn"})

# Routing outputs — these are always valid; they pick which
# (artifact, operation) the dispatch targets, not what the handler consumes.
_ROUTING_OUTPUTS: frozenset[str] = frozenset({"artifact", "operation"})


@dataclass(frozen=True)
class PermissionFieldSurface:
    """The field surface a single (artifact, operation) pair accepts."""

    artifact: str
    operation: str
    # Handler has **kwargs — statically it accepts any output name.
    accepts_var_kwargs: bool
    # Structured path (writes) — Pydantic item class field names.
    item_class_fields: frozenset[str]
    # Kwargs path (reads) — handler keyword params (minus infra + ctx).
    handler_keyword_params: frozenset[str]

    @property
    def valid_output_keys(self) -> frozenset[str]:
        """Output names this permission's handler/item consumes."""
        return self.item_class_fields | self.handler_keyword_params


@dataclass(frozen=True)
class PermissionSchema:
    """Aggregated schema for a set of permissions."""

    per_permission: tuple[PermissionFieldSurface, ...]

    @property
    def valid_output_keys(self) -> frozenset[str]:
        """Union of acceptable output names across all permissions.

        Routing outputs (``artifact``, ``operation``) are always included.
        """
        keys: set[str] = set(_ROUTING_OUTPUTS)
        for p in self.per_permission:
            keys |= p.valid_output_keys
        return frozenset(keys)

    @property
    def has_var_kwargs_handler(self) -> bool:
        """Any permission's handler accepts ``**kwargs``?

        When true, static validation can't reject output names — the
        handler silently absorbs anything. Callers deciding between
        strict/permissive modes typically key off this flag.
        """
        return any(p.accepts_var_kwargs for p in self.per_permission)

    def field_coverage(self) -> dict[str, frozenset[tuple[str, str]]]:
        """Return a map ``output_key → set of (artifact, operation) that accept it``."""
        out: dict[str, set[tuple[str, str]]] = {}
        for p in self.per_permission:
            for key in p.valid_output_keys:
                out.setdefault(key, set()).add((p.artifact, p.operation))
        return {k: frozenset(v) for k, v in out.items()}

    def validate_output_keys(
        self,
        output_names: Iterable[str],
        *,
        strict: bool = False,
    ) -> list[str]:
        """Return the list of output names that no permission can accept.

        By default, handlers with ``**kwargs`` short-circuit validation
        (any name is plausibly valid). Pass ``strict=True`` to validate
        against the declared signature fields regardless — useful for seed
        CI where ``**kwargs`` is treated as tech debt rather than a pass.
        """
        if not strict and self.has_var_kwargs_handler:
            return []
        valid = self.valid_output_keys
        return [name for name in output_names if name not in valid]


def _keyword_params(fn: Any) -> tuple[frozenset[str], bool]:
    """Extract (keyword_param_names, accepts_var_kwargs) from a callable."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return frozenset(), False

    accepts_var_kw = False
    keyword_names: set[str] = set()
    for name, param in sig.parameters.items():
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_var_kw = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        if name in _INFRA_POSITIONAL or name in _CTX_KWARGS:
            continue
        keyword_names.add(name)
    return frozenset(keyword_names), accepts_var_kw


def derive_schema_for_permissions(
    permissions: Iterable[tuple[str, str]],
) -> PermissionSchema:
    """Compute the valid field surface for a set of ``(artifact, operation)`` pairs.

    Missing or unimportable callables/item classes yield an empty surface
    for that permission rather than raising — lets the validator surface
    "dead permissions" as a finding instead of crashing the audit.
    """
    surfaces: list[PermissionFieldSurface] = []
    for artifact, operation in permissions:
        try:
            fn = resolve_callable(artifact, operation, INFRA_OPS)
        except Exception:
            fn = None
        keyword_params, accepts_var_kw = _keyword_params(fn) if fn else (frozenset(), False)

        try:
            item_cls = resolve_item_class(artifact, operation)
        except Exception:
            item_cls = None
        item_fields = (
            frozenset(item_cls.model_fields.keys()) if item_cls is not None else frozenset()
        )

        surfaces.append(
            PermissionFieldSurface(
                artifact=artifact,
                operation=operation,
                accepts_var_kwargs=accepts_var_kw,
                item_class_fields=item_fields,
                handler_keyword_params=keyword_params,
            )
        )
    return PermissionSchema(per_permission=tuple(surfaces))
