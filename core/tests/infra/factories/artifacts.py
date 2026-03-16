"""Artifact-level black-box factories for infra tests."""

from tests.helpers import unique_tag

from .types import (
    PersonaContextFixture,
    ProfileIdentityFixture,
    SettingGraphFixture,
    SystemGraphFixture,
)


async def create_profile_identity_fixture(
    pool,
    redis_client,
    *,
    name: str | None = "Test User",
    role: tuple[str, str, str] | None = (
        "admin",
        "Admin",
        "Administrator role",
    ),
    departments: list[str] | None = None,
    emails: list[str] | None = None,
    artifact_active: bool = True,
) -> ProfileIdentityFixture:
    """Create a real profile artifact plus linked resources for context tests."""
    from app.tools.artifacts.profile.create import (
        create_profile as create_profile_artifact,
    )
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.emails.create import create_email
    from app.tools.resources.names.create import create_name
    from app.tools.resources.profiles.create import (
        create_profile as create_profile_resource,
    )
    from app.tools.resources.roles.create import create_role

    tag = unique_tag()

    expected_name = f"{name}-{tag}" if name is not None else None
    expected_departments = (
        [f"{dept_name}-{tag}" for dept_name in departments]
        if departments is not None
        else []
    )
    expected_emails: list[str] = []

    async with pool.acquire() as conn:
        name_id = None
        if expected_name is not None:
            name_res = await create_name(conn, expected_name, redis_client)
            name_id = name_res.id

        role_ids = None
        expected_role = None
        expected_role_name = None
        expected_role_description = None
        expected_role_artifacts: list[str] = []
        if role is not None:
            role_key, role_name, role_description = role
            expected_role = role_key
            expected_role_name = f"{role_name} {tag}"
            expected_role_description = role_description
            role_res = await create_role(
                conn,
                role=expected_role,
                name=expected_role_name,
                description=role_description,
                redis=redis_client,
            )
            role_ids = [role_res.id]
            expected_role_artifacts = role_res.artifacts

        department_ids = None
        if departments is not None:
            department_ids = []
            for dept_name in expected_departments:
                dept_res = await create_department(
                    conn,
                    name=dept_name,
                    description="Test department",
                    redis=redis_client,
                )
                department_ids.append(dept_res.id)

        email_ids = None
        if emails is not None:
            email_ids = []
            for email in emails:
                local, domain = email.split("@", 1)
                expected_email = f"{local}+{tag}@{domain}"
                email_res = await create_email(
                    conn,
                    email=expected_email,
                    redis=redis_client,
                )
                email_ids.append(email_res.id)
                expected_emails.append(expected_email)

        profile_res = await create_profile_resource(
            conn,
            redis_client,
            name=f"profile-resource-{tag}",
            description="Test profile resource",
        )

        artifact_res = await create_profile_artifact(
            conn,
            name_id=name_id,
            department_ids=department_ids,
            email_ids=email_ids,
            role_ids=role_ids,
            profile_ids=[profile_res.id],
            soft=not artifact_active,
            redis=redis_client,
        )

    return ProfileIdentityFixture(
        artifact_id=artifact_res.id,
        profile_resource_id=profile_res.id,
        name=expected_name,
        role=expected_role,
        role_name=expected_role_name,
        role_description=expected_role_description,
        role_artifacts=expected_role_artifacts,
        departments=expected_departments,
        emails=expected_emails,
    )


