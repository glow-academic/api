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


# --------------------------------------------------------------------------
# C4-B: WS search payload page_size caps via the shared base
# --------------------------------------------------------------------------
# The le=200 cap originally landed only on the HTTP request models (#336) and
# the single WS attempt.search model (#354 B1). Every other WS search payload
# defined its own ``page_size: int = Field(<default>)`` with NO upper bound, so
# a socket sending ``{"page_size": 10_000_000}`` bypassed the DoS fix straight
# into ``search_*_impl``. All WS search payloads now inherit a shared base
# (PaginatedWsSearch / PagedWsSearch) that bounds page_size to MAX_PAGE_SIZE.
from app.ws.pagination import (  # noqa: E402
    MAX_WS_PAGE_SIZE,
    PaginatedWsSearch,
    PagedWsSearch,
)

# (module path, payload class name, shared base it must inherit). This is the
# FULL WS-search-payload sweep. ``LeaderboardSearchPayload`` and
# ``SettingSearchPayload`` are intentionally excluded — their impls take no
# client-controlled page_size (leaderboard has no LIMIT; setting uses a fixed
# server-side limit), so they carry no page_size field and stay on BaseModel.
_WS_SEARCH_PAYLOADS = [
    ("app.ws.agent.search", "AgentSearchPayload", PaginatedWsSearch),
    ("app.ws.auth.search", "AuthSearchPayload", PaginatedWsSearch),
    ("app.ws.cohort.search", "CohortSearchPayload", PaginatedWsSearch),
    ("app.ws.department.search", "DepartmentSearchPayload", PaginatedWsSearch),
    ("app.ws.document.search", "DocumentSearchPayload", PaginatedWsSearch),
    ("app.ws.eval.search", "EvalSearchPayload", PaginatedWsSearch),
    ("app.ws.field.search", "FieldSearchPayload", PaginatedWsSearch),
    ("app.ws.model.search", "ModelSearchPayload", PaginatedWsSearch),
    ("app.ws.parameter.search", "ParameterSearchPayload", PaginatedWsSearch),
    ("app.ws.persona.search", "PersonaSearchPayload", PaginatedWsSearch),
    ("app.ws.profile.search", "ProfileSearchPayload", PaginatedWsSearch),
    ("app.ws.provider.search", "ProviderSearchPayload", PaginatedWsSearch),
    ("app.ws.rubric.search", "RubricSearchPayload", PaginatedWsSearch),
    ("app.ws.scenario.search", "ScenarioSearchPayload", PaginatedWsSearch),
    ("app.ws.simulation.search", "SimulationSearchPayload", PaginatedWsSearch),
    ("app.ws.tool.search", "ToolSearchPayload", PaginatedWsSearch),
    ("app.ws.system.activity.search", "ActivitySearchPayload", PagedWsSearch),
    ("app.ws.system.pricing.search", "PricingSearchPayload", PagedWsSearch),
]


@pytest.mark.parametrize("module_path,class_name,base", _WS_SEARCH_PAYLOADS)
def test_ws_search_payload_inherits_shared_base(module_path, class_name, base):
    """Every WS search payload inherits the shared paginated base so the cap
    can never drift away one endpoint at a time again."""
    model = _resolve(module_path, class_name)
    assert issubclass(model, base), f"{class_name} must inherit {base.__name__}"


@pytest.mark.parametrize("module_path,class_name,base", _WS_SEARCH_PAYLOADS)
def test_ws_search_payload_rejects_oversized_page_size(module_path, class_name, base):
    """A socket sending page_size=10_000_000 is rejected at the model boundary
    (the WS handler treats the ValidationError as <event>.failed → no query)."""
    model = _resolve(module_path, class_name)
    with pytest.raises(ValidationError):
        model(page_size=10_000_000)


@pytest.mark.parametrize("module_path,class_name,base", _WS_SEARCH_PAYLOADS)
def test_ws_search_payload_rejects_page_size_just_over_cap(module_path, class_name, base):
    model = _resolve(module_path, class_name)
    with pytest.raises(ValidationError):
        model(page_size=MAX_WS_PAGE_SIZE + 1)


@pytest.mark.parametrize("module_path,class_name,base", _WS_SEARCH_PAYLOADS)
def test_ws_search_payload_rejects_non_positive_page_size(module_path, class_name, base):
    model = _resolve(module_path, class_name)
    with pytest.raises(ValidationError):
        model(page_size=0)


@pytest.mark.parametrize("module_path,class_name,base", _WS_SEARCH_PAYLOADS)
def test_ws_search_payload_accepts_cap_value(module_path, class_name, base):
    """The cap itself (200) still validates — only values above it are rejected."""
    model = _resolve(module_path, class_name)
    assert model(page_size=MAX_WS_PAGE_SIZE).page_size == MAX_WS_PAGE_SIZE


def test_ws_max_page_size_matches_http_cap():
    """The WS cap is the *same* shared constant as the HTTP cap (no drift)."""
    assert MAX_WS_PAGE_SIZE == MAX_PAGE_SIZE


