"""Route permissions — section/route definitions and access computation.

This module is the single source of truth for:
- Route paths and their access roles
- Section definitions (icon, order, children)
- compute_available_sections() — derives visible sections from user artifacts
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Profile role type (matches database enum)
ProfileRole = Literal[
    "guest", "member", "instructional", "admin", "superadmin", "custom"
]

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RoutePermission(BaseModel):
    """Route permission configuration."""

    path: str = Field(..., description="Route path with dynamic segments like [id]")
    roles: list[ProfileRole] = Field(
        ..., description="Roles allowed to access this route"
    )
    title: str = Field(..., description="Human-readable route title")
    description: str | None = Field(default=None, description="Route description")
    redirectTo: str | None = Field(
        default=None, description="Where to redirect if access denied"
    )
    create_label: str | None = Field(
        default=None, description="Label for create button on list pages"
    )
    artifact_type: str | None = Field(
        default=None, description="Artifact type for edit/create pages"
    )
    artifact: str | None = Field(
        default=None, description="Artifact that grants access to this route"
    )

    model_config = {"populate_by_name": True}


class SectionPermission(BaseModel):
    """Section permission configuration with nested routes."""

    section: str = Field(..., description="Section identifier")
    roles: list[ProfileRole] = Field(
        ..., description="Roles allowed to access this section"
    )
    title: str = Field(..., description="Human-readable section title")
    description: str | None = Field(default=None, description="Section description")
    routes: list[RoutePermission] = Field(..., description="Routes within this section")
    icon: str | None = Field(default=None, description="Lucide icon name")
    order: int = Field(default=0, description="Sidebar display order")
    children: list[str] | None = Field(
        default=None, description="Sidebar sub-section identifiers"
    )

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# ROUTE_PERMISSIONS — all paths use actual filesystem routes (no single-letter
# prefixes).
# ---------------------------------------------------------------------------

ROUTE_PERMISSIONS: list[SectionPermission] = [
    SectionPermission(
        section="home",
        roles=["member", "instructional", "admin", "superadmin"],
        title="Home",
        description="Main dashboard for member users",
        icon="Home",
        order=0,
        routes=[
            RoutePermission(
                path="/home",
                roles=["member", "instructional", "admin", "superadmin"],
                title="Home",
                redirectTo="/home",
                artifact="home",
            ),
            RoutePermission(
                path="/home/[attemptId]",
                roles=["member", "instructional", "admin", "superadmin"],
                title="Simulation Attempt",
                redirectTo="/home",
                artifact="attempt",
            ),
            RoutePermission(
                path="/home/[attemptId]/[trainingId]",
                roles=["member", "instructional", "admin", "superadmin"],
                title="Customize Training",
                redirectTo="/home",
                artifact="chat",
            ),
            # Canonical routes (top-level)
            RoutePermission(
                path="/attempt/[attemptId]",
                roles=["guest", "member", "instructional", "admin", "superadmin"],
                title="Attempt",
                redirectTo="/home",
                artifact="attempt",
            ),
            RoutePermission(
                path="/chat/[chatId]",
                roles=["guest", "member", "instructional", "admin", "superadmin"],
                title="Customize Training",
                redirectTo="/home",
                artifact="chat",
            ),
        ],
    ),
    SectionPermission(
        section="practice",
        roles=["guest", "member", "instructional", "admin", "superadmin"],
        title="Practice",
        description="Practice simulations for all users",
        icon="Target",
        order=1,
        routes=[
            RoutePermission(
                path="/practice",
                roles=["guest", "member", "instructional", "admin", "superadmin"],
                title="Practice",
                redirectTo="/practice",
                artifact="practice",
            ),
            RoutePermission(
                path="/practice/[attemptId]",
                roles=["guest", "member", "instructional", "admin", "superadmin"],
                title="Practice Attempt",
                redirectTo="/practice",
                artifact="attempt",
            ),
            RoutePermission(
                path="/practice/[attemptId]/[trainingId]",
                roles=["guest", "member", "instructional", "admin", "superadmin"],
                title="Customize Practice",
                redirectTo="/practice",
                artifact="chat",
            ),
        ],
    ),
    SectionPermission(
        section="leaderboard",
        roles=["member", "instructional", "admin", "superadmin"],
        title="Leaderboard",
        description="Performance leaderboard and rankings",
        icon="Trophy",
        order=2,
        routes=[
            RoutePermission(
                path="/leaderboard",
                roles=["member", "instructional", "admin", "superadmin"],
                title="Leaderboard",
                redirectTo="/leaderboard",
                artifact="leaderboard",
            ),
        ],
    ),
    SectionPermission(
        section="analytics",
        roles=["instructional", "admin", "superadmin"],
        title="Analytics",
        description="Analytics and reporting tools",
        icon="PieChart",
        order=3,
        children=["dashboard", "reports", "activity", "pricing"],
        routes=[
            # Section parent — accessible if any child artifact is available
            RoutePermission(
                path="/analytics",
                roles=["instructional", "admin", "superadmin"],
                title="Analytics",
                redirectTo="/analytics/dashboard",
            ),
            RoutePermission(
                path="/analytics/dashboard",
                roles=["instructional", "admin", "superadmin"],
                title="Dashboard",
                redirectTo="/analytics/dashboard",
                artifact="dashboard",
            ),
            RoutePermission(
                path="/analytics/reports",
                roles=["instructional", "admin", "superadmin"],
                title="Reports",
                redirectTo="/analytics/reports",
                artifact="reports",
            ),
            RoutePermission(
                path="/analytics/reports/[profileId]",
                roles=["instructional", "admin", "superadmin"],
                title="Profile Report",
                redirectTo="/analytics/reports",
                artifact_type="profile",
                artifact="record",
            ),
            RoutePermission(
                path="/analytics/activity",
                roles=["instructional", "admin", "superadmin"],
                title="Activity",
                redirectTo="/analytics/activity",
                artifact="activity",
            ),
            RoutePermission(
                path="/analytics/activity/[sessionId]",
                roles=["instructional", "admin", "superadmin"],
                title="Session Activity",
                redirectTo="/analytics/activity",
                artifact="session",
            ),
            RoutePermission(
                path="/analytics/pricing",
                roles=["instructional", "admin", "superadmin"],
                title="Pricing",
                redirectTo="/analytics/pricing",
                artifact="pricing",
            ),
            RoutePermission(
                path="/analytics/pricing/[groupId]",
                roles=["instructional", "admin", "superadmin"],
                title="Pricing Group",
                redirectTo="/analytics/pricing",
                artifact="group",
            ),
            # Canonical routes (top-level)
            RoutePermission(
                path="/record/[recordId]",
                roles=["instructional", "admin", "superadmin"],
                title="Profile Report",
                redirectTo="/analytics/reports",
                artifact_type="profile",
                artifact="record",
            ),
            RoutePermission(
                path="/session/[sessionId]",
                roles=["instructional", "admin", "superadmin"],
                title="Session Activity",
                redirectTo="/analytics/activity",
                artifact="session",
            ),
            RoutePermission(
                path="/group/[groupId]",
                roles=["instructional", "admin", "superadmin"],
                title="Pricing Group",
                redirectTo="/analytics/pricing",
                artifact="group",
            ),
        ],
    ),
    SectionPermission(
        section="training",
        roles=["instructional", "admin", "superadmin"],
        title="Training",
        description="Training content tools",
        icon="GraduationCap",
        order=4,
        children=["cohorts", "simulations", "scenarios", "personas"],
        routes=[
            # Section parent — accessible if any child artifact is available
            RoutePermission(
                path="/training",
                roles=["instructional", "admin", "superadmin"],
                title="Training",
                redirectTo="/training/personas",
            ),
            RoutePermission(
                path="/training/cohorts",
                roles=["instructional", "admin", "superadmin"],
                title="Cohorts",
                redirectTo="/training/cohorts",
                create_label="Create Cohort",
                artifact="cohort",
            ),
            RoutePermission(
                path="/training/cohorts/new",
                roles=["instructional", "admin", "superadmin"],
                title="Create Cohort",
                redirectTo="/training/cohorts",
                artifact_type="cohort",
                artifact="cohort",
            ),
            RoutePermission(
                path="/training/cohorts/[cohortId]",
                roles=["instructional", "admin", "superadmin"],
                title="Edit Cohort",
                redirectTo="/training/cohorts",
                artifact_type="cohort",
                artifact="cohort",
            ),
            RoutePermission(
                path="/training/simulations",
                roles=["instructional", "admin", "superadmin"],
                title="Simulations",
                redirectTo="/training/simulations",
                create_label="Create Simulation",
                artifact="simulation",
            ),
            RoutePermission(
                path="/training/simulations/new",
                roles=["instructional", "admin", "superadmin"],
                title="Create Simulation",
                redirectTo="/training/simulations",
                artifact_type="simulation",
                artifact="simulation",
            ),
            RoutePermission(
                path="/training/simulations/[simulationId]",
                roles=["instructional", "admin", "superadmin"],
                title="Edit Simulation",
                redirectTo="/training/simulations",
                artifact_type="simulation",
                artifact="simulation",
            ),
            RoutePermission(
                path="/training/scenarios",
                roles=["instructional", "admin", "superadmin"],
                title="Scenarios",
                redirectTo="/training/scenarios",
                create_label="Create Scenario",
                artifact="scenario",
            ),
            RoutePermission(
                path="/training/scenarios/new",
                roles=["instructional", "admin", "superadmin"],
                title="Create Scenario",
                redirectTo="/training/scenarios",
                artifact_type="scenario",
                artifact="scenario",
            ),
            RoutePermission(
                path="/training/scenarios/[scenarioId]",
                roles=["instructional", "admin", "superadmin"],
                title="Edit Scenario",
                redirectTo="/training/scenarios",
                artifact_type="scenario",
                artifact="scenario",
            ),
            RoutePermission(
                path="/training/personas",
                roles=["instructional", "admin", "superadmin"],
                title="Personas",
                redirectTo="/training/personas",
                create_label="Create Persona",
                artifact="persona",
            ),
            RoutePermission(
                path="/training/personas/new",
                roles=["instructional", "admin", "superadmin"],
                title="Create Persona",
                redirectTo="/training/personas",
                artifact_type="persona",
                artifact="persona",
            ),
            RoutePermission(
                path="/training/personas/[personaId]",
                roles=["instructional", "admin", "superadmin"],
                title="Edit Persona",
                redirectTo="/training/personas",
                artifact_type="persona",
                artifact="persona",
            ),
        ],
    ),
    SectionPermission(
        section="management",
        roles=["admin", "superadmin"],
        title="Management",
        description="System management tools",
        icon="ClipboardList",
        order=5,
        children=["profiles", "documents", "parameters", "fields"],
        routes=[
            RoutePermission(
                path="/management",
                roles=["admin", "superadmin"],
                title="Management",
                redirectTo="/management/profiles",
            ),
            RoutePermission(
                path="/management/profiles",
                roles=["admin", "superadmin"],
                title="Profiles",
                redirectTo="/management/profiles",
                create_label="Create Profile",
                artifact="profile",
            ),
            RoutePermission(
                path="/management/profiles/new",
                roles=["admin", "superadmin"],
                title="Create Profile",
                redirectTo="/management/profiles",
                artifact_type="profile",
                artifact="profile",
            ),
            RoutePermission(
                path="/management/profiles/[profileId]",
                roles=["admin", "superadmin"],
                title="Edit Profile",
                redirectTo="/management/profiles",
                artifact_type="profile",
                artifact="profile",
            ),
            RoutePermission(
                path="/management/documents",
                roles=["admin", "superadmin"],
                title="Documents",
                redirectTo="/management/documents",
                create_label="Create Document",
                artifact="document",
            ),
            RoutePermission(
                path="/management/documents/new",
                roles=["admin", "superadmin"],
                title="Create Document",
                redirectTo="/management/documents",
                artifact_type="document",
                artifact="document",
            ),
            RoutePermission(
                path="/management/documents/[documentId]",
                roles=["admin", "superadmin"],
                title="Edit Document",
                redirectTo="/management/documents",
                artifact_type="document",
                artifact="document",
            ),
            RoutePermission(
                path="/management/parameters",
                roles=["admin", "superadmin"],
                title="Parameters",
                redirectTo="/management/parameters",
                create_label="Create Parameter",
                artifact="parameter",
            ),
            RoutePermission(
                path="/management/parameters/new",
                roles=["admin", "superadmin"],
                title="Create Parameter",
                redirectTo="/management/parameters",
                artifact_type="parameter",
                artifact="parameter",
            ),
            RoutePermission(
                path="/management/parameters/[parameterId]",
                roles=["admin", "superadmin"],
                title="Edit Parameter",
                redirectTo="/management/parameters",
                artifact_type="parameter",
                artifact="parameter",
            ),
            RoutePermission(
                path="/management/fields",
                roles=["admin", "superadmin"],
                title="Fields",
                redirectTo="/management/fields",
                create_label="Create Field",
                artifact="field",
            ),
            RoutePermission(
                path="/management/fields/new",
                roles=["admin", "superadmin"],
                title="Create Field",
                redirectTo="/management/fields",
                artifact_type="field",
                artifact="field",
            ),
            RoutePermission(
                path="/management/fields/[fieldId]",
                roles=["admin", "superadmin"],
                title="Edit Field",
                redirectTo="/management/fields",
                artifact_type="field",
                artifact="field",
            ),
        ],
    ),
    SectionPermission(
        section="intelligence",
        roles=["admin", "superadmin"],
        title="Intelligence",
        description="Intelligence configuration tools",
        icon="Sparkles",
        order=6,
        children=["agents", "models", "providers", "tools"],
        routes=[
            RoutePermission(
                path="/intelligence",
                roles=["admin", "superadmin"],
                title="Intelligence",
                redirectTo="/intelligence/agents",
            ),
            RoutePermission(
                path="/intelligence/agents",
                roles=["admin", "superadmin"],
                title="Agents",
                redirectTo="/intelligence/agents",
                create_label="Create Agent",
                artifact="agent",
            ),
            RoutePermission(
                path="/intelligence/agents/new",
                roles=["admin", "superadmin"],
                title="Create Agent",
                redirectTo="/intelligence/agents",
                artifact_type="agent",
                artifact="agent",
            ),
            RoutePermission(
                path="/intelligence/agents/[agentId]",
                roles=["admin", "superadmin"],
                title="Edit Agent",
                redirectTo="/intelligence/agents",
                artifact_type="agent",
                artifact="agent",
            ),
            RoutePermission(
                path="/intelligence/models",
                roles=["admin", "superadmin"],
                title="Models",
                redirectTo="/intelligence/models",
                create_label="Create Model",
                artifact="model",
            ),
            RoutePermission(
                path="/intelligence/models/new",
                roles=["admin", "superadmin"],
                title="Create Model",
                redirectTo="/intelligence/models",
                artifact_type="model",
                artifact="model",
            ),
            RoutePermission(
                path="/intelligence/models/[modelId]",
                roles=["admin", "superadmin"],
                title="Edit Model",
                redirectTo="/intelligence/models",
                artifact_type="model",
                artifact="model",
            ),
            RoutePermission(
                path="/intelligence/providers",
                roles=["admin", "superadmin"],
                title="Providers",
                redirectTo="/intelligence/providers",
                create_label="Create Provider",
                artifact="provider",
            ),
            RoutePermission(
                path="/intelligence/providers/new",
                roles=["admin", "superadmin"],
                title="Create Provider",
                redirectTo="/intelligence/providers",
                artifact_type="provider",
                artifact="provider",
            ),
            RoutePermission(
                path="/intelligence/providers/[providerId]",
                roles=["admin", "superadmin"],
                title="Edit Provider",
                redirectTo="/intelligence/providers",
                artifact_type="provider",
                artifact="provider",
            ),
            RoutePermission(
                path="/intelligence/tools",
                roles=["admin", "superadmin"],
                title="Tools",
                redirectTo="/intelligence/tools",
                create_label="Create Tool",
                artifact="tool",
            ),
            RoutePermission(
                path="/intelligence/tools/new",
                roles=["admin", "superadmin"],
                title="Create Tool",
                redirectTo="/intelligence/tools",
                artifact_type="tool",
                artifact="tool",
            ),
            RoutePermission(
                path="/intelligence/tools/[toolId]",
                roles=["admin", "superadmin"],
                title="Edit Tool",
                redirectTo="/intelligence/tools",
                artifact_type="tool",
                artifact="tool",
            ),
        ],
    ),
    SectionPermission(
        section="system",
        roles=["superadmin"],
        title="System",
        description="System administration tools",
        icon="Server",
        order=7,
        children=["departments", "rubrics", "auth", "evals"],
        routes=[
            RoutePermission(
                path="/system",
                roles=["superadmin"],
                title="System",
                redirectTo="/system/departments",
            ),
            RoutePermission(
                path="/system/departments",
                roles=["superadmin"],
                title="Departments",
                redirectTo="/system/departments",
                create_label="Create Department",
                artifact="department",
            ),
            RoutePermission(
                path="/system/departments/new",
                roles=["superadmin"],
                title="Create Department",
                redirectTo="/system/departments",
                artifact_type="department",
                artifact="department",
            ),
            RoutePermission(
                path="/system/departments/[departmentId]",
                roles=["superadmin"],
                title="Edit Department",
                redirectTo="/system/departments",
                artifact_type="department",
                artifact="department",
            ),
            RoutePermission(
                path="/system/rubrics",
                roles=["superadmin"],
                title="Rubrics",
                redirectTo="/system/rubrics",
                create_label="Create Rubric",
                artifact="rubric",
            ),
            RoutePermission(
                path="/system/rubrics/new",
                roles=["superadmin"],
                title="Create Rubric",
                redirectTo="/system/rubrics",
                artifact_type="rubric",
                artifact="rubric",
            ),
            RoutePermission(
                path="/system/rubrics/[rubricId]",
                roles=["superadmin"],
                title="Edit Rubric",
                redirectTo="/system/rubrics",
                artifact_type="rubric",
                artifact="rubric",
            ),
            RoutePermission(
                path="/system/auth",
                roles=["superadmin"],
                title="Auth",
                redirectTo="/system/auth",
                artifact="auth",
            ),
            RoutePermission(
                path="/system/auth/new",
                roles=["superadmin"],
                title="Create Auth",
                redirectTo="/system/auth",
                artifact_type="auth",
                artifact="auth",
            ),
            RoutePermission(
                path="/system/auth/[authId]",
                roles=["superadmin"],
                title="Edit Auth",
                redirectTo="/system/auth",
                artifact_type="auth",
                artifact="auth",
            ),
            RoutePermission(
                path="/system/evals",
                roles=["superadmin"],
                title="Evals",
                redirectTo="/system/evals",
                create_label="Create Eval",
                artifact="eval",
            ),
            RoutePermission(
                path="/system/evals/new",
                roles=["superadmin"],
                title="Create Eval",
                redirectTo="/system/evals",
                artifact_type="eval",
                artifact="eval",
            ),
            RoutePermission(
                path="/system/evals/[evalId]",
                roles=["superadmin"],
                title="Edit Eval",
                redirectTo="/system/evals",
                artifact_type="eval",
                artifact="eval",
            ),
        ],
    ),
    SectionPermission(
        section="health",
        roles=["admin", "superadmin"],
        title="Health",
        description="System health monitoring",
        icon="Activity",
        order=8,
        routes=[
            RoutePermission(
                path="/health",
                roles=["admin", "superadmin"],
                title="Health",
                redirectTo="/health",
                artifact="health",
            ),
        ],
    ),
    SectionPermission(
        section="benchmark",
        roles=["custom", "instructional", "admin", "superadmin"],
        title="Benchmark",
        description="Run and manage evaluations",
        icon="Gauge",
        order=9,
        routes=[
            RoutePermission(
                path="/benchmark",
                roles=["custom", "instructional", "admin", "superadmin"],
                title="Benchmark",
                redirectTo="/benchmark",
                artifact="benchmark",
            ),
            RoutePermission(
                path="/benchmark/[testId]",
                roles=["custom", "instructional", "admin", "superadmin"],
                title="Benchmark Test",
                redirectTo="/benchmark",
                artifact="test",
            ),
            RoutePermission(
                path="/benchmark/[testId]/[suiteId]",
                roles=["custom", "instructional", "admin", "superadmin"],
                title="Benchmark Suite",
                redirectTo="/benchmark",
                artifact="eval",
            ),
            # Canonical routes (top-level)
            RoutePermission(
                path="/test/[testId]",
                roles=["custom", "instructional", "admin", "superadmin"],
                title="Benchmark Test",
                redirectTo="/benchmark",
                artifact="test",
            ),
        ],
    ),
    SectionPermission(
        section="settings",
        roles=["admin", "superadmin"],
        title="Settings",
        description="System settings and configuration",
        icon="Settings",
        order=10,
        routes=[
            RoutePermission(
                path="/settings",
                roles=["admin", "superadmin"],
                title="Settings",
                redirectTo="/settings",
                artifact="settings",
            ),
            RoutePermission(
                path="/settings/new",
                roles=["admin", "superadmin"],
                title="Create Setting",
                redirectTo="/settings",
                artifact_type="settings",
                artifact="settings",
            ),
            RoutePermission(
                path="/settings/[settingId]",
                roles=["admin", "superadmin"],
                title="Edit Setting",
                redirectTo="/settings",
                artifact_type="settings",
                artifact="settings",
            ),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Computation functions
# ---------------------------------------------------------------------------


def compute_available_sections(user_artifacts: list[str]) -> list[str]:
    """Derive sections from artifacts — a section is visible if ANY of its routes' artifacts are in user_artifacts."""
    artifact_set = set(user_artifacts)
    sections: list[str] = []
    for sp in ROUTE_PERMISSIONS:
        if any(rp.artifact in artifact_set for rp in sp.routes if rp.artifact):
            sections.append(sp.section)
    return sections
