"""Module 08 — Eval seed definitions.

Each eval dict maps directly to CreateEvalItem fields. Beyond the static
{name, description, flag_ids}, every eval is wired to:

  * model_ids           — every model from glow-deploy.yaml (full coverage)
  * model_flag_ids      — one (model, use_custom=true) row per model
  * model_rubric_ids    — one (model, eval-rubric) row per model
  * model_position_ids  — one (model, value=index) row per model, value is
                          the model's index inside this eval's model list

These per-(model, *) sub-resource rows live in `model_flags_resource`,
`model_rubrics_resource`, `model_positions_resource`. Their deterministic IDs
are derived here and re-exported as `model_flags`, `model_rubrics`, and
`model_positions` so the runner can pre-create the resource rows BEFORE the
eval module runs (eval junction inserts FK to those rows).

Threading sub-resources end-to-end is what unblocks `sync_benchmark_entries`
during eval create — without `model_ids`, that helper short-circuits to 0
and benchmark cards never appear.
"""

from uuid import UUID

from database.seeds.ids import sid
from database.seeds.models import models as _model_seeds

# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Flags (from database/seeds/resources/flags.py)
GROUPS_FLAG = sid("flag/groups")
DYNAMIC_FLAG = sid("flag/dynamic")
EVAL_ACTIVE_FLAG = sid("flag/eval-active")

# `use_custom=true` flag (variant emitted by `_flag_pair("use-custom", ...)`).
USE_CUSTOM_TRUE_FLAG = sid("flag/use-custom")

# Common flag set shared by all evals
_EVAL_FLAGS = [GROUPS_FLAG, DYNAMIC_FLAG, EVAL_ACTIVE_FLAG]

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

RUN_EVAL = sid("eval/run")
GROUP_EVAL = sid("eval/group")
AGENT_AGENT_EVAL = sid("eval/agent-agent")
AUTH_AGENT_EVAL = sid("eval/auth-agent")
BENCHMARK_AGENT_EVAL = sid("eval/benchmark-agent")
CHAT_AGENT_AGENT_EVAL = sid("eval/chat-agent-agent")
COHORT_AGENT_EVAL = sid("eval/cohort-agent")
DEPARTMENT_AGENT_EVAL = sid("eval/department-agent")
DOCUMENT_AGENT_EVAL = sid("eval/document-agent")
EVAL_AGENT_EVAL = sid("eval/eval-agent")
FIELD_AGENT_EVAL = sid("eval/field-agent")
GRADE_AGENT_AGENT_EVAL = sid("eval/grade-agent-agent")
MODEL_AGENT_EVAL = sid("eval/model-agent")
PARAMETER_AGENT_EVAL = sid("eval/parameter-agent")
PERSONA_AGENT_EVAL = sid("eval/persona-agent")
PROFILE_AGENT_EVAL = sid("eval/profile-agent")
PROVIDER_AGENT_EVAL = sid("eval/provider-agent")
RUBRIC_AGENT_EVAL = sid("eval/rubric-agent")
SCENARIO_AGENT_EVAL = sid("eval/scenario-agent")
SETTING_AGENT_EVAL = sid("eval/setting-agent")
SIMULATION_AGENT_EVAL = sid("eval/simulation-agent")
TOOL_AGENT_EVAL = sid("eval/tool-agent")
TRAINING_AGENT_EVAL = sid("eval/training-agent")

# ---------------------------------------------------------------------------
# Eval → rubric mapping (1:1)
# ---------------------------------------------------------------------------
# Each eval gets a dedicated rubric resource. The *-agent evals follow the
# `*-rubric` slug; run/group have explicit run-rubric / group-rubric entries
# added in seeds/rubrics.py.