def test_ws_auth_payload_keeps_large_default_but_caps_explicit():
    """auth.search legitimately defaults to a whole-reference-list page (1000);
    the default is preserved (Pydantic does not validate defaults) but an
    explicit oversized value is still rejected."""
    from app.ws.auth.search import AuthSearchPayload

    assert AuthSearchPayload().page_size == 1000
    with pytest.raises(ValidationError):
        AuthSearchPayload(page_size=10_000_000)


# --------------------------------------------------------------------------
# C4-A: ListPricingRequest (/system/groups) page/page_size cap
# --------------------------------------------------------------------------

def test_list_pricing_request_rejects_oversized_page_size():
    """/system/groups binds ListPricingRequest directly; an uncapped page_size
    materialized limit+offset+1000 MV rows. It must now be bounded."""
    from app.infra.pricing.types import ListPricingRequest

    with pytest.raises(ValidationError):
        ListPricingRequest(page_size=10_000_000)


def test_list_pricing_request_rejects_page_size_just_over_cap():
    from app.infra.pricing.types import ListPricingRequest

    with pytest.raises(ValidationError):
        ListPricingRequest(page_size=MAX_PAGE_SIZE + 1)


def test_list_pricing_request_rejects_non_positive():
    from app.infra.pricing.types import ListPricingRequest

    with pytest.raises(ValidationError):
        ListPricingRequest(page_size=0)
    with pytest.raises(ValidationError):
        ListPricingRequest(page=-1)


def test_list_pricing_request_accepts_normal():
    from app.infra.pricing.types import ListPricingRequest

    req = ListPricingRequest(page=1, page_size=50)
    assert req.page == 1
    assert req.page_size == 50


# --------------------------------------------------------------------------
# C4-C: annotation-array bounds on the attempt-chat grade write paths
# --------------------------------------------------------------------------
# Each item/nested item is a per-item DB INSERT inside one grade-write
# transaction; an unbounded array lets one request fan out arbitrarily many
# round trips / hold the transaction open (resource-exhaustion DoS). The lists
# are bounded to MAX_BULK_ITEMS, consistent with the bulk-create endpoints.
from app.infra.shared_types import MAX_BULK_ITEMS  # noqa: E402


def test_chat_strengths_request_caps_strengths_and_highlights():
    from app.routes.attempt.chat_strengths import (
        ChatStrengthItem,
        ChatStrengthsRequest,
    )

    chat_id = __import__("uuid").uuid4()
    one = ChatStrengthItem(name="n", description="d")
    # top-level strengths array bounded
    with pytest.raises(ValidationError):
        ChatStrengthsRequest(chat_id=chat_id, strengths=[one] * (MAX_BULK_ITEMS + 1))
    # nested highlights array bounded
    hl = {"section": "s"}
    with pytest.raises(ValidationError):
        ChatStrengthItem(name="n", description="d", highlights=[hl] * (MAX_BULK_ITEMS + 1))
    # a normal-sized payload still validates
    ok = ChatStrengthsRequest(chat_id=chat_id, strengths=[one] * 3)
    assert len(ok.strengths) == 3


def test_chat_improvements_request_caps_improvements_and_replacements():
    from app.routes.attempt.chat_improvements import (
        ChatImprovementItem,
        ChatImprovementsRequest,
    )

    chat_id = __import__("uuid").uuid4()
    one = ChatImprovementItem(name="n", description="d")
    with pytest.raises(ValidationError):
        ChatImprovementsRequest(chat_id=chat_id, improvements=[one] * (MAX_BULK_ITEMS + 1))
    rpl = {"section": "s", "replace": "r"}
    with pytest.raises(ValidationError):
        ChatImprovementItem(name="n", description="d", replacements=[rpl] * (MAX_BULK_ITEMS + 1))


def test_chat_analyses_request_caps_analyses():
    from app.routes.attempt.chat_analyses import (
        ChatAnalysesRequest,
        ChatAnalysisItem,
    )

    chat_id = __import__("uuid").uuid4()
    one = ChatAnalysisItem(content="c")
    with pytest.raises(ValidationError):
        ChatAnalysesRequest(chat_id=chat_id, analyses=[one] * (MAX_BULK_ITEMS + 1))


def test_chat_feedback_request_caps_feedbacks():
    from app.routes.attempt.chat_feedback import (
        ChatFeedbackItem,
        ChatFeedbackRequest,
    )

    chat_id = __import__("uuid").uuid4()
    one = ChatFeedbackItem(feedback="f")
    with pytest.raises(ValidationError):
        ChatFeedbackRequest(chat_id=chat_id, feedbacks=[one] * (MAX_BULK_ITEMS + 1))


def test_chat_hints_request_caps_hints():
    """I1: the 5th C4-C sibling — chat_hints' array was the one left unbounded.
    A normal-sized payload still validates; oversized is rejected."""
    from app.routes.attempt.chat_hints import ChatHintItem, ChatHintsRequest

    chat_id = __import__("uuid").uuid4()
    one = ChatHintItem(hint="h")
    with pytest.raises(ValidationError):
        ChatHintsRequest(chat_id=chat_id, hints=[one] * (MAX_BULK_ITEMS + 1))
    ok = ChatHintsRequest(chat_id=chat_id, hints=[one] * 3)
    assert len(ok.hints) == 3
