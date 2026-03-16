"""Types for dashboard artifact get bundle."""

from datetime import date as date_type
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.v5_types import (
    FilterOption,
    HistoryResponse,
)

# ============================================================================
# Request
# ============================================================================


class DashboardRequest(BaseModel):
    """Request for getting dashboard data (get.py scope only)."""

    # Global filters
    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    roles: list[str] | None = Field(None, description="Roles to filter by")
    simulation_filters: list[str] | None = Field(None, description="Simulation filter strings")
    actor_profile_id: UUID | None = Field(None, description="Acting user profile ID")
    target_profile_id: UUID | None = Field(None, description="Target profile ID to scope data")
    page_limit: int = Field(default=50, ge=1, le=200, description="Max items per page")
    page_offset: int = Field(default=0, ge=0, description="Pagination offset")

    # Section pickers (canonical — shared across charts in each section)
    rubric_ids: list[UUID] | None = Field(None, description="Rubric IDs for section picker")
    rubric_search: str | None = Field(None, description="Search string for rubrics")
    simulation_picker_ids: list[UUID] | None = Field(None, description="Simulation picker IDs")
    simulation_picker_search: str | None = Field(None, description="Search string for simulations")
    parameter_ids: list[UUID] | None = Field(None, description="Parameter IDs for section picker")
    parameter_search: str | None = Field(None, description="Search string for parameters")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs for section picker")
    scenario_search: str | None = Field(None, description="Search string for scenarios")

    # History section (attempt list) — kept for backward compat, use /list endpoint
    history_practice: bool = Field(False, description="Filter to practice attempts only")
    history_scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs for history filter")
    history_infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    history_show_archived: bool = Field(False, description="Include archived attempts")
    history_sort_by: str | None = Field("date", description="History sort field")
    history_sort_order: str | None = Field("desc", description="History sort direction")
    history_page: int = Field(0, description="History pagination page number")
    history_page_size: int = Field(20, description="History items per page")
    history_simulation_search: str | None = Field(None, description="Search string for history simulations")
    history_scenario_search: str | None = Field(None, description="Search string for history scenarios")
    history_profile_search: str | None = Field(None, description="Search string for history profiles")


class ListDashboardRequest(BaseModel):
    """Request for dashboard history list endpoint (paginated attempt history)."""

    # Global filters
    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    target_profile_id: UUID | None = Field(None, description="Target profile ID to scope data")

    # History-specific
    practice: bool = Field(False, description="Filter to practice attempts only")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    show_archived: bool = Field(False, description="Include archived attempts")
    sort_by: str = Field("date", description="Sort field name")
    sort_order: str = Field("desc", description="Sort direction (asc or desc)")
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(20, description="Items per page")
    simulation_search: str | None = Field(None, description="Search string for simulations")
    scenario_search: str | None = Field(None, description="Search string for scenarios")
    profile_search: str | None = Field(None, description="Search string for profiles")


# ============================================================================
# Target client bundle response shape
# ============================================================================


class DashboardTrendPoint(BaseModel):
    date: date_type | str | None = Field(
        None, description="Date of the trend data point"
    )
    value: float | None = Field(None, description="Metric value at this point")
    count: int | None = Field(None, description="Number of observations")


class DashboardHeaderMetric(BaseModel):
    current_value: float | int | None = Field(None, description="Current metric value")
    trend_data: list[DashboardTrendPoint] = Field(default_factory=list, description="Time-series trend data points")
    has_data: bool = Field(False, description="Whether metric has any data")
    trend_analysis: str | None = Field(None, description="Textual trend analysis summary")
    status: str = Field("neutral", description="Metric status indicator")


class DashboardHeaderMetrics(BaseModel):
    average_score: DashboardHeaderMetric = Field(default_factory=DashboardHeaderMetric, description="Average score metric")
    completion_percentage: DashboardHeaderMetric = Field(
        default_factory=DashboardHeaderMetric, description="Completion percentage metric"
    )
    first_attempt_pass_rate: DashboardHeaderMetric = Field(
        default_factory=DashboardHeaderMetric, description="First attempt pass rate metric"
    )
    highest_score: DashboardHeaderMetric = Field(default_factory=DashboardHeaderMetric, description="Highest score metric")
    messages_per_session: DashboardHeaderMetric = Field(
        default_factory=DashboardHeaderMetric, description="Messages per session metric"
    )
    persona_response_times: DashboardHeaderMetric = Field(
        default_factory=DashboardHeaderMetric, description="Persona response times metric"
    )
    session_efficiency: DashboardHeaderMetric = Field(
        default_factory=DashboardHeaderMetric, description="Session efficiency metric"
    )
    stagnation_rate: DashboardHeaderMetric = Field(
        default_factory=DashboardHeaderMetric, description="Stagnation rate metric"
    )
    time_spent: DashboardHeaderMetric = Field(default_factory=DashboardHeaderMetric, description="Time spent metric")
    total_attempts: DashboardHeaderMetric = Field(default_factory=DashboardHeaderMetric, description="Total attempts metric")


