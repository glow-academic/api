"""SSTI→RCE regression — every user-authored Jinja render must be sandboxed.

A plain ``jinja2.Environment`` lets a template body reach Python object
internals (``__class__``, ``__globals__``, ``__init__`` …) and from there
``os.popen`` — i.e. arbitrary command execution on the API container. The
fix routes every user-template render site through
``app.utils.templates.sandbox.make_sandboxed_env`` (a ``SandboxedEnvironment``).

These tests assert two properties for the shared helper and for each render
site that is reachable without a database:

  1. The canonical SSTI payloads raise ``jinja2.exceptions.SecurityError``
     (or are otherwise neutralized) instead of executing.
  2. Legitimate tool templates — variable substitution plus the normal
     filters/loops/conditionals real tool seeds use — still render correctly.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from jinja2.exceptions import SecurityError, TemplateError

from app.infra.generation.render_developer_instructions import (
    render_developer_instructions,
)
from app.infra.tools.execute_infra_operation import (
    InfraOperationError,
    render_output_map,
)
from app.infra.tools.render_result import render_tool_result
from app.infra.tools.render_tool_template import validate_jinja_template
from app.infra.tools.resolve_tool_spec import _jinja_env as resolve_env
from app.utils.settings.theme import ThemeTokens
from app.utils.templates.jinja_renderer import render_template
from app.utils.templates.sandbox import make_sandboxed_env

# Canonical SSTI gadget chains. Each, under a plain Environment, walks object
# internals to reach os and execute a command; under the sandbox each raises
# SecurityError at the first unsafe attribute access.
SSTI_PAYLOADS = [
    "{{ cycler.__init__.__globals__.os.popen('id').read() }}",
    "{{ ''.__class__.__mro__[1].__subclasses__() }}",
    "{{ self.__init__.__globals__ }}",
    "{{ ().__class__.__bases__[0].__subclasses__() }}",
]


# --------------------------------------------------------------------------
# The shared helper itself.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("payload", SSTI_PAYLOADS)
def test_sandbox_blocks_ssti(payload: str) -> None:
    env = make_sandboxed_env(autoescape=False)
    with pytest.raises(SecurityError):
        env.from_string(payload).render({})


def test_sandbox_security_error_is_template_error() -> None:
    # Render sites that catch TemplateError therefore neutralize SSTI cleanly.
    assert issubclass(SecurityError, TemplateError)


def test_sandbox_legit_variable_and_filters_render() -> None:
    env = make_sandboxed_env(autoescape=False)
    out = env.from_string(
        "Hi {{ name | upper }} — {{ items | join(', ') }} "
        "({{ count | default(0) }})"
    ).render(name="bob", items=["a", "b"], count=3)
    assert out == "Hi BOB — a, b (3)"


def test_sandbox_legit_loops_conditionals_and_dict_methods() -> None:
    env = make_sandboxed_env(autoescape=False)
    tmpl = (
        "{% if ok %}{% for k, v in data.items() %}"
        "{{ k | replace('_', ' ') | title }}={{ v }};{% endfor %}{% endif %}"
    )
    out = env.from_string(tmpl).render(ok=True, data={"first_name": "x"})
    assert out == "First Name=x;"


def test_sandbox_tojson_filter_when_requested() -> None:
    from uuid import UUID

    env = make_sandboxed_env(autoescape=False, json_safe_tojson=True)
    out = env.from_string("{{ v | tojson }}").render(
        v=[UUID("00000000-0000-0000-0000-000000000001")]
    )
    assert out == '["00000000-0000-0000-0000-000000000001"]'


# --------------------------------------------------------------------------
# render_tool_result — persisted ``_instruction_template``.
# --------------------------------------------------------------------------


@dataclass
class _FakeResult:
    success: bool
    result: dict

    def model_dump(self, mode: str = "json") -> dict:
        return {"success": self.success, "result": self.result}


@pytest.mark.parametrize("payload", SSTI_PAYLOADS)
def test_render_tool_result_neutralizes_ssti(payload: str) -> None:
    td = {"_instruction_template": payload}
    results = [_FakeResult(success=True, result={})]
    # SecurityError is swallowed → falls back to the JSON dump, never executes.
    out = render_tool_result(td, results)
    assert "uid=" not in out and "root" not in out
    assert out.startswith("{")  # JSON fallback


def test_render_tool_result_legit_template_still_renders() -> None:
    td = {
        "_instruction_template": (
            "Created `{{ results[0].result.id }}` "
            "for {{ results[0].result.name | upper }}"
        )
    }
    results = [_FakeResult(success=True, result={"id": "p1", "name": "ash"})]
    assert render_tool_result(td, results) == "Created `p1` for ASH"


# --------------------------------------------------------------------------
# render_developer_instructions.
# --------------------------------------------------------------------------


def test_render_developer_instructions_neutralizes_ssti() -> None:
    out = render_developer_instructions(SSTI_PAYLOADS, {})
    # Every payload SecurityErrors and is filtered out.
    assert out == []


def test_render_developer_instructions_legit_still_renders() -> None:
    out = render_developer_instructions(
        ["Names: {{ names | join(', ') }}"], {"names": ["Alice", "Bob"]}
    )
    assert out == ["Names: Alice, Bob"]


# --------------------------------------------------------------------------
# render_template (artifact/setting HTML).
# --------------------------------------------------------------------------


def _theme() -> ThemeTokens:
    # All 40 fields default to "" — fine for these render assertions.
    return ThemeTokens()


@pytest.mark.parametrize("payload", SSTI_PAYLOADS)
def test_render_template_blocks_ssti(payload: str) -> None:
    with pytest.raises(SecurityError):
        render_template(f"<p>{payload}</p>", {}, _theme())


def test_render_template_legit_still_renders() -> None:
    out = render_template("<p>Hello {{ name }}</p>", {"name": "Ash"}, _theme())
    assert "<p>Hello Ash</p>" in out


# --------------------------------------------------------------------------
# render_output_map (persisted output_map) + resolve_tool_spec routing env.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("payload", SSTI_PAYLOADS)
def test_render_output_map_blocks_ssti(payload: str) -> None:
    with pytest.raises(InfraOperationError):
        render_output_map({}, {"field": payload})


def test_render_output_map_legit_still_renders() -> None:
    out = render_output_map({"a": "x", "b": "y"}, {"f": "{{ a }}-{{ b }}"})
    assert out == {"f": "x-y"}


@pytest.mark.parametrize("payload", SSTI_PAYLOADS)
def test_resolve_tool_spec_env_blocks_ssti(payload: str) -> None:
    with pytest.raises(SecurityError):
        resolve_env.from_string(payload).render()


def test_resolve_tool_spec_env_legit_renders() -> None:
    assert resolve_env.from_string("{{ artifact }}").render(artifact="persona") == "persona"


# --------------------------------------------------------------------------
# validate_jinja_template — still accepts legit, rejects bad syntax.
# --------------------------------------------------------------------------


def test_validate_jinja_template_accepts_legit() -> None:
    assert validate_jinja_template("Hello {{ name | upper }}") == (True, None)


def test_validate_jinja_template_rejects_bad_syntax() -> None:
    ok, err = validate_jinja_template("Hello {{ name ")
    assert ok is False and err is not None
