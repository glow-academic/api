"""Module 03 — Model seed definitions (config-driven).

All model metadata (modalities, reasoning levels, temperature ranges,
pricing, voices, qualities) is read from glow-deploy.yaml and resolved
to UUIDs dynamically.  No hardcoded legacy model definitions.
"""

from __future__ import annotations

from uuid import UUID

from database.seeds.config import get_ai_models, get_ai_roles, load_deploy_config
from database.seeds.ids import sid
from database.seeds.providers import PROVIDER_IDS

# ---------------------------------------------------------------------------
# Resource lookups — map human-readable names to seed UUIDs
# ---------------------------------------------------------------------------

from database.seeds.resources.modalities import modalities as _all_modalities

_MODALITY_LOOKUP: dict[str, UUID] = {
    f"{m['modality']}_{'in' if m['is_input'] else 'out'}": m["id"]
    for m in _all_modalities
}

from database.seeds.resources.reasoning_levels import reasoning_levels as _all_reasoning

# Reasoning levels are duplicated per model group — deduplicate by name,
# keeping the first occurrence.
_REASONING_LOOKUP: dict[str, UUID] = {}
for _r in _all_reasoning:
    _rname = _r["reasoning_level"]
    if _rname not in _REASONING_LOOKUP:
        _REASONING_LOOKUP[_rname] = _r["id"]

from database.seeds.resources.voices import voices as _all_voices

_VOICE_LOOKUP: dict[str, UUID] = {v["voice"]: v["id"] for v in _all_voices}

from database.seeds.resources.qualities import qualities as _all_qualities

_QUALITY_LOOKUP: dict[str, UUID] = {q["quality"]: q["id"] for q in _all_qualities}

from database.seeds.resources.flags import flags as _all_flags

_MODEL_ACTIVE_FLAG_ID: UUID | None = next(
    (f["id"] for f in _all_flags if f.get("type") == "model_active"), None
)

# ---------------------------------------------------------------------------
# Load deploy config
# ---------------------------------------------------------------------------

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"ai": {"providers": [], "models": [], "roles": {}}}

_config_models_raw = get_ai_models(_config)
_roles = get_ai_roles(_config)


# ---------------------------------------------------------------------------
# Helper: generate temperature level IDs from {min, max, step}
# ---------------------------------------------------------------------------

def _temperature_ids(model_name: str, temp_cfg: dict) -> list[UUID]:
    """Generate deterministic temperature level UUIDs for a model.

    temp_cfg: {"min": 0, "max": 1.0, "step": 0.01}
    """
    t_min = float(temp_cfg.get("min", 0))
    t_max = float(temp_cfg.get("max", 1.0))
    t_step = float(temp_cfg.get("step", 0.01))
    if t_step <= 0:
        return []
    ids: list[UUID] = []
    # Use integer arithmetic to avoid float drift
    steps = round((t_max - t_min) / t_step)
    for i in range(steps + 1):
        value = round(t_min + i * t_step, 4)
        ids.append(sid(f"temperature/{model_name}/{value}"))
    return ids


# ---------------------------------------------------------------------------
# Helper: generate pricing IDs from [{type, price, unit}]
# ---------------------------------------------------------------------------

def _pricing_ids(model_name: str, pricing_list: list[dict]) -> list[UUID]:
    """Generate deterministic pricing UUIDs for a model."""
    ids: list[UUID] = []
    for p in pricing_list:
        p_type = p.get("type", "input")
        p_price = p.get("price", 0)
        p_unit = p.get("unit", "million_text")
        ids.append(sid(f"pricing/{model_name}/{p_type}/{p_unit}/{p_price}"))
    return ids


# ---------------------------------------------------------------------------
# Build model dicts from config
# ---------------------------------------------------------------------------

models: list[dict] = []

for _m in _config_models_raw:
    _name = _m.get("name", "")
    _prov = _m.get("provider", "")
    _prov_id = PROVIDER_IDS.get(_prov)
    if not _name or not _prov_id:
        continue

    # Modalities
    _mod_ids: list[UUID] = []
    for _mod_name in _m.get("modalities", []):
        _mid = _MODALITY_LOOKUP.get(_mod_name)
        if _mid:
            _mod_ids.append(_mid)

    # Reasoning levels
    _reason_ids: list[UUID] = []
    for _rl_name in _m.get("reasoning_levels", []):
        _rid = _REASONING_LOOKUP.get(_rl_name)
        if _rid:
            _reason_ids.append(_rid)

    # Temperature levels
    _temp_ids: list[UUID] = []
    _temp_cfg = _m.get("temperature")
    if _temp_cfg and isinstance(_temp_cfg, dict):
        _temp_ids = _temperature_ids(_name, _temp_cfg)

    # Pricing
    _price_ids: list[UUID] = []
    _pricing_cfg = _m.get("pricing")
    if _pricing_cfg and isinstance(_pricing_cfg, list):
        _price_ids = _pricing_ids(_name, _pricing_cfg)

    # Voices
    _voice_ids: list[UUID] = []
    for _vname in _m.get("voices", []):
        _vid = _VOICE_LOOKUP.get(_vname)
        if _vid:
            _voice_ids.append(_vid)

    # Qualities
    _quality_ids: list[UUID] = []
    for _qname in _m.get("qualities", []):
        _qid = _QUALITY_LOOKUP.get(_qname)
        if _qid:
            _quality_ids.append(_qid)

    # Flags — all models get the model_active flag
    _flag_ids: list[UUID] = []
    if _MODEL_ACTIVE_FLAG_ID:
        _flag_ids.append(_MODEL_ACTIVE_FLAG_ID)

    models.append(
        dict(
            id=sid(f"model/{_name}"),
            name=_name,
            description=_m.get("description", _name),
            provider_ids=[_prov_id],
            flag_ids=_flag_ids,
            modality_ids=_mod_ids,
            pricing_ids=_price_ids,
            reasoning_level_ids=_reason_ids,
            temperature_level_ids=_temp_ids,
            voice_ids=_voice_ids,
            quality_ids=_quality_ids,
        )
    )

# ---------------------------------------------------------------------------
# Role → model ID mapping (for agents)
# ---------------------------------------------------------------------------

ROLE_MODEL_IDS: dict[str, UUID] = {}
for _role, _model_name in _roles.items():
    ROLE_MODEL_IDS[_role] = sid(f"model/{_model_name}")

DEFAULT_TEXT_MODEL: UUID | None = ROLE_MODEL_IDS.get("text")