class GrowthChartPoint(BaseModel):
    date: str | None = Field(None, description="Date of the growth data point")
    average_score: float | None = Field(None, description="Average score at this point")
    completion_rate: float | None = Field(None, description="Completion rate at this point")
    first_attempt_pass_rate: float | None = Field(None, description="First attempt pass rate")
    session_efficiency: float | None = Field(None, description="Session efficiency value")
    stagnation_rate: float | None = Field(None, description="Stagnation rate value")


class GrowthAvailableMetric(BaseModel):
    id: str | None = Field(None, description="Metric identifier")
    name: str | None = Field(None, description="Display name of the metric")
    color: str | None = Field(None, description="Chart color for the metric")
    unit: str | None = Field(None, description="Unit of measurement")
    description: str | None = Field(None, description="Human-readable metric description")
    formatter_id: str | None = Field(None, description="Client-side formatter identifier")


class GrowthWindowAverage(BaseModel):
    n: int = Field(0, description="Window size for the moving average")
    last: float | None = Field(None, description="Most recent window average")
    prev: float | None = Field(None, description="Previous window average")


class GrowthWindowAverages(BaseModel):
    average_score: GrowthWindowAverage = Field(default_factory=GrowthWindowAverage, description="Average score window average")


class PrimaryGrowthData(BaseModel):
    chart_data: list[GrowthChartPoint] = Field(default_factory=list, description="Growth chart time-series data")
    available_metrics: list[GrowthAvailableMetric] = Field(default_factory=list, description="Metrics available for charting")
    window_averages: GrowthWindowAverages | None = Field(None, description="Moving window averages")
    status: str = Field("neutral", description="Section status indicator")


class PersonaTrendPoint(BaseModel):
    date: str | None = Field(None, description="Date of the trend point")
    score: float | None = Field(None, description="Score value at this point")
    timestamp: int | None = Field(None, description="Unix timestamp of the point")
    simulation_id: str | None = Field(None, description="Associated simulation ID")


class PersonaChartRow(BaseModel):
    name: str | None = Field(None, description="Persona display name")
    score: float | None = Field(None, description="Average score for persona")
    sessions: int | None = Field(None, description="Number of sessions")
    color: str | None = Field(None, description="Chart color for persona")
    trend_data: list[PersonaTrendPoint] = Field(default_factory=list, description="Trend data points for persona")
    simulation_ids: list[str] = Field(default_factory=list, description="Associated simulation IDs")
    status: str = Field("neutral", description="Row status indicator")


class PersonaColorJunction(BaseModel):
    persona_name: str | None = Field(None, description="Persona display name")
    color: str | None = Field(None, description="Assigned chart color")


class PrimaryPersonaPerformance(BaseModel):
    chart_data: list[PersonaChartRow] = Field(default_factory=list, description="Persona performance chart rows")
    valid_simulation_ids: list[str] = Field(default_factory=list, description="Valid simulation IDs in scope")
    persona_colors_junction: list[PersonaColorJunction] = Field(default_factory=list, description="Persona-to-color mappings")
    status: str = Field("neutral", description="Section status indicator")


class RubricHeatmapStandardGroup(BaseModel):
    id: str | None = Field(None, description="Standard group identifier")
    name: str | None = Field(None, description="Standard group name")
    short_name: str | None = Field(None, description="Abbreviated display name")
    rubric_id: str | None = Field(None, description="Parent rubric ID")


class RubricHeatmapCell(BaseModel):
    rubric_id: str | None = Field(None, description="Rubric ID for this cell")
    correlation: float | None = Field(None, description="Correlation coefficient")
    p_value: float | None = Field(None, description="Statistical p-value")
    color: str | None = Field(None, description="Cell display color")
    strength: str | None = Field(None, description="Correlation strength label")
    data_points: int | None = Field(None, description="Number of data points")


