"""artifact → route paths it unlocks."""

from __future__ import annotations

ARTIFACT_ROUTES: dict[str, frozenset[str]] = {
    "activity": frozenset({"/analytics/activity"}),
    "agent": frozenset(
        {
            "/intelligence/agents",
            "/intelligence/agents/[agentId]",
            "/intelligence/agents/new",
        }
    ),
    "attempt": frozenset(
        {
            "/attempt/[attemptId]",
            "/attempt/[attemptId]/[chatId]",
            "/home/[attemptId]",
            "/practice/[attemptId]",
        }
    ),
    "auth": frozenset({"/system/auth", "/system/auth/[authId]", "/system/auth/new"}),
    "benchmark": frozenset({"/benchmark"}),
    "chat": frozenset(
        {"/home/[attemptId]/[trainingId]", "/practice/[attemptId]/[trainingId]"}
    ),
    "cohort": frozenset(
        {"/training/cohorts", "/training/cohorts/[cohortId]", "/training/cohorts/new"}
    ),
    "dashboard": frozenset({"/analytics/dashboard"}),
    "department": frozenset(
        {
            "/system/departments",
            "/system/departments/[departmentId]",
            "/system/departments/new",
        }
    ),
    "document": frozenset(
        {
            "/management/documents",
            "/management/documents/[documentId]",
            "/management/documents/new",
        }
    ),
    "eval": frozenset({"/system/evals", "/system/evals/[evalId]", "/system/evals/new"}),
    "field": frozenset(
        {"/management/fields", "/management/fields/[fieldId]", "/management/fields/new"}
    ),
    "group": frozenset({"/analytics/pricing/[groupId]", "/group/[groupId]"}),
    "health": frozenset({"/health"}),
    "home": frozenset({"/home"}),
    "invocation": frozenset(
        {"/benchmark/[testId]/[suiteId]", "/invocation/[invocationId]"}
    ),
    "leaderboard": frozenset({"/leaderboard"}),
    "model": frozenset(
        {
            "/intelligence/models",
            "/intelligence/models/[modelId]",
            "/intelligence/models/new",
        }
    ),
    "parameter": frozenset(
        {
            "/management/parameters",
            "/management/parameters/[parameterId]",
            "/management/parameters/new",
        }
    ),
    "persona": frozenset(
        {
            "/training/personas",
            "/training/personas/[personaId]",
            "/training/personas/new",
        }
    ),
    "practice": frozenset({"/practice"}),
    "pricing": frozenset({"/analytics/pricing"}),
    "profile": frozenset(
        {
            "/management/profiles",
            "/management/profiles/[profileId]",
            "/management/profiles/new",
        }
    ),
    "provider": frozenset(
        {
            "/intelligence/providers",
            "/intelligence/providers/[providerId]",
            "/intelligence/providers/new",
        }
    ),
    "record": frozenset({"/analytics/reports/[profileId]", "/record/[recordId]"}),
    "reports": frozenset({"/analytics/reports"}),
    "rubric": frozenset(
        {"/system/rubrics", "/system/rubrics/[rubricId]", "/system/rubrics/new"}
    ),
    "scenario": frozenset(
        {
            "/training/scenarios",
            "/training/scenarios/[scenarioId]",
            "/training/scenarios/new",
        }
    ),
    "session": frozenset({"/analytics/activity/[sessionId]", "/session/[sessionId]"}),
    "setting": frozenset({"/settings", "/settings/[settingId]", "/settings/new"}),
    "simulation": frozenset(
        {
            "/training/simulations",
            "/training/simulations/[simulationId]",
            "/training/simulations/new",
        }
    ),
    "test": frozenset({"/benchmark/[testId]", "/test/[testId]"}),
    "tool": frozenset(
        {
            "/intelligence/tools",
            "/intelligence/tools/[toolId]",
            "/intelligence/tools/new",
        }
    ),
}