EVAL_RUBRIC_SLUGS: dict[UUID, str] = {
    RUN_EVAL: "run-rubric",
    GROUP_EVAL: "group-rubric",
    AGENT_AGENT_EVAL: "agent-rubric",
    AUTH_AGENT_EVAL: "auth-rubric",
    BENCHMARK_AGENT_EVAL: "benchmark-rubric",
    CHAT_AGENT_AGENT_EVAL: "chat-agent-rubric",
    COHORT_AGENT_EVAL: "cohort-rubric",
    DEPARTMENT_AGENT_EVAL: "department-rubric",
    DOCUMENT_AGENT_EVAL: "document-rubric",
    EVAL_AGENT_EVAL: "eval-rubric",
    FIELD_AGENT_EVAL: "field-rubric",
    GRADE_AGENT_AGENT_EVAL: "grade-agent-rubric",
    MODEL_AGENT_EVAL: "model-rubric",
    PARAMETER_AGENT_EVAL: "parameter-rubric",
    PERSONA_AGENT_EVAL: "persona-rubric",
    PROFILE_AGENT_EVAL: "profile-rubric",
    PROVIDER_AGENT_EVAL: "provider-rubric",
    RUBRIC_AGENT_EVAL: "rubric-rubric",
    SCENARIO_AGENT_EVAL: "scenario-rubric",
    SETTING_AGENT_EVAL: "setting-rubric",
    SIMULATION_AGENT_EVAL: "simulation-rubric",
    TOOL_AGENT_EVAL: "tool-rubric",
    TRAINING_AGENT_EVAL: "training-rubric",
}

EVAL_SLUG_BY_ID: dict[UUID, str] = {
    eval_id: rubric_slug.replace("-rubric", "") if rubric_slug.endswith("-rubric") else rubric_slug
    for eval_id, rubric_slug in EVAL_RUBRIC_SLUGS.items()
}
# A few evals don't follow the simple slug stripping above. Use the eval's
# bare slug (last segment after `eval/`) for position id derivation so the
# sids stay readable + collision-free.
_EVAL_SHORT_SLUGS: dict[UUID, str] = {
    RUN_EVAL: "run",
    GROUP_EVAL: "group",
    AGENT_AGENT_EVAL: "agent-agent",
    AUTH_AGENT_EVAL: "auth-agent",
    BENCHMARK_AGENT_EVAL: "benchmark-agent",
    CHAT_AGENT_AGENT_EVAL: "chat-agent-agent",
    COHORT_AGENT_EVAL: "cohort-agent",
    DEPARTMENT_AGENT_EVAL: "department-agent",
    DOCUMENT_AGENT_EVAL: "document-agent",
    EVAL_AGENT_EVAL: "eval-agent",
    FIELD_AGENT_EVAL: "field-agent",
    GRADE_AGENT_AGENT_EVAL: "grade-agent-agent",
    MODEL_AGENT_EVAL: "model-agent",
    PARAMETER_AGENT_EVAL: "parameter-agent",
    PERSONA_AGENT_EVAL: "persona-agent",
    PROFILE_AGENT_EVAL: "profile-agent",
    PROVIDER_AGENT_EVAL: "provider-agent",
    RUBRIC_AGENT_EVAL: "rubric-agent",
    SCENARIO_AGENT_EVAL: "scenario-agent",
    SETTING_AGENT_EVAL: "setting-agent",
    SIMULATION_AGENT_EVAL: "simulation-agent",
    TOOL_AGENT_EVAL: "tool-agent",
    TRAINING_AGENT_EVAL: "training-agent",
}

# ---------------------------------------------------------------------------
# Per-eval × per-model cross-product helpers
# ---------------------------------------------------------------------------
# Coverage is now per-eval — `EVAL_MODEL_IDS` maps each eval id → the list
# of model resource ids attached to it. Resource ids are the canonical
# `sid("model-resource/<name>")` shape (same value used in models.py:201,
# ROLE_MODEL_IDS, and everywhere else a model is referenced), so the
# mapping is stable across regens and round-trippable from the model name.
#
# To attach more models to an eval, add their `sid("model-resource/<name>")`
# to that eval's list. To narrow further, drop entries. The cross-product
# helpers below (`_ids_for_eval`) walk this per-eval list, so model_flags,
# model_rubrics, and model_positions row counts shrink/grow uniformly.

_GLOW_TEXT_RESOURCE_ID: UUID = sid("model-resource/glow-text")

# Single-model coverage for v1 — every eval gets glow-text only. Swap in
# additional ids per eval as coverage broadens.
EVAL_MODEL_IDS: dict[UUID, list[UUID]] = {
    RUN_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    GROUP_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    AGENT_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    AUTH_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    BENCHMARK_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    CHAT_AGENT_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    COHORT_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    DEPARTMENT_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    DOCUMENT_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    EVAL_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    FIELD_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    GRADE_AGENT_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    MODEL_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    PARAMETER_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    PERSONA_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    PROFILE_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    PROVIDER_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    RUBRIC_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    SCENARIO_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    SETTING_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    SIMULATION_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    TOOL_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
    TRAINING_AGENT_EVAL: [_GLOW_TEXT_RESOURCE_ID],
}