class RubricHeatmapMatrixRow(BaseModel):
    cells: list[RubricHeatmapCell] = Field(default_factory=list, description="Cells in this heatmap row")


class RubricHeatmapMatrix(BaseModel):
    rubric_id: str | None = Field(None, description="Rubric ID for this matrix")
    standard_groups: list[RubricHeatmapStandardGroup] = Field(default_factory=list, description="Standard groups as axes")
    matrix: list[RubricHeatmapMatrixRow] = Field(default_factory=list, description="Correlation matrix rows")
    insights: str | None = Field(None, description="Generated insights text")
    has_data: bool = Field(False, description="Whether matrix has data")


class PrimaryRubricHeatmap(BaseModel):
    matrices: list[RubricHeatmapMatrix] = Field(default_factory=list, description="Heatmap matrices per rubric")
    valid_rubric_ids: list[str] = Field(default_factory=list, description="Valid rubric IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class PrimaryRubricTrendPoint(BaseModel):
    date: str | None = Field(None, description="Date of the trend point")
    standard_group_id: str | None = Field(None, description="Standard group identifier")
    standard_group_name: str | None = Field(None, description="Standard group display name")
    avg_pct: float | None = Field(None, description="Average percentage score")


class PrimaryRubricTrend(BaseModel):
    trend_data: list[PrimaryRubricTrendPoint] = Field(default_factory=list, description="Rubric trend time-series data")
    valid_rubric_ids: list[str] = Field(default_factory=list, description="Valid rubric IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class DashboardPrimaryMetrics(BaseModel):
    rubric_heatmap: PrimaryRubricHeatmap = Field(default_factory=PrimaryRubricHeatmap, description="Rubric correlation heatmap data")
    rubric_trend: PrimaryRubricTrend = Field(default_factory=PrimaryRubricTrend, description="Rubric trend over time")
    skill_performance: "SecondarySkillPerformance" = Field(
        default_factory=lambda: SecondarySkillPerformance(), description="Skill performance radar data"
    )


class SecondaryCohortData(BaseModel):
    id: str | None = Field(None, description="Cohort identifier")
    name: str | None = Field(None, description="Cohort display name")
    pass_rate: float | None = Field(None, description="Cohort pass rate percentage")
    avg_percentage_score: float | None = Field(None, description="Average percentage score")
    total_students: int | None = Field(None, description="Total students in cohort")
    passed_students: int | None = Field(None, description="Number of students who passed")
    total_attempts: int | None = Field(None, description="Total number of attempts")
    passed_attempts: int | None = Field(None, description="Number of passing attempts")
    simulation_count: int | None = Field(None, description="Number of simulations attempted")
    required_simulations: int | None = Field(None, description="Number of required simulations")
    status: str = Field("neutral", description="Cohort status indicator")


class SecondaryCohortDaily(BaseModel):
    date: str | None = Field(None, description="Date of the daily aggregate")
    avg_score: float | None = Field(None, description="Average score for the day")
    cohort_id: str | None = Field(None, description="Associated cohort ID")


class SecondarySimulationFact(BaseModel):
    cohort_id: str | None = Field(None, description="Associated cohort ID")
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    pass_rate: float | None = Field(None, description="Pass rate for this simulation")
    avg_score: float | None = Field(None, description="Average score for this simulation")
    attempts: int | None = Field(None, description="Number of attempts")


class SecondaryDailyFact(BaseModel):
    date: str | None = Field(None, description="Date of the daily fact")
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    avg_score: float | None = Field(None, description="Average score for the day")


class SecondaryCohortPerformance(BaseModel):
    cohort_data: list[SecondaryCohortData] = Field(default_factory=list, description="Per-cohort aggregate data")
    daily_data: list[SecondaryCohortDaily] = Field(default_factory=list, description="Daily cohort aggregates")
    simulation_facts: list[SecondarySimulationFact] = Field(default_factory=list, description="Per-simulation cohort facts")
    daily_facts: list[SecondaryDailyFact] = Field(default_factory=list, description="Daily simulation facts")
    valid_simulation_ids: list[str] = Field(default_factory=list, description="Valid simulation IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class SecondaryAttemptImprovementChart(BaseModel):
    attempt: str | None = Field(None, description="Attempt number label")
    average_score: float | None = Field(None, description="Average score for this attempt")
    average_time: float | None = Field(None, description="Average time in minutes")
    pass_rate: float | None = Field(None, description="Pass rate for this attempt")


class SecondaryAttemptImprovementFact(BaseModel):
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    attempt_no: int | None = Field(None, description="Attempt number")
    avg_grade: float | None = Field(None, description="Average grade for this attempt")
    avg_minutes: float | None = Field(None, description="Average duration in minutes")
    pass_rate: float | None = Field(None, description="Pass rate for this attempt")


class SecondaryAttemptImprovement(BaseModel):
    chart_data: list[SecondaryAttemptImprovementChart] = Field(default_factory=list, description="Attempt improvement chart data")
    facts: list[SecondaryAttemptImprovementFact] = Field(default_factory=list, description="Per-simulation attempt facts")
    valid_simulation_ids: list[str] = Field(default_factory=list, description="Valid simulation IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class SecondaryRadarPoint(BaseModel):
    metric: str | None = Field(None, description="Metric name for radar axis")
    description: str | None = Field(None, description="Metric description")
    value: float | None = Field(None, description="Metric value")
    full_mark: float | None = Field(None, description="Maximum possible value")


class SecondaryGroupFact(BaseModel):
    group_id: str | None = Field(None, description="Standard group identifier")
    group_name: str | None = Field(None, description="Standard group name")
    group_description: str | None = Field(None, description="Standard group description")
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    score: float | None = Field(None, description="Raw score value")
    points: float | None = Field(None, description="Points earned")
    avg_pct: float | None = Field(None, description="Average percentage score")


class SecondarySkillPackage(BaseModel):
    rubric_id: str | None = Field(None, description="Rubric ID for this package")
    radar_data: list[SecondaryRadarPoint] = Field(default_factory=list, description="Radar chart data points")
    group_facts: list[SecondaryGroupFact] = Field(default_factory=list, description="Per-group performance facts")


class SecondarySkillPerformance(BaseModel):
    packages: list[SecondarySkillPackage] = Field(default_factory=list, description="Skill performance packages per rubric")
    valid_rubric_ids: list[str] = Field(default_factory=list, description="Valid rubric IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class DashboardSecondaryMetrics(BaseModel):
    persona_performance: PrimaryPersonaPerformance = Field(
        default_factory=PrimaryPersonaPerformance, description="Persona performance data"
    )
    cohort_performance: SecondaryCohortPerformance = Field(
        default_factory=SecondaryCohortPerformance, description="Cohort performance data"
    )
    attempt_improvement: SecondaryAttemptImprovement = Field(
        default_factory=SecondaryAttemptImprovement, description="Attempt improvement data"
    )


class FooterScenarioAttributeAttemptFact(BaseModel):
    parameter_id: str | None = Field(None, description="Parameter identifier")
    parameter_item_id: str | None = Field(None, description="Parameter item identifier")
    date: str | None = Field(None, description="Date of the attempt fact")
    timestamp: int | None = Field(None, description="Unix timestamp")
    avg_score: float | None = Field(None, description="Average score")
    attempts: int | None = Field(None, description="Number of attempts")
    passed_attempts: int | None = Field(None, description="Number of passing attempts")


class FooterScenarioAttributeScenarioFact(BaseModel):
    parameter_id: str | None = Field(None, description="Parameter identifier")
    parameter_item_id: str | None = Field(None, description="Parameter item identifier")
    scenario_id: str | None = Field(None, description="Associated scenario ID")


class FooterScenarioPerformance(BaseModel):
    attribute_attempt_facts: list[FooterScenarioAttributeAttemptFact] = Field(
        default_factory=list, description="Attribute-level attempt facts"
    )
    attribute_scenario_facts: list[FooterScenarioAttributeScenarioFact] = Field(
        default_factory=list, description="Attribute-level scenario facts"
    )
    valid_parameter_ids: list[str] = Field(default_factory=list, description="Valid parameter IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class FooterNumericAttemptFact(BaseModel):
    parameter_id: str | None = Field(None, description="Parameter identifier")
    level_label: str | None = Field(None, description="Numeric level label")
    level_value: float | None = Field(None, description="Numeric level value")
    score: float | None = Field(None, description="Score value")
    attempts: int | None = Field(None, description="Number of attempts")


class FooterNumericScenarioFact(BaseModel):
    parameter_id: str | None = Field(None, description="Parameter identifier")
    scenario_id: str | None = Field(None, description="Associated scenario ID")
    level_label: str | None = Field(None, description="Numeric level label")
    level_value: float | None = Field(None, description="Numeric level value")


class FooterScenarioStats(BaseModel):
    numeric_attempt_facts: list[FooterNumericAttemptFact] = Field(default_factory=list, description="Numeric parameter attempt facts")
    numeric_scenario_facts: list[FooterNumericScenarioFact] = Field(
        default_factory=list, description="Numeric parameter scenario facts"
    )
    valid_numeric_parameter_ids: list[str] = Field(default_factory=list, description="Valid numeric parameter IDs")
    status: str = Field("neutral", description="Section status indicator")


class FooterScenarioSimulationFact(BaseModel):
    scenario_id: str | None = Field(None, description="Associated scenario ID")
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    simulation_name: str | None = Field(None, description="Simulation display name")
    avg_score: float | None = Field(None, description="Average score")
    success_rate: float | None = Field(None, description="Success rate percentage")
    total_attempts: int | None = Field(None, description="Total number of attempts")
    completed_attempts: int | None = Field(None, description="Number of completed attempts")


class FooterScenarioSimulationPerformance(BaseModel):
    simulation_facts: list[FooterScenarioSimulationFact] = Field(default_factory=list, description="Per-simulation scenario facts")
    valid_scenario_ids: list[str] = Field(default_factory=list, description="Valid scenario IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class FooterScenarioCompositionSummary(BaseModel):
    """Per-scenario summary with high/low chat split."""

    scenario_id: str | None = Field(None, description="Associated scenario ID")
    name: str | None = Field(None, description="Scenario display name")
    total_chats: int | None = Field(None, description="Total number of chats")
    high_count: int | None = Field(None, description="Count of high-scoring chats")
    low_count: int | None = Field(None, description="Count of low-scoring chats")
    high_avg_score: float | None = Field(None, description="Average score of high group")
    low_avg_score: float | None = Field(None, description="Average score of low group")


class FooterScenarioCompositionParamFact(BaseModel):
    """Parameter counts per (scenario, group) — group is 'high' or 'low'."""

    scenario_id: str | None = Field(None, description="Associated scenario ID")
    group: str | None = Field(None, description="Score group (high or low)")
    parameter_id: str | None = Field(None, description="Parameter identifier")
    parameter_item_id: str | None = Field(None, description="Parameter item identifier")
    chat_count: int | None = Field(None, description="Number of chats in this group")


class FooterScenarioComposition(BaseModel):
    scenario_summaries: list[FooterScenarioCompositionSummary] = Field(
        default_factory=list, description="Per-scenario composition summaries"
    )
    chat_parameter_facts: list[FooterScenarioCompositionParamFact] = Field(
        default_factory=list, description="Chat parameter composition facts"
    )
    valid_scenario_ids: list[str] = Field(default_factory=list, description="Valid scenario IDs in scope")
    status: str = Field("neutral", description="Section status indicator")


class DashboardFooterMetrics(BaseModel):
    scenario_performance: FooterScenarioPerformance = Field(
        default_factory=FooterScenarioPerformance, description="Scenario attribute performance data"
    )
    scenario_stats: FooterScenarioStats = Field(default_factory=FooterScenarioStats, description="Numeric scenario statistics")
    scenario_simulation_performance: FooterScenarioSimulationPerformance = Field(
        default_factory=FooterScenarioSimulationPerformance, description="Per-simulation scenario performance"
    )
    scenario_composition: FooterScenarioComposition = Field(
        default_factory=FooterScenarioComposition, description="Scenario composition analysis"
    )


class DashboardSimulationMeta(BaseModel):
    simulation_id: str | None = Field(None, description="Simulation identifier")
    name: str | None = Field(None, description="Simulation display name")
    description: str | None = Field(None, description="Simulation description")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    time_limit: int | None = Field(None, description="Time limit in seconds")


class DashboardScenarioMeta(BaseModel):
    scenario_id: str | None = Field(None, description="Scenario identifier")
    name: str | None = Field(None, description="Scenario display name")
    description: str | None = Field(None, description="Scenario description")


class DashboardRubricMeta(BaseModel):
    rubric_id: str | None = Field(None, description="Rubric identifier")
    name: str | None = Field(None, description="Rubric display name")
    description: str | None = Field(None, description="Rubric description")


class DashboardParameterMeta(BaseModel):
    parameter_id: str | None = Field(None, description="Parameter identifier")
    name: str | None = Field(None, description="Parameter display name")
    description: str | None = Field(None, description="Parameter description")
    numerical: bool | None = Field(None, description="Whether parameter is numerical")
    document_parameter: bool | None = Field(None, description="Whether parameter is document-type")
    persona_parameter: bool | None = Field(None, description="Whether parameter is persona-type")


class DashboardFieldMeta(BaseModel):
    field_id: str | None = Field(None, description="Field identifier")
    name: str | None = Field(None, description="Field display name")
    description: str | None = Field(None, description="Field description")
    parameter_id: str | None = Field(None, description="Parent parameter ID")
    parameter_name: str | None = Field(None, description="Parent parameter name")


class DashboardInsightObject(BaseModel):
    insight: str | None = Field(None, description="Generated insight text")


class DashboardInsights(BaseModel):
    rubric_trend: str | None = Field(None, description="Rubric trend insight text")
    rubric_heatmap: str | None = Field(None, description="Rubric heatmap insight text")
    attempt_improvement: str | None = Field(None, description="Attempt improvement insight text")
    skill_performance: str | None = Field(None, description="Skill performance insight text")
    scenario_performance: str | None = Field(None, description="Scenario performance insight text")
    scenario_stats: str | None = Field(None, description="Scenario stats insight text")
    scenario_simulation_performance: str | None = Field(None, description="Scenario simulation insight text")
    scenario_composition: str | None = Field(None, description="Scenario composition insight text")
    persona: dict[str, str | DashboardInsightObject | None] | None = Field(None, description="Per-persona insights")
    cohort: dict[str, str | DashboardInsightObject | None] | None = Field(None, description="Per-cohort insights")


class DashboardThresholds(BaseModel):
    success: float = Field(0, description="Success threshold value")
    warning: float = Field(0, description="Warning threshold value")
    danger: float = Field(0, description="Danger threshold value")


class DashboardBundleResponse(BaseModel):
    """Target dashboard bundle shape expected by dashboard client."""

    header_metrics: DashboardHeaderMetrics = Field(
        default_factory=DashboardHeaderMetrics, description="Header summary metrics"
    )
    primary_metrics: DashboardPrimaryMetrics = Field(
        default_factory=DashboardPrimaryMetrics, description="Primary dashboard metrics"
    )
    secondary_metrics: DashboardSecondaryMetrics = Field(
        default_factory=DashboardSecondaryMetrics, description="Secondary dashboard metrics"
    )
    footer_metrics: DashboardFooterMetrics = Field(
        default_factory=DashboardFooterMetrics, description="Footer dashboard metrics"
    )

    simulations: list[DashboardSimulationMeta] = Field(default_factory=list, description="Simulation metadata list")
    scenarios: list[DashboardScenarioMeta] = Field(default_factory=list, description="Scenario metadata list")
    rubrics: list[DashboardRubricMeta] = Field(default_factory=list, description="Rubric metadata list")
    parameters: list[DashboardParameterMeta] = Field(default_factory=list, description="Parameter metadata list")
    fields: list[DashboardFieldMeta] = Field(default_factory=list, description="Field metadata list")

    thresholds: DashboardThresholds | None = Field(None, description="Score thresholds configuration")
    insights: DashboardInsights | None = Field(None, description="Generated insights per section")

    simulation_options: list[FilterOption] = Field(default_factory=list, description="Simulation filter options")

    # Profile metadata (populated when target_profile_id is provided)
    profile_name: str | None = Field(None, description="Target profile display name")
    profile_emails: list[str] | None = Field(None, description="Target profile email addresses")
    profile_primary_email: str | None = Field(None, description="Target profile primary email")
    profile_role: str | None = Field(None, description="Target profile role")

    # Inline analytics facets
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")

    # Attempt history
    history: HistoryResponse | None = Field(None, description="Inline attempt history response")


class ListDashboardResponse(BaseModel):
    """Response for dashboard history list endpoint."""

    data: list = Field(default_factory=list, description="List of history row items")
    total_count: int = Field(0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")
    simulation_options: list[FilterOption] | None = Field(None, description="Simulation filter options")
    scenario_options: list[FilterOption] | None = Field(None, description="Scenario filter options")
    profile_options: list[FilterOption] | None = Field(None, description="Profile filter options")


# Resolve forward reference for DashboardPrimaryMetrics.skill_performance
DashboardPrimaryMetrics.model_rebuild()

# =============================================================================
# Export Types
# =============================================================================


class ExportDashboardApiResponse(BaseModel):
    """Response model for dashboard export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")
