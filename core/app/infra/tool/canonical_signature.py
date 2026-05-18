"""Compute the canonical tool shape for a (verb, permissions) pair.

Sketch — not yet wired into seed generation. Treats handler signatures +
Pydantic item classes as the source of truth and derives what a *well-formed*
tool seed would look like (routing + args_outputs + required args), so
seeds can be regenerated in lockstep with the infra layer instead of
hand-maintained.

Sits one layer above ``schema_derive`` — schema_derive answers "what field
surface do these permissions accept?", this module answers "what tool seed
should we emit for them?".

Three conceptual outputs for each tool:

  * **routing** — how ``artifact`` and ``operation`` get into the
    ``args_outputs`` list. Collapses to a hardcoded value when all
    permissions agree; pass-through otherwise (matches the runtime
    collapse in ``resolve_tool_spec``).
  * **args** / **required_args** — the LLM-visible parameters. Required
    is the *intersection* across permissions (if any permission would
    reject a missing field, the LLM must supply it).
  * **payload_outputs** — non-routing field names headed into the
    handler. One per arg, with the conventional pass-through template.

No DB, no I/O. Reuses ``derive_schema_for_permissions``.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.infra.tool.schema_derive import (
    _CTX_KWARGS,
    _INFRA_POSITIONAL,
    _ROUTING_OUTPUTS,
    derive_schema_for_permissions,
)
from app.registry.operations import INFRA_OPS, resolve_callable, resolve_item_class

RoutingMode = str  # "hardcoded:<value>" or "passthrough"


@dataclass(frozen=True)
class CanonicalToolShape:
    """The seed-shape we *would* emit for a given tool.

    Compare against the existing row in ``database/seeds/tools.py`` to
    surface drift. Callers that regenerate seeds translate the name-level
    fields below into args_output slugs (``"name"`` → ``"name_passthrough"``
    etc.) via the registry in ``database/seeds/resources/args_outputs.py``.
    """

    verb: str
    permissions: tuple[tuple[str, str], ...]
    artifact_routing: RoutingMode
    operation_routing: RoutingMode
    args: tuple[str, ...]
    required_args: tuple[str, ...]
    payload_outputs: tuple[str, ...]
    # Names declared by at least one permission that aren't available on
    # every permission — surfaced so the caller can decide whether to
    # require them, expose them as optional, or split the tool.
    partial_coverage: tuple[str, ...] = field(default_factory=tuple)


def canonical_tool_signature(
    verb: str,
    permissions: Iterable[tuple[str, str]],
) -> CanonicalToolShape:
    """Return the canonical tool shape for ``(verb, permissions)``.

    ``verb`` is informational — routing is derived from the actual
    permission set, not the verb name. It's carried through so callers
    can group shapes by verb when regenerating seeds.
    """
    perms = tuple(permissions)
    if not perms:
        raise ValueError("canonical_tool_signature requires at least one permission")

    schema = derive_schema_for_permissions(perms)

    # --- Routing: collapse when all permissions agree on a dimension ---
    distinct_artifacts = {a for (a, _o) in perms}
    distinct_operations = {o for (_a, o) in perms}

    artifact_routing = (
        f"hardcoded:{next(iter(distinct_artifacts))}"
        if len(distinct_artifacts) == 1
        else "passthrough"
    )
    operation_routing = (
        f"hardcoded:{next(iter(distinct_operations))}"
        if len(distinct_operations) == 1
        else "passthrough"
    )

    # --- Payload surface: union minus routing ---
    all_valid = schema.valid_output_keys - _ROUTING_OUTPUTS

    # Coverage — keep fields every permission accepts. A field that only one
    # of N permissions takes can't be safely required (the handler for the
    # other permissions would reject it), but we still want to know it
    # exists so the caller can decide whether to split the tool.
    coverage = schema.field_coverage()
    full_coverage = {
        name for name, accepts in coverage.items()
        if len(accepts) == len(perms) and name not in _ROUTING_OUTPUTS
    }
    partial_coverage = sorted(
        (all_valid - full_coverage) - _ROUTING_OUTPUTS
    )

    # --- Required: intersection across permissions ---
    required_per_permission: list[frozenset[str]] = []
    for artifact, operation in perms:
        required_per_permission.append(_required_fields(artifact, operation))

    required_args = (
        frozenset.intersection(*required_per_permission)
        if required_per_permission
        else frozenset()
    ) - _ROUTING_OUTPUTS

    # --- Assemble ---
    # Prefer field names available on every permission. For varkw handlers
    # schema.valid_output_keys is still computed from item_class_fields, so
    # it's not empty just because the handler accepts **kwargs.
    args = tuple(sorted(full_coverage))
    payload_outputs = args  # seed payload outputs mirror the args, 1:1

    return CanonicalToolShape(
        verb=verb,
        permissions=perms,
        artifact_routing=artifact_routing,
        operation_routing=operation_routing,
        args=args,
        required_args=tuple(sorted(required_args & full_coverage)),
        payload_outputs=payload_outputs,
        partial_coverage=tuple(partial_coverage),
    )


@dataclass(frozen=True)
class ToolSchemaFindings:
    """What a tool's declared outputs look like against its canonical shape.

    Three independent signals — all can be non-empty simultaneously:

    * ``unknown_outputs`` — declared names no permission's handler accepts.
      The LLM would send these to the tool and they'd be dropped on the
      floor. Was the first check the validator did; still useful.
    * ``missing_required`` — required kwargs (present in every permission's
      handler signature) that no declared output produces. The handler will
      reject the call at runtime with a missing-kwarg error. This catches
      the "Create Content has no ``color``/``icon``" bug class.
    * ``partial_coverage_declared`` — declared outputs that only some (not
      all) permissions accept. Not wrong per se — cross-cutting tools
      commonly expose optional fields only relevant to a subset — but
      worth surfacing so the caller can decide whether to split the tool.
    """

    unknown_outputs: tuple[str, ...]
    missing_required: tuple[str, ...]
    partial_coverage_declared: tuple[str, ...]

    def is_clean(self) -> bool:
        return not (self.unknown_outputs or self.missing_required)

    def to_warnings(self) -> list[str]:
        """Flatten to a list of human-readable warning strings."""
        out: list[str] = []
        if self.unknown_outputs:
            out.append(f"unknown outputs: {list(self.unknown_outputs)}")
        if self.missing_required:
            out.append(f"missing required: {list(self.missing_required)}")
        if self.partial_coverage_declared:
            out.append(f"partial-coverage outputs: {list(self.partial_coverage_declared)}")
        return out


def validate_tool_outputs(
    permissions: Iterable[tuple[str, str]],
    declared_output_names: Iterable[str],
    *,
    strict: bool = False,
) -> ToolSchemaFindings:
    """Validate a tool's declared args_output names against its permissions.

    Composes:

    * ``derive_schema_for_permissions(...).validate_output_keys(...)`` —
      catches **unknown** names. Respects ``**kwargs`` handlers by default
      (no complaints); pass ``strict=True`` to validate even against those.
    * ``canonical_tool_signature(...)`` — catches **missing required** names
      and flags **partial-coverage** declared names.

    No DB, no I/O. Callers feed it names from the tool's args_outputs rows.
    """
    declared = tuple(declared_output_names)
    perms = tuple(permissions)
    if not perms:
        return ToolSchemaFindings((), (), ())

    schema = derive_schema_for_permissions(perms)
    unknown = tuple(schema.validate_output_keys(declared, strict=strict))

    shape = canonical_tool_signature("", perms)
    declared_set = set(declared)
    missing_required = tuple(sorted(set(shape.required_args) - declared_set))
    partial = tuple(sorted(set(shape.partial_coverage) & declared_set))

    return ToolSchemaFindings(
        unknown_outputs=unknown,
        missing_required=missing_required,
        partial_coverage_declared=partial,
    )


def _required_fields(artifact: str, operation: str) -> frozenset[str]:
    """Required field names for one permission (handler ∪ item class).

    Item class: Pydantic ``model_fields[name].is_required()``.
    Handler: keyword params with no default (and kind POSITIONAL_OR_KEYWORD
    or KEYWORD_ONLY), minus infra/ctx kwargs.
    """
    required: set[str] = set()

    try:
        item_cls = resolve_item_class(artifact, operation)
    except Exception:
        item_cls = None
    if item_cls is not None:
        for name, info in item_cls.model_fields.items():
            if info.is_required():
                required.add(name)

    try:
        fn = resolve_callable(artifact, operation, INFRA_OPS)
    except Exception:
        fn = None
    if fn is not None:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            sig = None
        if sig is not None:
            for name, param in sig.parameters.items():
                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue
                if name in _INFRA_POSITIONAL or name in _CTX_KWARGS:
                    continue
                if param.default is inspect.Parameter.empty:
                    required.add(name)

    return frozenset(required)
