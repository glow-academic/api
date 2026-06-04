"""Tests for persona permission helpers — pure business logic.

All functions here are sync compute helpers. Don't add `pytestmark =
pytest.mark.asyncio` at module level: pytest-asyncio in strict mode
emits a warning per sync test under an asyncio mark.
"""

from uuid import uuid4

from app.infra.persona.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.persona.permissions import compute_can_create
from app.infra.persona.permissions import (
    compute_show_color,
    compute_show_departments,
    compute_show_description,
    compute_show_examples,
    compute_show_flag,
    compute_show_icon,
    compute_show_instructions,
    compute_show_name,
    compute_show_parameter_fields,
    compute_show_parameters,
    compute_name_required,
    compute_description_required,
    compute_color_required,
    compute_icon_required,
    compute_instructions_required,
    compute_flag_required,
    get_missing_tools,
)

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    def test_admin_with_matching_departments_can_edit(self):
        assert compute_can_edit(1, [("persona", "update")], [_DEPT], 0, [_DEPT]) is True

    def test_superadmin_can_edit_default(self):
        assert compute_can_edit(0, [("persona", "update")], None, 0) is True

    def test_admin_cannot_edit_default(self):
        assert compute_can_edit(1, [("persona", "update")], None, 0) is False

    def test_member_cannot_edit(self):
        assert compute_can_edit(3, [], [_DEPT], 0) is False

    def test_blocked_by_usage(self):
        assert compute_can_edit(1, [("persona", "update")], [_DEPT], 1) is False


class TestComputeDisabledReason:
    def test_returns_none_when_allowed(self):
        assert compute_disabled_reason(1, [("persona", "update")], [_DEPT], 0, [_DEPT]) is None

    def test_returns_reason_for_default(self):
        reason = compute_disabled_reason(1, [("persona", "update")], None, 0)
        assert reason is not None
        assert "default" in reason.lower()

    def test_returns_reason_for_usage(self):
        reason = compute_disabled_reason(1, [("persona", "update")], [_DEPT], 1)
        assert reason is not None

    def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(3, [], [_DEPT], 0)
        assert reason is not None


