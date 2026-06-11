"""Shared hardened Jinja sandbox for ALL user-authored template rendering.

Every Jinja template whose body originates from a profile/request — tool
output templates, persisted tool ``args_outputs`` templates, tool
``_instruction_template`` bodies, developer-instruction templates, and
artifact/setting HTML templates — MUST be rendered through one of the
``SandboxedEnvironment`` instances produced here.

A plain ``jinja2.Environment`` exposes Python object internals
(``__class__``, ``__globals__``, ``__init__`` …) to the template, so an
attacker who controls the template body can reach ``os.popen`` and execute
arbitrary commands on the API container (SSTI → RCE). ``SandboxedEnvironment``
blocks access to those unsafe attributes and raises
``jinja2.exceptions.SecurityError`` instead.

Use:
    from app.utils.templates.sandbox import make_sandboxed_env

    env = make_sandboxed_env(autoescape=True)
    rendered = env.from_string(user_template).render(**ctx)

The legitimate template features that real tool templates rely on —
variable substitution, the standard filters (``upper``, ``join``, ``default``,
``tojson`` …), loops and conditionals — all keep working under the sandbox.
Only attribute/method access that Jinja deems unsafe is rejected.
"""

from __future__ import annotations

from typing import Any

from jinja2.sandbox import SandboxedEnvironment


def _tojson_filter(value: Any) -> str:
    """Pydantic-friendly JSON serialization for the ``| tojson`` filter.

    ``{{ list }}`` in stock Jinja renders Python's ``repr`` (``[UUID('...')]``)
    which downstream ``TypeAdapter`` can't coerce back. Tools that pass
    ``list[UUID]`` / dict / non-scalar values through Jinja use
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


def make_sandboxed_env(
    *,
    autoescape: bool = True,
    trim_blocks: bool = False,
    lstrip_blocks: bool = False,
    keep_trailing_newline: bool = True,
    json_safe_tojson: bool = False,
    **kwargs: Any,
) -> SandboxedEnvironment:
    """Build a hardened ``SandboxedEnvironment`` for user-authored templates.

    Args:
        autoescape: HTML-escape rendered output. Default True (safe for HTML
            sinks); pass False for plain-text sinks (e.g. tool arg rendering
            into JSON, where ``&amp;`` would corrupt the payload).
        trim_blocks / lstrip_blocks / keep_trailing_newline: standard Jinja
            whitespace controls, passed through unchanged.
        json_safe_tojson: install the UUID/datetime-aware ``tojson`` filter
            (needed by the infra-operation arg renderer).
        **kwargs: any additional ``Environment`` kwargs.

    Returns:
        A ``SandboxedEnvironment`` that rejects unsafe attribute access with
        ``jinja2.exceptions.SecurityError`` while leaving normal template
        features (variables, filters, loops, conditionals) intact.
    """
    env = SandboxedEnvironment(
        autoescape=autoescape,
        trim_blocks=trim_blocks,
        lstrip_blocks=lstrip_blocks,
        keep_trailing_newline=keep_trailing_newline,
        **kwargs,
    )
    if json_safe_tojson:
        env.filters["tojson"] = _tojson_filter
    return env


__all__: list[str] = ["make_sandboxed_env"]
