"""Model-level DoS-bound tests (P1 page_size caps + I1 string max_length).

These exercise the Pydantic request models directly — no DB / app needed — so
they are fast and assert exactly what the validation layer rejects/accepts.
"""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError

from app.infra.shared_types import (
    MAX_PAGE_SIZE,
    MAX_SEARCH_LIMIT,
    MAX_TEXT_FIELD_LEN,
)

# (module path, request-model class name, the standard page-size cap that model
#  enforces). Auth fetches a whole reference list so caps at MAX_SEARCH_LIMIT;
#  every other artifact search caps at MAX_PAGE_SIZE.
_SEARCH_MODELS = [
    ("app.routes.agent.search", "SearchAgentApiRequest", MAX_PAGE_SIZE),
    ("app.routes.auth.search", "SearchAuthApiRequest", MAX_SEARCH_LIMIT),
    ("app.routes.cohort.search", "SearchCohortApiRequest", MAX_PAGE_SIZE),
    ("app.routes.department.search", "SearchDepartmentApiRequest", MAX_PAGE_SIZE),
    ("app.routes.document.search", "SearchDocumentApiRequest", MAX_PAGE_SIZE),
    ("app.routes.eval.search", "SearchEvalApiRequest", MAX_PAGE_SIZE),
    ("app.routes.field.search", "SearchFieldApiRequest", MAX_PAGE_SIZE),
    ("app.routes.model.search", "SearchModelApiRequest", MAX_PAGE_SIZE),
    ("app.routes.parameter.search", "SearchParameterApiRequest", MAX_PAGE_SIZE),
    ("app.routes.persona.search", "SearchPersonaApiRequest", MAX_PAGE_SIZE),
    ("app.routes.profile.search", "SearchProfileApiRequest", MAX_PAGE_SIZE),
    ("app.routes.provider.search", "SearchProviderApiRequest", MAX_PAGE_SIZE),
    ("app.routes.rubric.search", "SearchRubricApiRequest", MAX_PAGE_SIZE),
    ("app.routes.scenario.search", "SearchScenarioApiRequest", MAX_PAGE_SIZE),
    ("app.routes.simulation.search", "SearchSimulationApiRequest", MAX_PAGE_SIZE),
    ("app.routes.test.search", "SearchTestApiRequest", MAX_PAGE_SIZE),
    ("app.routes.tool.search", "SearchToolApiRequest", MAX_PAGE_SIZE),
]


def _resolve(module_path: str, class_name: str):
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


@pytest.mark.parametrize("module_path,class_name,cap", _SEARCH_MODELS)
def test_search_model_rejects_oversized_page_size(module_path, class_name, cap):
    """page_size far above the cap is rejected (422 at the route boundary)."""
    model = _resolve(module_path, class_name)
    with pytest.raises(ValidationError):
        model(page_size=10_000_000)


@pytest.mark.parametrize("module_path,class_name,cap", _SEARCH_MODELS)
def test_search_model_rejects_page_size_just_over_cap(module_path, class_name, cap):
    model = _resolve(module_path, class_name)
    with pytest.raises(ValidationError):
        model(page_size=cap + 1)


@pytest.mark.parametrize("module_path,class_name,cap", _SEARCH_MODELS)
def test_search_model_rejects_non_positive_page_size(module_path, class_name, cap):
    model = _resolve(module_path, class_name)
    with pytest.raises(ValidationError):
        model(page_size=0)


@pytest.mark.parametrize("module_path,class_name,cap", _SEARCH_MODELS)
def test_search_model_accepts_normal_page_size(module_path, class_name, cap):
    """A normal in-range page_size still validates fine."""
    model = _resolve(module_path, class_name)
    instance = model(page_size=10)
    assert instance.page_size == 10


# --------------------------------------------------------------------------
# I1(2): string max_length on create/update artifact models
# --------------------------------------------------------------------------

def test_create_model_rejects_oversized_name():
    """A name beyond MAX_TEXT_FIELD_LEN is rejected (memory-exhaustion guard)."""
    from app.infra.auth.types import CreateAuthItem

    with pytest.raises(ValidationError):
        CreateAuthItem(name="x" * (MAX_TEXT_FIELD_LEN + 1))


def test_create_model_rejects_oversized_description():
    from app.infra.auth.types import CreateAuthItem

    with pytest.raises(ValidationError):
        CreateAuthItem(description="d" * (MAX_TEXT_FIELD_LEN + 1))


def test_create_model_accepts_normal_strings():
    """Normal-length name/description/slug pass."""
    from app.infra.auth.types import CreateAuthItem

    item = CreateAuthItem(name="My Provider", description="x" * 500, slug="my-provider")
    assert item.name == "My Provider"


def test_update_model_rejects_oversized_name():
    from uuid import uuid4

    from app.infra.auth.types import UpdateAuthItem

    with pytest.raises(ValidationError):
        UpdateAuthItem(id=uuid4(), name="x" * (MAX_TEXT_FIELD_LEN + 1))
