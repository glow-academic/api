from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.infra.dashboard.permissions import (
    _build_trend_analysis,
    _status_from_thresholds,
    _thresholds,
    _weighted_average,
    build_dashboard_bundle,
    compute_footer_metrics,
    compute_footer_metrics_v2,
    compute_header_metrics,
    compute_header_metrics_v2,
    compute_primary_metrics,
    compute_primary_metrics_v2,
    compute_secondary_metrics,
    compute_secondary_metrics_v2,
)


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def test_dashboard_permission_helpers_cover_core_threshold_logic():
    assert (
        _weighted_average([(80, 2), (100, 1), (None, 5), (90, 0)]) == 86.66666666666667
    )
    assert _weighted_average([(None, 1), (90, 0)]) is None

    assert _build_trend_analysis([50.0, 60.0]) == "Up 20.0% vs period start"
    assert (
        _build_trend_analysis([20.0, 10.0], lower_is_better=True)
        == "Up 50.0% vs period start"
    )
    assert _build_trend_analysis([0.0, 3.0]) == "Up 3.00 vs period start"
    assert _build_trend_analysis([10.0]) == "Insufficient data"

    assert _status_from_thresholds(90, 85, 70) == "success"
    assert _status_from_thresholds(80, 85, 70) == "warning"
    assert _status_from_thresholds(60, 85, 70) == "danger"
    assert _status_from_thresholds(3, 2, 5, lower_is_better=True) == "warning"
    assert _thresholds(None) == (85, 80, 70)
    assert _thresholds({"success": 90, "warning": 75, "danger": 55}) == (90, 75, 55)


def test_compute_header_metrics_v2_returns_neutral_empty_metrics():
    metrics = compute_header_metrics_v2(
        [], thresholds={"success": 90, "warning": 75, "danger": 60}
    )

    assert metrics.average_score.status == "neutral"
    assert metrics.total_attempts.current_value == 0
    assert metrics.first_attempt_pass_rate.trend_analysis == "Insufficient data"


def test_compute_header_metrics_v2_computes_real_trends_and_statuses():
    sim_id = str(uuid4())
    rows = [
        _ns(
            attempt_date=date(2026, 1, 1),
            attempt_id=uuid4(),
            simulation_id=sim_id,
            completed=True,
            grade_percent=80,
            profile_id=uuid4(),
            chat_id=uuid4(),
            passed=True,
            num_messages_total=6,
            avg_response_sec=8,
            time_taken_seconds=1800,
        ),
        _ns(
            attempt_date=date(2026, 1, 1),
            attempt_id=uuid4(),
            simulation_id=sim_id,
            completed=False,
            grade_percent=60,
            profile_id=uuid4(),
            chat_id=uuid4(),
            passed=False,
            num_messages_total=4,
            avg_response_sec=12,
            time_taken_seconds=3600,
        ),
        _ns(
            attempt_date=date(2026, 1, 2),
            attempt_id=uuid4(),
            simulation_id=sim_id,
            completed=True,
            grade_percent=95,
            profile_id=uuid4(),
            chat_id=uuid4(),
            passed=True,
            num_messages_total=7,
            avg_response_sec=5,
            time_taken_seconds=1200,
        ),
    ]

    metrics = compute_header_metrics_v2(
        rows,
        simulation_scenario_counts={sim_id: 1},
        thresholds={"success": 90, "warning": 75, "danger": 60},
    )

    assert metrics.average_score.has_data is True
    assert metrics.average_score.status == "warning"
    assert metrics.completion_percentage.current_value == 66.67
    assert metrics.highest_score.current_value == 95.0
    assert metrics.persona_response_times.status == "success"
    assert metrics.total_attempts.current_value == 3
    assert len(metrics.average_score.trend_data) == 2