# Reverse name lookup — model_flags / model_rubrics / model_positions sub-resource
# ids derive from the model's *name*, so we still need to resolve resource_id → name.
_MODEL_NAMES_BY_RESOURCE_ID: dict[UUID, str] = {
    m["resource_id"]: m["name"] for m in _model_seeds
}

# Stable, deduplicated union of model ids referenced by *any* eval. Used by
# the runner-exported model_flags / model_rubrics / model_positions seed
# lists (below) so we only create sub-resource rows that an eval actually
# references — no orphan rows for unused models.
def _all_referenced_model_ids() -> list[UUID]:
    seen: set[UUID] = set()
    out: list[UUID] = []
    for ids in EVAL_MODEL_IDS.values():
        for mid in ids:
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
    return out


def _model_flag_id(model_resource_id: UUID) -> UUID:
    """Deterministic id for the (model, use_custom=true) sub-resource row."""
    name = _MODEL_NAMES_BY_RESOURCE_ID[model_resource_id]
    return sid(f"model-flag/{name}/use-custom")


def _model_rubric_id(model_resource_id: UUID, rubric_slug: str) -> UUID:
    """Deterministic id for the (model, rubric) sub-resource row."""
    name = _MODEL_NAMES_BY_RESOURCE_ID[model_resource_id]
    return sid(f"model-rubric/{name}/{rubric_slug}")


def _model_position_id(model_resource_id: UUID, eval_slug: str, position: int) -> UUID:
    """Deterministic id for the (model, eval, position) sub-resource row."""
    name = _MODEL_NAMES_BY_RESOURCE_ID[model_resource_id]
    return sid(f"model-position/{name}/{eval_slug}/{position}")


def _ids_for_eval(eval_id: UUID) -> dict:
    """Build the four cross-product id lists for a single eval entry.

    Pulls the model coverage from `EVAL_MODEL_IDS[eval_id]` so each eval
    can target a different subset. Sub-resource ids (model_flag,
    model_rubric, model_position) are still deterministic from the
    (model_name, eval/rubric_slug, index) triple via sid().
    """
    rubric_slug = EVAL_RUBRIC_SLUGS[eval_id]
    short_slug = _EVAL_SHORT_SLUGS[eval_id]
    model_ids = list(EVAL_MODEL_IDS.get(eval_id, []))
    model_flag_ids = [_model_flag_id(mid) for mid in model_ids]
    model_rubric_ids = [
        _model_rubric_id(mid, rubric_slug) for mid in model_ids
    ]
    model_position_ids = [
        _model_position_id(mid, short_slug, idx)
        for idx, mid in enumerate(model_ids)
    ]
    return dict(
        model_ids=model_ids,
        model_flag_ids=model_flag_ids,
        model_rubric_ids=model_rubric_ids,
        model_position_ids=model_position_ids,
    )


# ---------------------------------------------------------------------------
# Eval definitions
# ---------------------------------------------------------------------------
# Each entry is the static metadata; cross-product fields are merged in below.

