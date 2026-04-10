"""Module 03 — Model seed definitions (config-driven).

All model metadata is read from glow-deploy.yaml. Dynamic resources
(temperature levels, pricing, voices) are generated from model configs
and exported for the runner to create before the models themselves.
"""

from __future__ import annotations

from uuid import UUID

from database.seeds.config import get_ai_models, get_ai_roles, load_deploy_config
from database.seeds.ids import sid
from database.seeds.providers import PROVIDER_IDS

# ---------------------------------------------------------------------------
# Static resource lookups (these resources are seeded independently)
# ---------------------------------------------------------------------------

from database.seeds.resources.modalities import modalities as _all_modalities

_MODALITY_LOOKUP: dict[str, UUID] = {
    f"{m['modality']}_{'in' if m['is_input'] else 'out'}": m["id"]
    for m in _all_modalities
}

from database.seeds.resources.reasoning_levels import reasoning_levels as _all_reasoning

_REASONING_LOOKUP: dict[str, UUID] = {}
for _r in _all_reasoning:
    _rname = _r["reasoning_level"]
    if _rname not in _REASONING_LOOKUP:
        _REASONING_LOOKUP[_rname] = _r["id"]

from database.seeds.resources.qualities import qualities as _all_qualities

_QUALITY_LOOKUP: dict[str, UUID] = {q["quality"]: q["id"] for q in _all_qualities}

from database.seeds.resources.temperature_levels import TEMPERATURE_LOOKUP

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
# Dynamic resources — generated from model configs, exported for runner
# ---------------------------------------------------------------------------

# Pricing: {id, pricing_type, price, unit_name, unit_category, unit_value}
# Deduplicated globally — same price point shared across models
dynamic_pricing: list[dict] = []
_pricing_id_set: set[UUID] = set()

# Voices: {id, voice} — deduplicated globally by voice name
dynamic_voices: list[dict] = []
_voice_names_seen: set[str] = set()


def _lookup_temperatures(temp_cfg: dict) -> list[UUID]:
    """Look up temperature level UUIDs from the static pool for a model's range."""
    t_min = float(temp_cfg.get("min", 0))
    t_max = float(temp_cfg.get("max", 2.0))
    ids: list[UUID] = []
    for value, uid in TEMPERATURE_LOOKUP.items():
        if t_min <= value <= t_max:
            ids.append(uid)
    return sorted(ids, key=lambda u: str(u))  # stable order


def _generate_pricing(model_name: str, pricing_list: list[dict]) -> list[UUID]:
    """Generate pricing resources and return their IDs."""
    ids: list[UUID] = []
    for p in pricing_list:
        p_type = p.get("type", "input")
        p_price = float(p.get("price", 0))
        p_unit = p.get("unit", "million_text")
        pid = sid(f"pricing/{model_name}/{p_type}/{p_unit}/{p_price}")
        ids.append(pid)
        if pid not in _pricing_id_set:
            _pricing_id_set.add(pid)
            # Determine unit_category from unit_name (must match unit_type enum: tokens, seconds, units)
            if "second" in p_unit:
                category = "seconds"
            elif "image" in p_unit or "video" in p_unit:
                category = "units"
            else:
                category = "tokens"
            unit_value = 1000000 if "million" in p_unit else 1
            dynamic_pricing.append(dict(
                id=pid,
                pricing_type=p_type,
                price=p_price,
                unit_name=p_unit,
                unit_category=category,
                unit_value=unit_value,
            ))
    return ids


def _collect_voices(model_name: str, voice_names: list[str]) -> list[UUID]:
    """Collect voice resources and return their IDs."""
    ids: list[UUID] = []
    for vname in voice_names:
        vid = sid(f"voice/{vname}")
        ids.append(vid)
        if vname not in _voice_names_seen:
            _voice_names_seen.add(vname)
            dynamic_voices.append(dict(id=vid, voice=vname))
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

    # Modalities (static lookup)
    _mod_ids = [_MODALITY_LOOKUP[n] for n in _m.get("modalities", []) if n in _MODALITY_LOOKUP]

    # Reasoning levels (static lookup)
    _reason_ids = [_REASONING_LOOKUP[n] for n in _m.get("reasoning_levels", []) if n in _REASONING_LOOKUP]

    # Qualities (static lookup)
    _quality_ids = [_QUALITY_LOOKUP[n] for n in _m.get("qualities", []) if n in _QUALITY_LOOKUP]

    # Temperature levels (static lookup by range)
    _temp_ids: list[UUID] = []
    _temp_cfg = _m.get("temperature")
    if _temp_cfg and isinstance(_temp_cfg, dict):
        _temp_ids = _lookup_temperatures(_temp_cfg)

    # Pricing (dynamic — generates resources)
    _price_ids: list[UUID] = []
    _pricing_cfg = _m.get("pricing")
    if _pricing_cfg and isinstance(_pricing_cfg, list):
        _price_ids = _generate_pricing(_name, _pricing_cfg)

    # Voices (dynamic — generates resources)
    _voice_ids: list[UUID] = []
    _voices_cfg = _m.get("voices")
    if _voices_cfg and isinstance(_voices_cfg, list):
        _voice_ids = _collect_voices(_name, _voices_cfg)

    # Flags
    _flag_ids = [_MODEL_ACTIVE_FLAG_ID] if _MODEL_ACTIVE_FLAG_ID else []

    models.append(dict(
        id=sid(f"model/{_name}"),
        resource_id=sid(f"model-resource/{_name}"),
        name=_name,
        value=_name,
        description=_m.get("description", _name),
        provider_ids=[_prov_id],
        flag_ids=_flag_ids,
        modality_ids=_mod_ids,
        pricing_ids=_price_ids,
        reasoning_level_ids=_reason_ids,
        temperature_level_ids=_temp_ids,
        voice_ids=_voice_ids,
        quality_ids=_quality_ids,
    ))

# ---------------------------------------------------------------------------
# Role → model ID mapping (for agents)
# ---------------------------------------------------------------------------

ROLE_MODEL_IDS: dict[str, UUID] = {}
for _role, _model_name in _roles.items():
    if _model_name:  # skip unconfigured roles (empty string)
        ROLE_MODEL_IDS[_role] = sid(f"model-resource/{_model_name}")

DEFAULT_TEXT_MODEL: UUID | None = ROLE_MODEL_IDS.get("text")