def test_compute_primary_metrics_v2_builds_heatmap_trend_and_skill_packages():
    rubric_id = uuid4()
    chat_a = uuid4()
    chat_b = uuid4()
    chat_c = uuid4()
    group_a = str(uuid4())
    group_b = str(uuid4())

    rubric_facts = [
        _ns(
            rubric_id=rubric_id,
            chat_id=chat_a,
            standard_group_id=group_a,
            score_percent=90,
            attempt_date=date(2026, 1, 1),
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=chat_a,
            standard_group_id=group_b,
            score_percent=60,
            attempt_date=date(2026, 1, 1),
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=chat_b,
            standard_group_id=group_a,
            score_percent=80,
            attempt_date=date(2026, 1, 2),
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=chat_b,
            standard_group_id=group_b,
            score_percent=50,
            attempt_date=date(2026, 1, 2),
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=chat_c,
            standard_group_id=group_a,
            score_percent=70,
            attempt_date=date(2026, 1, 3),
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=chat_c,
            standard_group_id=group_b,
            score_percent=40,
            attempt_date=date(2026, 1, 3),
        ),
    ]

    metrics = compute_primary_metrics_v2(
        rubric_facts,
        standard_group_name_map={group_a: "Accuracy", group_b: "Judgment"},
        thresholds={"success": 85, "warning": 70, "danger": 50},
    )

    assert metrics.rubric_heatmap.status in {"warning", "danger", "success"}
    assert metrics.rubric_heatmap.matrices
    assert metrics.rubric_trend.trend_data
    assert metrics.skill_performance.packages
    assert metrics.skill_performance.valid_rubric_ids == [str(rubric_id)]


def test_compute_secondary_metrics_v2_builds_persona_cohort_and_attempt_views():
    sim_id = uuid4()
    persona_id = uuid4()
    cohort_id = uuid4()
    profile_id = uuid4()
    simulation_facts = [
        _ns(
            simulation_id=sim_id,
            persona_id=persona_id,
            cohort_id=cohort_id,
            profile_id=profile_id,
            grade_percent=92,
            completed=True,
            passed=True,
            attempt_date=date(2026, 1, 1),
            attempt_number=1,
            time_taken_seconds=1200,
        ),
        _ns(
            simulation_id=sim_id,
            persona_id=persona_id,
            cohort_id=cohort_id,
            profile_id=profile_id,
            grade_percent=96,
            completed=True,
            passed=True,
            attempt_date=date(2026, 1, 2),
            attempt_number=2,
            time_taken_seconds=900,
        ),
    ]

    metrics = compute_secondary_metrics_v2(
        simulation_facts,
        persona_name_map={str(persona_id): "Coach"},
        cohort_name_map={str(cohort_id): "Alpha"},
        thresholds={"success": 90, "warning": 75, "danger": 60},
    )

    assert metrics.persona_performance.chart_data[0].name == "Coach"
    assert metrics.cohort_performance.cohort_data[0].name == "Alpha"
    assert metrics.attempt_improvement.chart_data[0].attempt == "Attempt 1"
    assert metrics.attempt_improvement.status == "success"


def test_compute_footer_metrics_v2_builds_scenario_composition_and_stats():
    scenario_id = uuid4()
    simulation_id = uuid4()
    persona_id = uuid4()
    document_id = uuid4()
    pf_scenario = uuid4()
    pf_persona = uuid4()
    pf_document = uuid4()
    parameter_regular = uuid4()
    parameter_persona = uuid4()
    field_regular = uuid4()
    field_persona = uuid4()

    scenario_facts = [
        _ns(
            scenario_id=scenario_id,
            simulation_id=simulation_id,
            completed=True,
            passed=True,
            grade_percent=90,
            attempt_date=date(2026, 1, 1),
            document_ids=[document_id],
        ),
        _ns(
            scenario_id=scenario_id,
            simulation_id=simulation_id,
            completed=True,
            passed=False,
            grade_percent=50,
            attempt_date=date(2026, 1, 2),
            document_ids=[document_id],
        ),
    ]
    scenarios = [
        _ns(
            scenario_id=scenario_id,
            persona_ids=[persona_id],
            parameter_field_ids=[pf_scenario],
        )
    ]
    personas = [_ns(persona_id=persona_id, parameter_field_ids=[pf_persona])]
    documents = [_ns(document_id=document_id, parameter_field_ids=[pf_document])]
    parameter_fields = [
        _ns(id=pf_scenario, parameter_id=parameter_regular, field_id=field_regular),
        _ns(id=pf_persona, parameter_id=parameter_persona, field_id=field_persona),
        _ns(id=pf_document, parameter_id=parameter_persona, field_id=field_persona),
    ]
    parameters = [
        _ns(
            parameter_id=parameter_regular,
            document_parameter=False,
            persona_parameter=False,
        ),
        _ns(
            parameter_id=parameter_persona,
            document_parameter=True,
            persona_parameter=False,
        ),
    ]
    fields = [
        _ns(field_id=field_regular, name="Difficulty"),
        _ns(field_id=field_persona, name="Tone"),
    ]

    metrics = compute_footer_metrics_v2(
        scenario_facts,
        scenarios=scenarios,
        personas=personas,
        documents=documents,
        parameter_fields=parameter_fields,
        parameters=parameters,
        fields=fields,
        simulation_name_map={str(simulation_id): "Simulation A"},
        scenario_name_map={str(scenario_id): "Scenario A"},
        thresholds={"success": 85, "warning": 70, "danger": 55},
    )

    assert (
        metrics.scenario_simulation_performance.simulation_facts[0].simulation_name
        == "Simulation A"
    )
    assert metrics.scenario_composition.scenario_summaries[0].name == "Scenario A"
    assert metrics.scenario_performance.valid_parameter_ids == [str(parameter_regular)]
    assert metrics.scenario_stats.valid_numeric_parameter_ids == [
        str(parameter_persona)
    ]


