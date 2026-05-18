"""execute_infra_operation kwargs-path type coercion.

render_output_map Jinja-stringifies every arg. The kwargs-path target
function may declare int/bool/UUID/list[T], so we coerce via
pydantic.TypeAdapter before calling.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.tools.execute_infra_operation import _coerce_kwargs_to_signature


async def sample_fn(
    pool,
    redis,
    *,
    page: int = 1,
    page_size: int = 20,
    active: bool = True,
    persona_id: UUID | None = None,
    search: str | None = None,
    tag_ids: list[UUID] | None = None,
) -> dict:
    return {}


def test_string_int_coerces_to_int():
    out = _coerce_kwargs_to_signature(sample_fn, {"page": "1", "page_size": "50"})
    assert out == {"page": 1, "page_size": 50}
    assert isinstance(out["page"], int)


def test_string_bool_coerces_to_bool():
    out = _coerce_kwargs_to_signature(sample_fn, {"active": "true"})
    assert out == {"active": True}


def test_string_uuid_coerces_to_uuid():
    pid = "12345678-1234-5678-1234-567812345678"
    out = _coerce_kwargs_to_signature(sample_fn, {"persona_id": pid})
    assert out == {"persona_id": UUID(pid)}


def test_string_stays_string():
    out = _coerce_kwargs_to_signature(sample_fn, {"search": "alice"})
    assert out == {"search": "alice"}


def test_list_of_uuids_from_strings():
    pid_1 = "12345678-1234-5678-1234-567812345678"
    pid_2 = "87654321-4321-8765-4321-876543218765"
    out = _coerce_kwargs_to_signature(sample_fn, {"tag_ids": [pid_1, pid_2]})
    assert out["tag_ids"] == [UUID(pid_1), UUID(pid_2)]


def test_uncoercible_value_passes_through_unchanged():
    """If Pydantic can't parse it, return the original — let the handler
    surface the actual error instead of masking it."""
    out = _coerce_kwargs_to_signature(sample_fn, {"page": "not-a-number"})
    # Value kept as-is so the underlying handler (or Pydantic downstream)
    # produces an accurate error message.
    assert out == {"page": "not-a-number"}


def test_unknown_kwarg_passes_through():
    """Kwargs not in the function signature are passed through verbatim."""
    out = _coerce_kwargs_to_signature(sample_fn, {"page": "1", "extra": "x"})
    assert out["page"] == 1
    assert out["extra"] == "x"


def test_none_value_passes_through():
    out = _coerce_kwargs_to_signature(sample_fn, {"active": None})
    assert out == {"active": None}


def test_missing_type_hint_passes_through():
    async def untyped(pool, redis, *, thing) -> dict:
        return {}

    out = _coerce_kwargs_to_signature(untyped, {"thing": "42"})
    # No hint on `thing` → string stays string.
    assert out == {"thing": "42"}
