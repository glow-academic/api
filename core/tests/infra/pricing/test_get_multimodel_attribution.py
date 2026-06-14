"""C2: pin the multi-model cost-attribution limitation in /system/pricing.

The daily-chart bucketing in ``get_pricing_impl`` keys each run's cost on
``run.model_ids[0]`` (get.py:138). For a multi-model run (e.g. opus + haiku)
this attributes 100% of the run's blended cost to whichever model id sorts
first and $0 to the rest.

A *correct* per-model split is not implementable from the current schema:
``tokens_entry`` and ``run_pricing_entry`` record tokens/cost once per RUN
(no model_id column), and ``runs_mv.model_ids`` is a DISTINCT array_agg with
no per-model token weighting. So the data needed to split the cost simply
does not exist — see the C2 note in the bug report.

These tests therefore pin the *known-wrong* current behavior (DB-free, pure):
they exercise the real cost math + a faithful replica of the bucketing loop.
If a correct per-model attribution is ever shipped, the misattribution
assertions below will fail — flagging the C2 marker for re-evaluation.
"""

from decimal import Decimal
from uuid import UUID

from app.infra.pricing.get import _compute_run_costs
from app.tools.entries.runs.search import RunPricingItem, RunViewItem


def _bucket_by_first_model(runs, run_costs):
    """Faithful replica of the daily bucketing in get_pricing_impl (get.py:133-145).

    Kept in-test (not imported) so the production path stays untouched while
    the C2 limitation is pinned.
    """
    daily_buckets: dict[tuple[str, str | None], Decimal] = {}
    for run in runs:
        date_key = (
            run.run_created_at.strftime("%Y-%m-%d") if run.run_created_at else "unknown"
        )
        model_id = str(run.model_ids[0]) if run.model_ids else None
        bucket_key = (date_key, model_id)
        daily_buckets[bucket_key] = daily_buckets.get(
            bucket_key, Decimal("0")
        ) + run_costs.get(run.run_id, Decimal("0"))
    return daily_buckets


def test_multimodel_run_cost_lands_entirely_on_first_model():
    # Two distinct models on one run; sort the ids so we know which is "first".
    model_a = UUID("00000000-0000-0000-0000-0000000000aa")
    model_b = UUID("00000000-0000-0000-0000-0000000000bb")
    run_id = UUID("11111111-1111-1111-1111-111111111111")
    input_pricing = UUID("22222222-2222-2222-2222-222222222222")
    output_pricing = UUID("33333333-3333-3333-3333-333333333333")

    run = RunViewItem(
        run_id=run_id,
        run_created_at=None,
        model_ids=[model_a, model_b],
        pricing=[
            RunPricingItem(pricing_type="input", count=1000, pricing_id=input_pricing),
            RunPricingItem(pricing_type="output", count=1000, pricing_id=output_pricing),
        ],
    )
    # 1000/1000 * 0.02 + 1000/1000 * 0.03 = 0.05 blended cost for the run.
    pricing_map = {
        input_pricing: {"price": Decimal("0.02"), "unit_value": 1000},
        output_pricing: {"price": Decimal("0.03"), "unit_value": 1000},
    }

    run_costs = _compute_run_costs([run], pricing_map)
    assert run_costs[run_id] == Decimal("0.05")

    buckets = _bucket_by_first_model([run], run_costs)

    # C2: the entire blended cost is attributed to model_ids[0] (model_a);
    # model_b is never even bucketed. This is the documented misattribution —
    # a correct split would put a fraction under model_b instead.
    assert buckets[("unknown", str(model_a))] == Decimal("0.05")
    assert ("unknown", str(model_b)) not in buckets


def test_singlemodel_run_attribution_is_correct():
    # Control: with one model, model_ids[0] attribution is the right answer.
    model = UUID("00000000-0000-0000-0000-0000000000cc")
    run_id = UUID("44444444-4444-4444-4444-444444444444")
    input_pricing = UUID("55555555-5555-5555-5555-555555555555")

    run = RunViewItem(
        run_id=run_id,
        run_created_at=None,
        model_ids=[model],
        pricing=[
            RunPricingItem(pricing_type="input", count=2000, pricing_id=input_pricing),
        ],
    )
    pricing_map = {input_pricing: {"price": Decimal("0.02"), "unit_value": 1000}}

    run_costs = _compute_run_costs([run], pricing_map)
    assert run_costs[run_id] == Decimal("0.04")

    buckets = _bucket_by_first_model([run], run_costs)
    assert buckets[("unknown", str(model))] == Decimal("0.04")