def test_build_dashboard_bundle_returns_empty_sections_without_data():
    bundle = build_dashboard_bundle(
        attempts=[],
        daily_rows=[],
        chat_rows=[],
        profile_rows=[],
    )

    assert bundle.header_metrics.average_score.status == "neutral"
    assert bundle.primary_metrics.rubric_heatmap.status == "neutral"
    assert bundle.secondary_metrics.persona_performance.status == "neutral"
    assert bundle.footer_metrics.scenario_performance.status == "neutral"


def test_compute_header_metrics_legacy_builds_all_metric_families():
    sim_id = uuid4()
    profile_id = uuid4()
    attempt_rows = [
        _ns(
            attempt_created_at=_ns(date=lambda: date(2026, 1, 1)),
            score_percent=82,
            profile_id=profile_id,
            simulation_id=sim_id,
            total_time_seconds=1800,
            has_passed=True,
        ),
        _ns(
            attempt_created_at=_ns(date=lambda: date(2026, 1, 2)),
            score_percent=94,
            profile_id=profile_id,
            simulation_id=sim_id,
            total_time_seconds=1200,
            has_passed=True,
        ),
    ]
    daily_rows = [
        _ns(
            date_key=date(2026, 1, 1),
            attempt_count=1,
            completed_count=1,
            passed_count=1,
            total_time_seconds=1800,
            avg_score=82,
            avg_messages=5,
        ),
        _ns(
            date_key=date(2026, 1, 2),
            attempt_count=1,
            completed_count=1,
            passed_count=1,
            total_time_seconds=1200,
            avg_score=94,
            avg_messages=7,
        ),
    ]
    chat_rows = [
        _ns(
            attempt_id=uuid4(),
            attempt_created_at=_ns(date=lambda: date(2026, 1, 1)),
            chat_created_at=_ns(date=lambda: date(2026, 1, 1)),
            simulation_id=sim_id,
            completed=True,
            grade_percent=82,
            message_time_taken_seconds=[5, 7],
            time_taken=900,
        ),
        _ns(
            attempt_id=uuid4(),
            attempt_created_at=_ns(date=lambda: date(2026, 1, 2)),
            chat_created_at=_ns(date=lambda: date(2026, 1, 2)),
            simulation_id=sim_id,
            completed=True,
            grade_percent=94,
            message_time_taken_seconds=[3, 4],
            time_taken=600,
        ),
    ]
    profile_rows = [
        _ns(avg_persona_response_sec=6, total_attempts=2),
        _ns(avg_persona_response_sec=4, total_attempts=1),
    ]
    first_attempt_rows = [
        _ns(
            attempt_created_at=_ns(date=lambda: date(2026, 1, 1)),
            rubric_pass_points=7,
            rubric_total_points=10,
            grade_percent=82,
        ),
        _ns(
            attempt_created_at=_ns(date=lambda: date(2026, 1, 2)),
            rubric_pass_points=7,
            rubric_total_points=10,
            grade_percent=94,
        ),
    ]

    metrics = compute_header_metrics(
        attempts=attempt_rows,
        daily_rows=daily_rows,
        chat_rows=chat_rows,
        profile_rows=profile_rows,
        first_attempt_rows=first_attempt_rows,
        simulation_scenario_counts={str(sim_id): 1},
        thresholds={"success": 90, "warning": 75, "danger": 60},
    )

    assert metrics.average_score.current_value == 88.0
    assert metrics.completion_percentage.current_value == 100.0
    assert metrics.first_attempt_pass_rate.current_value == 100.0
    assert metrics.highest_score.current_value == 94.0
    assert metrics.messages_per_session.current_value == 6.0
    assert metrics.persona_response_times.current_value == 5.33
    assert metrics.total_attempts.current_value == 2