async def create_setting_graph_fixture(
    pool,
    redis_client,
    *,
    tool_operation: str = "create",
    tool_artifacts: list[str] | None = None,
) -> SettingGraphFixture:
    """Create a full profile -> setting -> system -> agent -> tool graph."""
    from app.tools.artifacts.profile.create import (
        create_profile as create_profile_artifact,
    )
    from app.tools.resources.agents.create import create_agent
    from app.tools.resources.artifacts.create import create_artifact
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.names.create import create_name
    from app.tools.resources.operations.create import create_operation
    from app.tools.resources.profiles.create import (
        create_profile as create_profile_resource,
    )
    from app.tools.resources.settings.create import create_setting
    from app.tools.resources.systems.create import create_system
    from app.tools.resources.tools.create import create_tool

    tag = unique_tag()
    artifacts = tool_artifacts or ["profile", "persona"]

    async with pool.acquire() as conn:
        name_res = await create_name(conn, f"Graph User {tag}", redis_client)
        profile_res = await create_profile_resource(
            conn,
            redis_client,
            name=f"profile-resource-{tag}",
            description="Graph profile resource",
        )

        operation_res = await create_operation(conn, tool_operation, redis_client)
        artifact_rows = [
            await create_artifact(conn, artifact_name, redis_client)
            for artifact_name in artifacts
        ]

        tool_res = await create_tool(
            conn,
            name=f"tool-{tag}",
            description="Graph tool",
            operation=operation_res.operation,
            artifacts=[row.artifact for row in artifact_rows],
            redis=redis_client,
        )
        agent_res = await create_agent(
            conn,
            name=f"agent-{tag}",
            description="Graph agent",
            tool_ids=[tool_res.id],
            redis=redis_client,
        )
        system_res = await create_system(
            conn,
            name=f"system-{tag}",
            description="Graph system",
            agent_ids=[agent_res.id],
            redis=redis_client,
        )
        setting_res = await create_setting(
            conn,
            name=f"setting-{tag}",
            description="Graph setting",
            system_ids=[system_res.id],
            redis=redis_client,
        )
        department_res = await create_department(
            conn,
            name=f"department-{tag}",
            description="Graph department",
            setting_ids=[setting_res.id],
            is_primary=True,
            redis=redis_client,
        )
        profile_artifact_res = await create_profile_artifact(
            conn,
            name_id=name_res.id,
            department_ids=[department_res.id],
            profile_ids=[profile_res.id],
            redis=redis_client,
        )

    return SettingGraphFixture(
        profile_artifact_id=profile_artifact_res.id,
        profile_resource_id=profile_res.id,
        department_id=department_res.id,
        setting_id=setting_res.id,
        system_id=system_res.id,
        agent_id=agent_res.id,
        tool_id=tool_res.id,
        operation=operation_res.operation,
        resources=[],
        entries=[],
        artifacts=[row.artifact for row in artifact_rows],
    )


async def create_system_graph_fixture(
    pool,
    redis_client,
) -> SystemGraphFixture:
    """Create a full system -> agent -> model/provider/tool graph."""
    from app.tools.resources.agents.create import create_agent
    from app.tools.resources.args.create import create_arg
    from app.tools.resources.args_outputs.create import create_args_output
    from app.tools.resources.instructions.create import create_instruction
    from app.tools.resources.models.create import create_model
    from app.tools.resources.prompts.create import create_prompt
    from app.tools.resources.providers.create import create_provider
    from app.tools.resources.rubrics.create import create_rubric
    from app.tools.resources.systems.create import create_system
    from app.tools.resources.tools.create import create_tool

    tag = unique_tag()

    async with pool.acquire() as conn:
        provider_res = await create_provider(
            conn,
            name=f"provider-{tag}",
            description="Graph provider",
            redis=redis_client,
        )
        model_res = await create_model(
            conn,
            value=f"model-{tag}",
            name=f"Model {tag}",
            description="Graph model",
            provider_id=provider_res.id,
            redis=redis_client,
        )
        arg_res = await create_arg(
            conn,
            f"arg-{tag}",
            "text",
            redis_client,
        )
        arg_output_res = await create_args_output(
            conn,
            arg_res.id,
            f"arg-output-{tag}",
            redis_client,
        )
        tool_res = await create_tool(
            conn,
            name=f"tool-{tag}",
            description="Graph tool",
            args_ids=[arg_res.id],
            args_output_ids=[arg_output_res.id],
            redis=redis_client,
        )
        prompt_res = await create_prompt(
            conn,
            "You are a helpful system agent.",
            f"prompt-{tag}",
            "Graph prompt",
            redis_client,
        )
        instruction_res = await create_instruction(
            conn,
            "Follow the instructions carefully.",
            redis_client,
        )
        rubric_res = await create_rubric(
            conn,
            redis_client,
            name=f"rubric-{tag}",
            description="Graph rubric",
        )
        agent_res = await create_agent(
            conn,
            name=f"agent-{tag}",
            description="Graph agent",
            model_id=model_res.id,
            prompt_id=prompt_res.id,
            rubric_id=rubric_res.id,
            tool_ids=[tool_res.id],
            instruction_ids=[instruction_res.id],
            redis=redis_client,
        )
        system_res = await create_system(
            conn,
            name=f"system-{tag}",
            description="Graph system",
            agent_ids=[agent_res.id],
            redis=redis_client,
        )

    return SystemGraphFixture(
        system_id=system_res.id,
        agent_id=agent_res.id,
        model_id=model_res.id,
        provider_id=provider_res.id,
        tool_id=tool_res.id,
        arg_id=arg_res.id,
        arg_output_id=arg_output_res.id,
        prompt_id=prompt_res.id,
        instruction_id=instruction_res.id,
        rubric_id=rubric_res.id,
    )