_eval_meta = [
    dict(
        id=RUN_EVAL,
        name="Run Evaluation",
        description="Evaluates individual runs from the demo attempt.",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=GROUP_EVAL,
        name="Group Evaluation",
        description="Evaluates the chat group from the demo attempt.",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=AGENT_AGENT_EVAL,
        name="Agent Agent Evaluation",
        description="Evaluation of agent agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=AUTH_AGENT_EVAL,
        name="Auth Agent Evaluation",
        description="Evaluation of auth agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=BENCHMARK_AGENT_EVAL,
        name="Benchmark Agent Evaluation",
        description="Evaluation of benchmark agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=CHAT_AGENT_AGENT_EVAL,
        name="Chat Agent Agent Evaluation",
        description="Evaluation of chat agent agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=COHORT_AGENT_EVAL,
        name="Cohort Agent Evaluation",
        description="Evaluation of cohort agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=DEPARTMENT_AGENT_EVAL,
        name="Department Agent Evaluation",
        description="Evaluation of department agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=DOCUMENT_AGENT_EVAL,
        name="Document Agent Evaluation",
        description="Evaluation of document agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=EVAL_AGENT_EVAL,
        name="Eval Agent Evaluation",
        description="Evaluation of eval agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=FIELD_AGENT_EVAL,
        name="Field Agent Evaluation",
        description="Evaluation of field agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=GRADE_AGENT_AGENT_EVAL,
        name="Grade Agent Agent Evaluation",
        description="Evaluation of grade agent agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=MODEL_AGENT_EVAL,
        name="Model Agent Evaluation",
        description="Evaluation of model agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PARAMETER_AGENT_EVAL,
        name="Parameter Agent Evaluation",
        description="Evaluation of parameter agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PERSONA_AGENT_EVAL,
        name="Persona Agent Evaluation",
        description="Evaluation of persona agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PROFILE_AGENT_EVAL,
        name="Profile Agent Evaluation",
        description="Evaluation of profile agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PROVIDER_AGENT_EVAL,
        name="Provider Agent Evaluation",
        description="Evaluation of provider agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=RUBRIC_AGENT_EVAL,
        name="Rubric Agent Evaluation",
        description="Evaluation of rubric agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=SCENARIO_AGENT_EVAL,
        name="Scenario Agent Evaluation",
        description="Evaluation of scenario agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=SETTING_AGENT_EVAL,
        name="Setting Agent Evaluation",
        description="Evaluation of setting agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=SIMULATION_AGENT_EVAL,
        name="Simulation Agent Evaluation",
        description="Evaluation of simulation agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=TOOL_AGENT_EVAL,
        name="Tool Agent Evaluation",
        description="Evaluation of tool agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=TRAINING_AGENT_EVAL,
        name="Training Agent Evaluation",
        description="Evaluation of training agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
]

evals: list[dict] = [
    {**meta, **_ids_for_eval(meta["id"])} for meta in _eval_meta
]


# ---------------------------------------------------------------------------
# Cross-product sub-resource lists for the runner
# ---------------------------------------------------------------------------
# These are flat lists of dicts (id, model_id, …) that the runner inserts
# directly into model_flags_resource / model_rubrics_resource /
# model_positions_resource BEFORE the eval module runs, so eval junction
# inserts FK-resolve. Deduped by id.

# model_flags rows: one per *referenced* model id (deduped union across
# all evals). use_custom=true is the same flag for every model, so this
# only needs the union — not per-eval.
_seen_flag: set[UUID] = set()
model_flags: list[dict] = []
for _mid in _all_referenced_model_ids():
    _id = _model_flag_id(_mid)
    if _id in _seen_flag:
        continue
    _seen_flag.add(_id)
    model_flags.append(
        dict(id=_id, model_id=_mid, flag_id=USE_CUSTOM_TRUE_FLAG)
    )


# model_rubrics rows: one per (model, eval-rubric) pair, scoped to that
# eval's model coverage from EVAL_MODEL_IDS. Models excluded from an eval
# don't get a model_rubric row for that eval's rubric slug.
_seen_rubric: set[UUID] = set()
model_rubrics: list[dict] = []
for _eval_id, _rubric_slug in EVAL_RUBRIC_SLUGS.items():
    _rubric_resource_id = sid(f"rubric-resource/{_rubric_slug}")
    for _mid in EVAL_MODEL_IDS.get(_eval_id, []):
        _id = _model_rubric_id(_mid, _rubric_slug)
        if _id in _seen_rubric:
            continue
        _seen_rubric.add(_id)
        model_rubrics.append(
            dict(id=_id, model_id=_mid, rubric_id=_rubric_resource_id)
        )


# model_positions rows: one per (model, eval) pair with the position
# index inside that eval's model list. Index is local to the eval, so two
# evals can both have a "position 0" row for the same model — different
# (eval, position) pairs hash to different sids.
_seen_position: set[UUID] = set()
model_positions: list[dict] = []
for _eval_id, _short_slug in _EVAL_SHORT_SLUGS.items():
    for _idx, _mid in enumerate(EVAL_MODEL_IDS.get(_eval_id, [])):
        _id = _model_position_id(_mid, _short_slug, _idx)
        if _id in _seen_position:
            continue
        _seen_position.add(_id)
        model_positions.append(dict(id=_id, model_id=_mid, value=_idx))
