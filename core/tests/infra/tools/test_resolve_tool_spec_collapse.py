"""resolve_tool_spec — collapses single-value routing dimensions.

When all of a tool's permissions agree on one value for `artifact` or
`operation`, the LLM shouldn't have to supply that dimension. Previously
this raised "routing could not be resolved"; now it resolves to the
implied value.
"""

from __future__ import annotations

import pytest

from app.infra.tools.resolve_tool_spec import resolve_tool_spec


def _td(perms, *, args_outputs=None):
    """Minimal tool_def shaped like enrich_tools_with_* output."""
    args_outputs = args_outputs or [
        {"name": "artifact", "template": "{{ artifact }}"},
        {"name": "operation", "template": "{{ operation }}"},
        {"name": "name", "template": "{{ name }}"},
    ]
    return {
        "name": "test-tool",
        "_permissions": perms,
        "_args_outputs": args_outputs,
    }


def test_operation_collapses_when_all_permissions_agree():
    """search_content: 4 artifacts × 1 operation (search). LLM supplies
    only artifact; resolver fills in operation from the single allowed value."""
    td = _td([
        {"artifact": "persona", "operation": "search"},
        {"artifact": "scenario", "operation": "search"},
        {"artifact": "cohort", "operation": "search"},
        {"artifact": "simulation", "operation": "search"},
    ])
    spec = resolve_tool_spec(td, {"artifact": "persona", "name": "alice"})
    assert spec.targets[0].artifact == "persona"
    assert spec.targets[0].operation == "search"


def test_artifact_collapses_when_all_permissions_agree():
    """Symmetric: 1 artifact × N operations. LLM supplies only operation."""
    td = _td([
        {"artifact": "persona", "operation": "get"},
        {"artifact": "persona", "operation": "update"},
        {"artifact": "persona", "operation": "delete"},
    ])
    spec = resolve_tool_spec(td, {"operation": "get"})
    assert spec.targets[0].artifact == "persona"
    assert spec.targets[0].operation == "get"


def test_both_dimensions_collapse_when_single_permission():
    """Single-permission tool — no routing args needed at all."""
    td = _td([{"artifact": "persona", "operation": "get"}])
    spec = resolve_tool_spec(td, {})
    assert spec.targets[0].artifact == "persona"
    assert spec.targets[0].operation == "get"


def test_multi_dimension_still_requires_llm_input():
    """create_content-shape: multi-artifact, same operation would collapse
    operation; but if both dimensions vary the LLM must still supply them."""
    td = _td([
        {"artifact": "persona", "operation": "create"},
        {"artifact": "persona", "operation": "update"},
        {"artifact": "scenario", "operation": "create"},
        {"artifact": "scenario", "operation": "update"},
    ])
    # Missing both: cannot resolve.
    with pytest.raises(ValueError, match="routing could not be resolved"):
        resolve_tool_spec(td, {})


def test_llm_explicit_value_wins_over_collapse():
    """If the LLM supplies artifact explicitly, we use that, not collapse."""
    td = _td([
        {"artifact": "persona", "operation": "search"},
        {"artifact": "scenario", "operation": "search"},
    ])
    spec = resolve_tool_spec(td, {"artifact": "scenario"})
    assert spec.targets[0].artifact == "scenario"
    assert spec.targets[0].operation == "search"


def test_zero_payload_tools_resolve_cleanly():
    """Tools with only routing args (no payload) must resolve — read tools
    like view_dashboards / delete-by-id commonly have nothing but routing +
    ctx. The handler validates its own required args at call time."""
    td = _td(
        [{"artifact": "attempt", "operation": "activity_get"}],
        args_outputs=[
            {"name": "artifact", "template": "{{ artifact }}"},
            {"name": "operation", "template": "{{ operation }}"},
        ],
    )
    spec = resolve_tool_spec(td, {})
    assert spec.targets[0].artifact == "attempt"
    assert spec.targets[0].operation == "activity_get"
    assert spec.output_map == {}


def test_disallowed_pair_still_rejected():
    """Collapse shouldn't mask unauthorized (artifact, operation) pairs."""
    td = _td([
        {"artifact": "persona", "operation": "search"},
        {"artifact": "scenario", "operation": "search"},
    ])
    with pytest.raises(ValueError, match="not permitted"):
        resolve_tool_spec(td, {"artifact": "cohort"})
