"""University pricing-resource seed definitions.

Each entry maps directly to ``create_pricing`` and produces a
``pricing_resource`` row with a NON-ZERO ``price``. The default
``glow-deploy.yaml`` ships every model with ``price: 0``, so the only
``pricing_resource`` rows the platform seeds are zero-priced — which makes
every spend figure on the Pricing dashboards (daily-cost,
model-breakdown, group-overview) render ``$0.00`` even though runs and
token counts exist.

Seeding realistic input/output rates here gives the analytics seed
(``database/seeds/attempts_analytics.py``) priced rows to attach to its
``run_pricing_entry`` rows. That seed prefers the highest-priced pricing
of each type when wiring run costs, so these win over the $0 config rows.

Cost math (mirrors app/infra/system/groups.py):
    run_cost = (count / unit_value) * price
With ``unit_value = 1000`` (per-1k tokens) and the analytics seed's token
envelopes, e.g. 1500 input @ $0.02/1k + 2000 output @ $0.03/1k = $0.09 —
the exact shape documented in PR #163.

IDs are deterministic via ``sid("uni/pricing/...")`` so re-runs are
idempotent at the DB layer.
"""

from database.seeds.ids import sid

# Per-1,000-token unit: cost = count / 1000 * price.
_UNIT_NAME = "thousand_text"
_UNIT_CATEGORY = "tokens"
_UNIT_VALUE = 1000

# (slug, pricing_type, price-per-1k-tokens)
_PRICING: list[tuple[str, str, float]] = [
    ("input", "input", 0.02),
    ("output", "output", 0.03),
]

# Exported IDs keyed by pricing_type so other modules / tests can reference them.
UNI_PRICING_IDS = {
    p_type: sid(f"uni/pricing/{slug}") for slug, p_type, _price in _PRICING
}

# ---------------------------------------------------------------------------
# Pricing definitions (creates) — dicts → create_pricing(**dict)
# ---------------------------------------------------------------------------

pricing = [
    dict(
        id=sid(f"uni/pricing/{slug}"),
        pricing_type=p_type,
        price=price,
        unit_name=_UNIT_NAME,
        unit_category=_UNIT_CATEGORY,
        unit_value=_UNIT_VALUE,
    )
    for slug, p_type, price in _PRICING
]