class TestHasAccess:
    def test_superadmin_always_has_access(self):
        assert has_access(0, None, [_DEPT]) is True

    def test_no_entity_departments_means_accessible(self):
        assert has_access(3, [_DEPT], None) is True

    def test_overlap_grants_access(self):
        assert has_access(1, [_DEPT], [_DEPT]) is True

    def test_no_overlap_denies_access(self):
        assert has_access(1, [_DEPT], [_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    def test_can_delete_granted(self):
        assert compute_can_delete(1, [("persona", "delete")], [_DEPT], 0) is True

    def test_can_delete_blocked_by_usage(self):
        assert compute_can_delete(1, [("persona", "delete")], [_DEPT], 1) is False

    def test_owner_in_department_can_delete(self):
        assert compute_can_delete(1, [("persona", "delete")], [_DEPT], 0, [_DEPT]) is True

    def test_cross_department_delete_denied(self):
        # Actor in Dept A (_OTHER) must NOT delete a Dept-B (_DEPT) persona.
        assert compute_can_delete(1, [("persona", "delete")], [_DEPT], 0, [_OTHER]) is False

    def test_superadmin_bypasses_department_scope_on_delete(self):
        assert compute_can_delete(0, [("persona", "delete")], [_DEPT], 0, [_OTHER]) is True

    def test_can_duplicate_granted(self):
        assert compute_can_duplicate(1, [("persona", "duplicate")]) is True

    def test_can_duplicate_denied(self):
        assert compute_can_duplicate(3, []) is False

    def test_owner_in_department_can_duplicate(self):
        assert compute_can_duplicate(1, [("persona", "duplicate")], [_DEPT], [_DEPT]) is True

    def test_cross_department_duplicate_denied(self):
        # Actor in Dept A (_OTHER) must NOT duplicate a Dept-B (_DEPT) persona.
        assert compute_can_duplicate(1, [("persona", "duplicate")], [_DEPT], [_OTHER]) is False

    def test_superadmin_bypasses_department_scope_on_duplicate(self):
        assert compute_can_duplicate(0, [("persona", "duplicate")], [_DEPT], [_OTHER]) is True

    def test_can_create_with_departments(self):
        assert compute_can_create(1, [("persona", "create")], [_DEPT]) is True

    def test_cannot_create_without_department(self):
        assert compute_can_create(1, [("persona", "create")], None) is False

    def test_member_cannot_create(self):
        assert compute_can_create(3, [], [_DEPT]) is False

    def test_can_draft_granted(self):
        assert compute_can_draft(1, [("persona", "draft")]) is True

    def test_can_draft_denied(self):
        assert compute_can_draft(3, []) is False


# ─── compute_show_* pickers ────────────────────────────────────────────────


class TestComputeShowPickers:
    """The `show_*` family answers: should the UI render this picker?

    Most pickers gate on the count of available items in the relevant
    resource set: zero items → hide the picker (nothing to pick from).
    A few are unconditional (name, description, instructions, flag) —
    those have no count-based gating and must return True.

    Tests below pin both behaviors so a future "tighten the UI" change
    (e.g. hide name unless it has tools) can't quietly slip through.
    """

    def test_name_always_shown_regardless_of_has_tools(self):
        assert compute_show_name(names_has_tools=True) is True
        assert compute_show_name(names_has_tools=False) is True

    def test_description_always_shown(self):
        assert compute_show_description() is True

    def test_instructions_always_shown(self):
        assert compute_show_instructions(instructions_has_tools=True) is True
        assert compute_show_instructions(instructions_has_tools=False) is True

    def test_flag_always_shown(self):
        assert compute_show_flag() is True

    def test_color_gated_on_count(self):
        assert compute_show_color(colors_has_tools=True, colors_count=0) is False
        assert compute_show_color(colors_has_tools=False, colors_count=1) is True
        assert compute_show_color(colors_has_tools=True, colors_count=5) is True

    def test_icon_gated_on_count(self):
        assert compute_show_icon(icons_has_tools=True, icons_count=0) is False
        assert compute_show_icon(icons_has_tools=False, icons_count=3) is True

    def test_departments_gated_on_count(self):
        assert compute_show_departments(departments_count=0) is False
        assert compute_show_departments(departments_count=2) is True

    def test_parameter_fields_gated_on_count(self):
        assert compute_show_parameter_fields(parameter_fields_count=0) is False
        assert compute_show_parameter_fields(parameter_fields_count=1) is True

    def test_examples_gated_on_count(self):
        assert compute_show_examples(examples_count=0) is False
        assert compute_show_examples(examples_count=1) is True

    def test_parameters_gated_on_count(self):
        assert compute_show_parameters(parameters_count=0) is False
        assert compute_show_parameters(parameters_count=4) is True


# ─── compute_*_required ────────────────────────────────────────────────────


class TestComputeRequiredFlags:
    """Pin the canonical required-field set. A regression here would
    silently relax (or tighten) input validation on persona save."""

    def test_required_fields(self):
        assert compute_name_required() is True
        assert compute_color_required() is True
        assert compute_icon_required() is True
        assert compute_instructions_required() is True

    def test_description_is_optional(self):
        assert compute_description_required() is False

    def test_flag_is_optional(self):
        assert compute_flag_required() is False


# ─── get_missing_tools ─────────────────────────────────────────────────────


class TestGetMissingTools:
    """`get_missing_tools` lists which AI-generator-backed fields lack
    a configured tool. Ordering matters for the UI surface — the list
    is rendered in this order to the operator.

    `show_*` flags gate the optional-field checks: when show_examples
    is False, missing examples tools don't surface here (the operator
    can't see the field anyway).
    """

    def _all_have_tools_kwargs(self) -> dict[str, bool]:
        return dict(
            names_has_tools=True,
            colors_has_tools=True,
            icons_has_tools=True,
            instructions_has_tools=True,
            show_departments=True,
            departments_has_tools=True,
            show_parameter_fields=True,
            parameter_fields_has_tools=True,
            show_examples=True,
            examples_has_tools=True,
        )

    def test_no_missing_when_all_have_tools(self):
        assert get_missing_tools(**self._all_have_tools_kwargs()) == []

    def test_missing_required_fields_listed_first_in_canonical_order(self):
        """Always-required fields (name, color, icon, instructions)
        appear in the missing list even if the optional-field flags
        are all off, and they appear in declaration order."""
        result = get_missing_tools(
            names_has_tools=False,
            colors_has_tools=False,
            icons_has_tools=False,
            instructions_has_tools=False,
            show_departments=False,  # gated off
            departments_has_tools=False,
            show_parameter_fields=False,  # gated off
            parameter_fields_has_tools=False,
            show_examples=False,  # gated off
            examples_has_tools=False,
        )
        assert result == ["name", "color", "icon", "instructions"]

    def test_optional_field_missing_only_when_shown(self):
        """When show_departments=False, a missing departments tool is
        NOT surfaced — operator can't see the picker so demanding the
        tool would be confusing."""
        hidden_dept = get_missing_tools(
            **{**self._all_have_tools_kwargs(),
               "show_departments": False,
               "departments_has_tools": False}
        )
        shown_dept = get_missing_tools(
            **{**self._all_have_tools_kwargs(),
               "show_departments": True,
               "departments_has_tools": False}
        )

        assert "departments" not in hidden_dept
        assert "departments" in shown_dept

    def test_all_missing_includes_optionals_in_canonical_order(self):
        """Required + optional missing together: declaration order is
        name → color → icon → instructions → departments →
        parameter_fields → examples."""
        result = get_missing_tools(
            names_has_tools=False,
            colors_has_tools=False,
            icons_has_tools=False,
            instructions_has_tools=False,
            show_departments=True,
            departments_has_tools=False,
            show_parameter_fields=True,
            parameter_fields_has_tools=False,
            show_examples=True,
            examples_has_tools=False,
        )
        assert result == [
            "name", "color", "icon", "instructions",
            "departments", "parameter_fields", "examples",
        ]
