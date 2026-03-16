"""Introspect a Python function to extract signature and return type schema."""

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel

from app.infra.docs.types import OperationInfo, ParamInfo

# Parameters that are infra-level, not caller-facing.
_SKIP_PARAMS = {"conn", "return"}


def get_operation_info(func: Callable[..., Any], description: str) -> OperationInfo:
    """Extract function signature and return type into OperationInfo."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)

    params: list[ParamInfo] = []
    for name, param in sig.parameters.items():
        if name in _SKIP_PARAMS:
            continue

        type_hint = hints.get(name)
        type_str = _type_to_str(type_hint) if type_hint else "Any"
        has_default = param.default is not inspect.Parameter.empty

        params.append(
            ParamInfo(
                name=name,
                type=type_str,
                required=not has_default,
                default=_serialize_default(param.default) if has_default else None,
            )
        )

    # Extract return type JSON schema from Pydantic model if available.
    returns: dict[str, Any] | None = None
    return_hint = hints.get("return")
    if return_hint is not None:
        returns = _return_schema(return_hint)

    return OperationInfo(
        name=func.__name__,
        description=description,
        params=params,
        returns=returns,
    )


def _type_to_str(t: Any) -> str:
    """Convert a type hint to a readable string."""
    origin = getattr(t, "__origin__", None)

    # Handle Optional / Union (e.g. list[UUID] | None)
    if origin is not None:
        args = getattr(t, "__args__", ())
        arg_strs = [_type_to_str(a) for a in args if a is not type(None)]
        base = getattr(origin, "__name__", str(origin))
        if len(arg_strs) == 1 and type(None) in args:
            return f"{arg_strs[0]} | None"
        if arg_strs:
            return f"{base}[{', '.join(arg_strs)}]"
        return base

    return getattr(t, "__name__", str(t))


def _return_schema(hint: Any) -> dict[str, Any]:
    """Extract JSON schema from return type hint."""
    # Direct Pydantic model
    if isinstance(hint, type) and issubclass(hint, BaseModel):
        return {"type": hint.__name__, "schema": hint.model_json_schema()}

    # Optional[Model] — unwrap and check inner
    args = getattr(hint, "__args__", ())
    for arg in args:
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            return {"type": f"{arg.__name__} | None", "schema": arg.model_json_schema()}

    # list[Model]
    origin = getattr(hint, "__origin__", None)
    if origin is list and args:
        inner = args[0]
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return {
                "type": f"list[{inner.__name__}]",
                "schema": inner.model_json_schema(),
            }

    return {"type": _type_to_str(hint)}


def _serialize_default(value: Any) -> Any:
    """Convert Python defaults to JSON-serializable docs values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_default(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_default(item) for key, item in value.items()}
    return repr(value)
