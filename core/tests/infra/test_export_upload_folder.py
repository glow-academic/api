"""Focused tests for export responses using the current inline content contract."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor

pytestmark = pytest.mark.asyncio


def _ensure_export_type_packages(artifact_name: str) -> None:
    main_dir = (
        Path(__file__).resolve().parents[2] / "app" / "routes" / "v5" / "api" / "main"
    )
    artifact_dir = main_dir / artifact_name
    if "app.routes.v5" not in sys.modules:
        package = ModuleType("app.routes.v5")
        package.__path__ = [str(main_dir)]  # type: ignore[attr-defined]
        sys.modules["app.routes.v5"] = package
    package_name = f"app.routes.v5.{artifact_name}"
    if package_name not in sys.modules:
        package = ModuleType(package_name)
        package.__path__ = [str(artifact_dir)]  # type: ignore[attr-defined]
        sys.modules[package_name] = package


async def test_export_persona_impl_returns_inline_csv_content(
    pool,
    redis_client,
    setting_graph_factory,
):
    _ensure_export_type_packages("persona")
    from app.infra.persona.export import export_persona_impl
    from app.tools.artifacts.persona.create import create_persona
    from app.tools.resources.names.create import create_name

    actor = await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["persona"],
        group_name="persona-export-folder",
        role_name_prefix="Persona Export Admin",
    )

    async with pool.acquire() as conn:
        name = await create_name(conn, f"persona-export-{unique_tag()}", redis_client)
        persona = await create_persona(
            conn,
            name_id=name.id,
            department_ids=[actor.department_id],
        )

    result = await export_persona_impl(
        pool,
        redis_client,
        profile_id=actor.profile_id,
        persona_id=persona.id,
    )

    assert result.file_name.endswith(".csv")
    assert result.mime_type == "text/csv"
    assert result.row_count == 1
    assert result.content


async def test_export_scenario_impl_returns_inline_csv_content(
    pool,
    redis_client,
    setting_graph_factory,
):
    _ensure_export_type_packages("scenario")
    from app.infra.scenario.export import export_scenario_impl
    from app.tools.artifacts.scenario.create import create_scenario
    from app.tools.resources.names.create import create_name
    from app.tools.resources.problem_statements.create import (
        create_problem_statement,
    )

    actor = await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["scenario"],
        group_name="scenario-export-folder",
        role_name_prefix="Scenario Export Admin",
    )

    async with pool.acquire() as conn:
        name = await create_name(conn, f"scenario-export-{unique_tag()}", redis_client)
        problem_statement = await create_problem_statement(
            conn,
            name=f"scenario-problem-{unique_tag()}",
            problem_statement="Export scenario problem statement",
            redis=redis_client,
        )
        scenario = await create_scenario(
            conn,
            name_id=name.id,
            problem_statement_ids=[problem_statement.id],
            department_ids=[actor.department_id],
        )

    result = await export_scenario_impl(
        pool,
        redis_client,
        profile_id=actor.profile_id,
        scenario_id=scenario.id,
    )

    assert result.file_name.endswith(".csv")
    assert result.mime_type == "text/csv"
    assert result.row_count == 1
    assert result.content


async def test_export_profile_impl_returns_inline_csv_content(
    pool,
    redis_client,
    setting_graph_factory,
):
    _ensure_export_type_packages("profile")
    from app.infra.profile.export import export_profile_impl
    from app.tools.artifacts.profile.create import create_profile
    from app.tools.resources.emails.create import create_email
    from app.tools.resources.names.create import create_name
    from app.tools.resources.request_limits.create import create_request_limit
    from app.tools.resources.roles.create import create_role

    actor = await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["profile"],
        group_name="profile-export-folder",
        role_name_prefix="Profile Export Admin",
    )

    tag = unique_tag()
    async with pool.acquire() as conn:
        name = await create_name(conn, f"profile-export-{tag}", redis_client)
        email = await create_email(
            conn, f"profile-export-{tag}@example.com", redis_client
        )
        request_limit = await create_request_limit(conn, 42, redis_client)
        role = await create_role(
            conn,
            role="member",
            name=f"Profile Export Role {tag}",
            description=f"Profile export role {tag}",
            redis=redis_client,
        )
        profile = await create_profile(
            conn,
            name_id=name.id,
            email_ids=[email.id],
            request_limit_id=request_limit.id,
            department_ids=[actor.department_id],
            role_ids=[role.id],
            redis=redis_client,
        )

    result = await export_profile_impl(
        pool,
        redis_client,
        profile_id=actor.profile_id,
        profile_export_id=profile.id,
    )

    assert result.file_name.endswith(".csv")
    assert result.mime_type == "text/csv"
    assert result.row_count == 1
    assert result.content
