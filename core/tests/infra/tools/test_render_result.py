"""render_tool_result (Layer 3) — rendered template or JSON fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.infra.tools.render_result import render_tool_result


@dataclass
class _FakeResult:
    success: bool
    result: dict

    def model_dump(self, mode: str = "json") -> dict:
        return {"success": self.success, "result": self.result}


def test_returns_rendered_template_when_present_and_non_empty():
    td = {
        "_instruction_template": (
            "## Personas ({{ results[0].result.count }} results)\n"
            "{% for p in results[0].result.personas %}- {{ p.name }}\n{% endfor %}"
        ),
    }
    results = [
        _FakeResult(success=True, result={
            "count": 2,
            "personas": [{"name": "Aggressive"}, {"name": "Passive"}],
        })
    ]
    out = render_tool_result(td, results)
    assert out.startswith("## Personas (2 results)")
    assert "- Aggressive" in out
    assert "- Passive" in out


def test_falls_back_to_json_when_no_template():
    results = [_FakeResult(success=True, result={"ok": 1})]
    out = render_tool_result({}, results)
    data = json.loads(out)
    assert data["success"] is True
    assert data["results"][0]["result"]["ok"] == 1


def test_falls_back_to_json_when_td_is_none():
    results = [_FakeResult(success=True, result={"ok": 1})]
    out = render_tool_result(None, results)
    data = json.loads(out)
    assert data["success"] is True


def test_falls_back_to_json_when_render_raises():
    td = {"_instruction_template": "{% invalid_syntax %}"}
    results = [_FakeResult(success=False, result={"error": "x"})]
    out = render_tool_result(td, results)
    data = json.loads(out)
    assert data["success"] is False


def test_falls_back_when_template_renders_empty_string():
    td = {"_instruction_template": "{% if results[0].result.personas %}X{% endif %}"}
    results = [_FakeResult(success=True, result={"personas": []})]
    out = render_tool_result(td, results)
    data = json.loads(out)
    # Template rendered empty; fall back to JSON.
    assert data["success"] is True


def test_success_is_and_of_all_results():
    results = [
        _FakeResult(success=True, result={}),
        _FakeResult(success=False, result={}),
    ]
    out = render_tool_result({}, results)
    assert json.loads(out)["success"] is False


def test_template_context_exposes_both_top_level_and_result_alias():
    td = {"_instruction_template": "{{ success }} | {{ result.success }}"}
    results = [_FakeResult(success=True, result={})]
    out = render_tool_result(td, results)
    assert out == "True | True"


def test_nested_inner_failures_flip_top_level_success():
    """Bulk handlers wrap per-item results — top-level must AND them in.

    Dispatch may report success=True (handler ran), yet every inner item
    failed validation. The LLM-facing wrapper should say success=False."""
    results = [
        _FakeResult(
            success=True,
            result={
                "results": [
                    {"success": False, "message": "Item 0: Validation errors"},
                    {"success": False, "message": "Item 1: Validation errors"},
                ],
            },
        ),
    ]
    out = render_tool_result({}, results)
    assert json.loads(out)["success"] is False


def test_nested_all_inner_success_keeps_top_level_true():
    results = [
        _FakeResult(
            success=True,
            result={
                "results": [
                    {"success": True, "tool_id": "a"},
                    {"success": True, "tool_id": "b"},
                ],
            },
        ),
    ]
    out = render_tool_result({}, results)
    assert json.loads(out)["success"] is True


def test_nested_empty_results_list_ignored():
    """Empty inner results shouldn't be treated as failure — search with
    no matches still succeeded at the dispatch layer."""
    results = [_FakeResult(success=True, result={"results": []})]
    out = render_tool_result({}, results)
    assert json.loads(out)["success"] is True