def test_compute_primary_metrics_legacy_builds_growth_persona_and_heatmap():
    sim_id = uuid4()
    persona_id = uuid4()
    rubric_id = uuid4()
    group_a = uuid4()
    group_b = uuid4()
    daily_rows = [
        _ns(
            date_key=date(2026, 1, 1),
            attempt_count=2,
            completed_count=1,
            passed_count=1,
            total_time_seconds=2400,
            avg_score=70,
        ),
        _ns(
            date_key=date(2026, 1, 2),
            attempt_count=2,
            completed_count=2,
            passed_count=2,
            total_time_seconds=1800,
            avg_score=88,
        ),
    ]
    chat_rows = [
        _ns(
            persona_id=persona_id,
            grade_percent=70,
            simulation_id=sim_id,
            chat_created_at=_ns(date=lambda: date(2026, 1, 1)),
        ),
        _ns(
            persona_id=persona_id,
            grade_percent=88,
            simulation_id=sim_id,
            chat_created_at=_ns(date=lambda: date(2026, 1, 2)),
        ),
    ]
    rubric_group_scores = [
        _ns(
            rubric_id=rubric_id,
            chat_id=uuid4(),
            standard_group_id=group_a,
            score_percent=90,
            group_name="Accuracy",
            group_short_name="ACC",
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=uuid4(),
            standard_group_id=group_b,
            score_percent=60,
            group_name="Judgment",
            group_short_name="JDG",
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=uuid4(),
            standard_group_id=group_a,
            score_percent=80,
            group_name="Accuracy",
            group_short_name="ACC",
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=uuid4(),
            standard_group_id=group_b,
            score_percent=50,
            group_name="Judgment",
            group_short_name="JDG",
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=uuid4(),
            standard_group_id=group_a,
            score_percent=85,
            group_name="Accuracy",
            group_short_name="ACC",
        ),
        _ns(
            rubric_id=rubric_id,
            chat_id=uuid4(),
            standard_group_id=group_b,
            score_percent=65,
            group_name="Judgment",
            group_short_name="JDG",
        ),
    ]

    metrics = compute_primary_metrics(
        attempts=[],
        daily_rows=daily_rows,
        chat_rows=chat_rows,
        profile_rows=[],
        rubric_group_scores=rubric_group_scores,
        persona_name_map={str(persona_id): "Coach"},
        thresholds={"success": 85, "warning": 70, "danger": 55},
    )

    assert metrics.rubric_heatmap.matrices
    assert metrics.rubric_trend.status == "neutral"
    assert metrics.skill_performance.status in {
        "success",
        "warning",
        "danger",
        "neutral",
    }
    assert metrics.rubric_heatmap.valid_rubric_ids == [str(rubric_id)]


def test_compute_secondary_metrics_legacy_builds_cohort_attempt_and_skill_views():
    sim_id = uuid4()
    cohort_id = uuid4()
    profile_id = uuid4()
    rubric_id = uuid4()
    group_id = uuid4()
    attempt_a = _ns(
        profile_id=profile_id,
        attempt_created_at=datetime(2026, 1, 1, 9, 0, 0),
        simulation_id=sim_id,
        score_percent=75,
        total_time_seconds=1800,
        has_passed=False,
    )
    attempt_b = _ns(
        profile_id=profile_id,
        attempt_created_at=datetime(2026, 1, 2, 9, 0, 0),
        simulation_id=sim_id,
        score_percent=92,
        total_time_seconds=1200,
        has_passed=True,
    )
    daily_rows = [
        _ns(
            date_key=date(2026, 1, 1),
            simulation_id=sim_id,
            cohort_id=cohort_id,
            attempt_count=1,
            completed_count=1,
            passed_count=0,
            avg_score=75,
            unique_profiles=1,
        ),
        _ns(
            date_key=date(2026, 1, 2),
            simulation_id=sim_id,
            cohort_id=cohort_id,
            attempt_count=1,
            completed_count=1,
            passed_count=1,
            avg_score=92,
            unique_profiles=1,
        ),
    ]
    rubric_group_scores = [
        _ns(
            rubric_id=rubric_id,
            standard_group_id=group_id,
            score_percent=88,
            group_name="Accuracy",
            group_short_name="ACC",
            chat_id=uuid4(),
        )
    ]

    metrics = compute_secondary_metrics(
        attempts=[attempt_a, attempt_b],
        daily_rows=daily_rows,
        chat_rows=[],
        profile_rows=[],
        cohort_name_map={str(cohort_id): "Alpha"},
        rubric_group_scores=rubric_group_scores,
        thresholds={"success": 85, "warning": 70, "danger": 55},
    )

    assert metrics.cohort_performance.cohort_data[0].name == "Alpha"
    assert metrics.attempt_improvement.chart_data[0].attempt == "Attempt 1"
    assert metrics.persona_performance.status == "neutral"