async def create_persona_context_fixture(
    pool,
    redis_client,
) -> PersonaContextFixture:
    """Create a published persona plus a draft override and suggestion resources."""
    from app.tools.artifacts.persona.create import create_persona
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona_drafts.create import create_persona_draft
    from app.tools.entries.sessions.create import create_session
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.flags.create import create_flag
    from app.tools.resources.names.create import create_name
    from app.tools.resources.profiles.create import (
        create_profile as create_profile_resource,
    )

    tag = unique_tag()
    published_name = f"persona-published-{tag}"
    draft_name = f"persona-draft-{tag}"
    selected_description = f"persona-selected-description-{tag}"
    suggestion_description = f"persona-suggestion-description-{tag}"

    async with pool.acquire() as conn:
        profile_res = await create_profile_resource(
            conn,
            redis_client,
            name=f"profile-resource-{tag}",
            description="Persona context profile",
        )
        session_res = await create_session(conn, profile_id=profile_res.id)
        group_res = await create_group(conn, session_id=session_res.id)

        published_name_res = await create_name(conn, published_name, redis_client)
        draft_name_res = await create_name(conn, draft_name, redis_client)
        suggestion_name_res = await create_name(
            conn,
            f"persona-suggestion-{tag}",
            redis_client,
        )
        selected_description_res = await create_description(
            conn, selected_description, redis_client
        )
        suggestion_description_res = await create_description(
            conn, suggestion_description, redis_client
        )
        persona_flag_res = await create_flag(
            conn,
            name=f"persona-flag-{tag}",
            description="Persona flag",
            icon="user",
            flag_type="persona_active",
            redis=redis_client,
        )
        scenario_flag_res = await create_flag(
            conn,
            name=f"scenario-flag-{tag}",
            description="Scenario flag",
            icon="alert",
            flag_type="scenario_active",
            redis=redis_client,
        )

        persona_res = await create_persona(
            conn,
            name_id=published_name_res.id,
            description_id=selected_description_res.id,
        )
        await create_persona(
            conn,
            name_id=suggestion_name_res.id,
            description_id=suggestion_description_res.id,
        )
        draft_res = await create_persona_draft(
            conn,
            group_id=group_res.id,
            session_id=session_res.id,
            version=3,
            name_ids=[draft_name_res.id],
        )

    return PersonaContextFixture(
        persona_id=persona_res.id,
        group_id=group_res.id,
        draft_id=draft_res.id,
        published_name_id=published_name_res.id,
        published_name=published_name,
        draft_name_id=draft_name_res.id,
        draft_name=draft_name,
        selected_description_id=selected_description_res.id,
        selected_description=selected_description,
        suggestion_description_id=suggestion_description_res.id,
        suggestion_description=suggestion_description,
        persona_flag_id=persona_flag_res.id,
        scenario_flag_id=scenario_flag_res.id,
    )