def test_compute_footer_metrics_legacy_builds_composition_and_numeric_stats():
    sim_id = uuid4()
    scenario_id = uuid4()
    scenario_two = uuid4()
    pf_regular = uuid4()
    pf_numeric = uuid4()
    param_regular = uuid4()
    param_numeric = uuid4()
    field_regular = uuid4()
    field_numeric = uuid4()
    chat_rows = [
        _ns(
            simulation_id=sim_id,
            scenario_id=scenario_id,
            completed=True,
            passed=True,
            grade_percent=90,
            parameter_field_ids=[pf_regular],
            persona_parameter_field_ids=[pf_numeric],
            document_parameter_field_ids=[],
            parameter_ids=[param_regular],
            field_ids=[field_regular],
            attempt_created_at=_ns(date=lambda: date(2026, 1, 1)),
        ),
        _ns(
            simulation_id=sim_id,
            scenario_id=scenario_id,
            completed=True,
            passed=False,
            grade_percent=55,
            parameter_field_ids=[pf_regular],
            persona_parameter_field_ids=[pf_numeric],
            document_parameter_field_ids=[],
            parameter_ids=[param_regular],
            field_ids=[field_regular],
            attempt_created_at=_ns(date=lambda: date(2026, 1, 2)),
        ),
        _ns(
            simulation_id=sim_id,
            scenario_id=scenario_two,
            completed=True,
            passed=True,
            grade_percent=80,
            parameter_field_ids=[pf_regular],
            persona_parameter_field_ids=[],
            document_parameter_field_ids=[],
            parameter_ids=[param_regular],
            field_ids=[field_regular],
            attempt_created_at=_ns(date=lambda: date(2026, 1, 2)),
        ),
    ]
    parameter_fields = [
        _ns(id=pf_regular, parameter_id=param_regular, field_id=field_regular),
        _ns(id=pf_numeric, parameter_id=param_numeric, field_id=field_numeric),
    ]
    parameters = [
        _ns(
            parameter_id=param_regular,
            document_parameter=False,
            persona_parameter=False,
        ),
        _ns(
            parameter_id=param_numeric, document_parameter=True, persona_parameter=False
        ),
    ]
    fields = [
        _ns(field_id=field_regular, name="Difficulty"),
        _ns(field_id=field_numeric, name="Tone"),
    ]

    metrics = compute_footer_metrics(
        attempts=[],
        daily_rows=[],
        chat_rows=chat_rows,
        profile_rows=[],
        parameter_fields=parameter_fields,
        parameters=parameters,
        fields=fields,
        simulation_name_map={str(sim_id): "Simulation A"},
        scenario_name_map={
            str(scenario_id): "Scenario A",
            str(scenario_two): "Scenario B",
        },
        thresholds={"success": 85, "warning": 70, "danger": 55},
    )

    assert (
        metrics.scenario_simulation_performance.simulation_facts[0].simulation_name
        == "Simulation A"
    )
    assert {
        summary.name for summary in metrics.scenario_composition.scenario_summaries
    } == {"Scenario A", "Scenario B"}
    assert metrics.scenario_performance.valid_parameter_ids == [str(param_regular)]
    assert metrics.scenario_stats.valid_numeric_parameter_ids == [str(param_numeric)]
