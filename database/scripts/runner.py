"""Seed runner — executes Python seed definitions against a temp DB and dumps SQL.

Usage:
    python -m database.scripts.runner --setup university     # Seed a single setup
    python -m database.scripts.runner --all                  # Seed all setups

Each setup is fully independent — creates ALL platform resources (modules 01-10)
+ setup-specific data (departments, profiles, settings, etc.) from scratch.
No shared base-seed.sql. Each generates its own history/{setup}.sql.gz.

Flow:
  1. Spin up Postgres + Redis testcontainers
  2. Load schema
  3. Bootstrap setup's superadmin profile
  4. Seed base modules (resources, providers, models, agents, etc.)
  5. Seed setup-specific modules
  6. Full dump → history/{setup}.sql.gz
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

import asyncpg
from dotenv import load_dotenv
from redis.asyncio import Redis
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# Load .env from project root (before any seed modules read env vars)
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Ensure core/ is on sys.path for app imports
CORE_DIR = PROJECT_ROOT / "core"
sys.path.insert(0, str(CORE_DIR))

DATABASE_DIR = Path(__file__).parent.parent
SCHEMA_DIR = DATABASE_DIR / "schema"
SEEDS_DIR = DATABASE_DIR / "seeds"
BUILD_DIR = Path(tempfile.mkdtemp(prefix="glow_seed_build_"))

# Profile ID for seed operations (Default Superadmin from test fixtures)
SEED_PROFILE_ID = UUID("019b3be4-36f0-788c-9df2-481eb5917940")


# ---------------------------------------------------------------------------
# Schema + module loading (mirrors test conftest.py)
# ---------------------------------------------------------------------------


def _concat_schema(schema_dir: Path) -> str:
    """Concatenate split schema files into a single SQL string."""
    parts: list[str] = []

    ext = schema_dir / "extensions.sql"
    if ext.exists():
        parts.append(ext.read_text())

    funcs = schema_dir / "functions.sql"
    if funcs.exists():
        parts.append(funcs.read_text())

    enums_dir = schema_dir / "enums"
    if enums_dir.exists():
        for f in sorted(enums_dir.glob("*.sql")):
            parts.append(f.read_text())

    subfolders = ("artifacts", "entries", "resources", "junctions", "connections")

    for subfolder in subfolders:
        d = schema_dir / "tables" / subfolder
        if d.exists():
            for f in sorted(d.glob("*.sql")):
                parts.append(f.read_text())

    for subfolder in subfolders:
        d = schema_dir / "indexes" / subfolder
        if d.exists():
            for f in sorted(d.glob("*.sql")):
                parts.append(f.read_text())

    for subfolder in subfolders:
        d = schema_dir / "foreign_keys" / subfolder
        if d.exists():
            for f in sorted(d.glob("*.sql")):
                parts.append(f.read_text())

    parts.append("SET search_path = public;")

    views_dir = schema_dir / "views"
    if views_dir.exists():
        for f in sorted(views_dir.glob("*.sql")):
            parts.append(f.read_text())

    idx_views_dir = schema_dir / "indexes" / "views"
    if idx_views_dir.exists():
        for f in sorted(idx_views_dir.glob("*.sql")):
            parts.append(f.read_text())

    return "\n".join(parts)


def _filter_meta_commands(sql: str) -> str:
    """Remove psql meta-commands (\\connect, SET client_encoding, etc.)."""
    return re.sub(r"^\\.*$", "", sql, flags=re.MULTILINE)


# ---------------------------------------------------------------------------
# Resource seed execution (tool-level create_* functions)
# ---------------------------------------------------------------------------


async def _run_resource_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Run all resource seed definitions through tool-level create_* functions."""
    from database.seeds.resources import MODULES

    for module_name in MODULES:
        print(f"\nSeeding {module_name}...")
        mod = importlib.import_module(f"database.seeds.resources.{module_name}")
        items = getattr(mod, module_name)  # e.g. mod.colors, mod.icons

        async with pool.acquire() as conn:
            if module_name == "colors":
                await _seed_colors(conn, redis, items)
            elif module_name == "icons":
                await _seed_icons(conn, redis, items)
            elif module_name == "flags":
                await _seed_flags(conn, redis, items)
            elif module_name == "roles":
                await _seed_roles(conn, redis, items)
            elif module_name == "modalities":
                await _seed_modalities(conn, redis, items)
            elif module_name == "qualities":
                await _seed_qualities(conn, redis, items)
            elif module_name == "thresholds":
                await _seed_thresholds(conn, redis, items)
            elif module_name == "points":
                await _seed_points(conn, redis, items)
            elif module_name == "request_limits":
                await _seed_request_limits(conn, redis, items)
            elif module_name == "reasoning_levels":
                await _seed_reasoning_levels(conn, redis, items)
            elif module_name == "temperature_levels":
                await _seed_temperature_levels(conn, redis, items)
            elif module_name == "permissions":
                await _seed_permissions(conn, redis, items)
            elif module_name == "args":
                await _seed_args(conn, redis, items)
            elif module_name == "args_outputs":
                await _seed_args_outputs(conn, redis, items)
            elif module_name == "standard_groups":
                await _seed_standard_groups(conn, redis, items)
            elif module_name == "standards":
                await _seed_standards(conn, redis, items)
            elif module_name == "keys":
                await _seed_keys(conn, redis, items)
            elif module_name == "items":
                await _seed_items(conn, redis, items)


async def _seed_colors(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.colors.create import create_color

    for item in items:
        color_type = item.pop("type", "primary")
        await create_color(conn, redis=redis, color_type=color_type, **item)
    print(f"  OK: {len(items)} colors created")


async def _seed_icons(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.icons.create import create_icon

    for item in items:
        await create_icon(conn, redis=redis, **item)
    print(f"  OK: {len(items)} icons created")


async def _seed_flags(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.flags.create import create_flag

    for item in items:
        clean = {k: v for k, v in item.items() if k != "type"}
        flag_type = item.get("type", "active")
        await create_flag(conn, redis=redis, flag_type=flag_type, **clean)
    print(f"  OK: {len(items)} flags created")


async def _seed_roles(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.roles.create import create_role

    for item in items:
        # Strip legacy 'artifacts' field (replaced by permission_ids)
        clean = {k: v for k, v in item.items() if k != "artifacts"}
        await create_role(conn, redis=redis, **clean)
    print(f"  OK: {len(items)} roles created")


async def _seed_modalities(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.modalities.create import create_modality

    for item in items:
        await create_modality(conn, redis=redis, **item)
    print(f"  OK: {len(items)} modalities created")


async def _seed_qualities(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.qualities.create import create_quality

    for item in items:
        await create_quality(conn, redis=redis, **item)
    print(f"  OK: {len(items)} qualities created")


async def _seed_thresholds(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.thresholds.create import create_threshold

    for item in items:
        threshold_type = item.pop("type", "success")
        await create_threshold(conn, redis=redis, threshold_type=threshold_type, **item)
    print(f"  OK: {len(items)} thresholds created")


async def _seed_points(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.points.create import create_point

    for item in items:
        point_type = item.pop("type", "total")
        await create_point(conn, redis=redis, point_type=point_type, **item)
    print(f"  OK: {len(items)} points created")


async def _seed_request_limits(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.request_limits.create import create_request_limit

    for item in items:
        await create_request_limit(conn, redis=redis, **item)
    print(f"  OK: {len(items)} request_limits created")


async def _seed_voices(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.voices.create import create_voice

    for item in items:
        await create_voice(conn, redis=redis, **item)
    print(f"  OK: {len(items)} voices created")


async def _seed_pricing(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.pricing.create import create_pricing

    for item in items:
        await create_pricing(conn, redis=redis, **item)
    print(f"  OK: {len(items)} pricing entries created")


async def _seed_reasoning_levels(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.reasoning_levels.create import (
        create_reasoning_level,
    )

    for item in items:
        await create_reasoning_level(conn, redis=redis, **item)
    print(f"  OK: {len(items)} reasoning_levels created")


async def _seed_temperature_levels(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.temperature_levels.create import (
        create_temperature_level,
    )

    for item in items:
        await create_temperature_level(conn, redis=redis, **item)
    print(f"  OK: {len(items)} temperature_levels created")


async def _seed_permissions(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.permissions.create import create_permission

    for item in items:
        await create_permission(conn, redis=redis, **item)
    print(f"  OK: {len(items)} permissions created")


async def _seed_args(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.args.create import create_arg

    for item in items:
        await create_arg(conn, redis=redis, **item)
    print(f"  OK: {len(items)} args created")


async def _seed_args_outputs(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.args_outputs.create import create_args_output

    for item in items:
        await create_args_output(conn, redis=redis, **item)
    print(f"  OK: {len(items)} args_outputs created")


async def _seed_standard_groups(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.standard_groups.create import (
        create_standard_group,
    )

    for item in items:
        await create_standard_group(conn, redis=redis, **item)
    print(f"  OK: {len(items)} standard_groups created")


async def _seed_standards(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.standards.create import create_standard

    for item in items:
        await create_standard(conn, redis=redis, **item)
    print(f"  OK: {len(items)} standards created")


async def _seed_keys(conn: asyncpg.Connection, redis: Redis, items: list[dict]) -> None:
    from app.tools.resources.keys.create import create_key

    for item in items:
        await create_key(conn, redis=redis, **item)
    print(f"  OK: {len(items)} keys created")


async def _seed_items(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.items.create import create_item

    for item in items:
        await create_item(conn, redis=redis, **item)
    print(f"  OK: {len(items)} items created")


# ---------------------------------------------------------------------------
# Module seed execution
# ---------------------------------------------------------------------------


async def _run_profile_bootstrap(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 09 — Bootstrap profiles using artifact + resource creates.

    Profiles require lower-level creates because _impl functions need a
    profile_id, but no profiles exist yet. This creates the Default Superadmin
    first, then remaining profiles.
    """
    from app.tools.artifacts.profile.create import (
        create_profile as create_profile_artifact,
    )
    from app.tools.resources.emails.create import create_email
    from app.tools.resources.names.create import create_name
    from app.tools.resources.profiles.create import (
        create_profile as create_profile_resource,
    )
    from database.seeds.profiles import profiles

    async with pool.acquire() as conn:
        for p in profiles:
            async with conn.transaction():
                # Step 1: create name resource
                name_resp = await create_name(conn, name=p["name"], redis=redis)
                name_id = name_resp.id

                # Step 2: create email resource (if provided)
                email_ids = None
                if p.get("email"):
                    email_resp = await create_email(conn, email=p["email"], redis=redis)
                    email_ids = [email_resp.id]

                # Step 3: create profiles_resource (denormalized snapshot)
                profile_resource = await create_profile_resource(
                    conn,
                    redis,
                    id=p.get("resource_id"),
                    name=p["name"],
                    department_ids=p.get("department_ids"),
                    role_id=p.get("role_id"),
                    emails=[p["email"]] if p.get("email") else None,
                    primary_email=p.get("email"),
                )
                profiles_resource_id = profile_resource.id

                # Step 4: create profile artifact with junctions (including email)
                await create_profile_artifact(
                    conn,
                    id=p["id"],
                    name_id=name_id,
                    role_ids=[p["role_id"]] if p.get("role_id") else None,
                    flag_ids=p.get("flag_ids"),
                    profile_ids=[profiles_resource_id],
                    email_ids=email_ids,
                    request_limit_id=p.get("request_limit_id"),
                    redis=redis,
                )

    print(f"  OK: {len(profiles)} profiles bootstrapped")


async def _run_provider_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 02 — Create providers via _impl."""
    from app.infra.provider.create import CreateProviderItem, create_provider_impl
    from database.seeds.providers import providers

    items = [CreateProviderItem(**d) for d in providers]
    await create_provider_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )
    print(f"  OK: {len(providers)} providers created")


async def _run_model_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 03 — Create models via _impl."""
    from app.infra.model.create import CreateModelItem, create_model_impl
    from database.seeds.models import models

    items = [CreateModelItem(**d) for d in models]
    await create_model_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )
    print(f"  OK: {len(models)} models created")


async def _run_prompt_and_instruction_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 04a — Create prompts and instructions before agents."""
    from app.tools.resources.prompts.create import create_prompt
    from app.tools.resources.instructions.create import create_instruction
    from database.seeds.prompts import prompts, instructions

    async with pool.acquire() as conn:
        for p in prompts:
            await create_prompt(
                conn,
                system_prompt=p["system_prompt"],
                name=p["name"],
                description=p["description"],
                redis=redis,
                id=p["id"],
            )
        for i in instructions:
            await create_instruction(
                conn,
                template=i["template"],
                redis=redis,
                id=i["id"],
            )
    print(f"  OK: {len(prompts)} prompts + {len(instructions)} instructions created")


async def _run_agent_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 04 — Create agents via _impl."""
    from app.infra.agent.create import CreateAgentItem, create_agent_impl
    from database.seeds.agents import agents

    items = [CreateAgentItem(**d) for d in agents]
    await create_agent_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )
    print(f"  OK: {len(agents)} agents created")


async def _run_auth_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 06 — Create auths via _impl."""
    from app.infra.auth.create import CreateAuthItem, create_auth_impl
    from database.seeds.auths import auths

    items = [CreateAuthItem(**d) for d in auths]
    await create_auth_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )
    print(f"  OK: {len(auths)} auths created")


async def _run_eval_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 08 — Create evals via _impl."""
    from app.infra.eval.create import CreateEvalItem, create_eval_impl
    from database.seeds.evals import evals

    items = [CreateEvalItem(**d) for d in evals]
    await create_eval_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )
    print(f"  OK: {len(evals)} evals created")


async def _run_system_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 10 — Create systems via tool-level create."""
    from app.tools.resources.systems.create import create_system
    from database.seeds.systems import systems

    async with pool.acquire() as conn:
        for s in systems:
            await create_system(conn, redis=redis, **s)

    print(f"  OK: {len(systems)} systems created")


async def _run_rubric_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 07 — Create rubrics via _impl."""
    from app.infra.rubric.create import CreateRubricItem, create_rubric_impl
    from database.seeds.rubrics import rubrics

    items = [CreateRubricItem(**d) for d in rubrics]
    result = await create_rubric_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )
    ok = sum(1 for r in result.results if r.success)
    errors = sum(1 for r in result.results if not r.success)
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
    print(f"  OK: {ok} rubrics created, {errors} errors")


# ---------------------------------------------------------------------------
# Setup seed execution (infra-level create_*_impl functions)
# ---------------------------------------------------------------------------


async def _run_document_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    document_defs: list[dict],
) -> list[UUID]:
    """Run document seed definitions through create_document_impl."""
    from app.infra.document.create import CreateDocumentItem, create_document_impl

    items = [CreateDocumentItem(**d) for d in document_defs]

    result = await create_document_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "document_id") and r.document_id:
                created_ids.append(r.document_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_department_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    department_defs: list[dict],
) -> list[UUID]:
    """Run department seed definitions through create_department_impl."""
    from app.infra.department.create import (
        CreateDepartmentItem,
        create_department_impl,
    )

    items = [CreateDepartmentItem(**d) for d in department_defs]

    result = await create_department_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "department_id") and r.department_id:
                created_ids.append(r.department_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_persona_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    persona_defs: list[dict],
) -> list[UUID]:
    """Run persona seed definitions through create_persona_impl."""
    from app.infra.persona.create import CreatePersonaItem, create_persona_impl
    from app.infra.persona.types import CreatePersonaApiRequest

    items = [CreatePersonaItem(**p) for p in persona_defs]

    result = await create_persona_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreatePersonaApiRequest(personas=items),
    )

    # Check for errors
    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "persona_id") and r.persona_id:
                created_ids.append(r.persona_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_scenario_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    scenario_defs: list[dict],
) -> list[UUID]:
    """Run scenario seed definitions through create_scenario_impl."""
    from app.infra.scenario.create import CreateScenarioItem, create_scenario_impl

    items = [CreateScenarioItem(**s) for s in scenario_defs]

    result = await create_scenario_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "scenario_id") and r.scenario_id:
                created_ids.append(r.scenario_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_simulation_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    simulation_defs: list[dict],
) -> list[UUID]:
    """Run simulation seed definitions through create_simulation_impl."""
    from app.infra.simulation.create import (
        CreateSimulationItem,
        create_simulation_impl,
    )

    items = [CreateSimulationItem(**s) for s in simulation_defs]

    result = await create_simulation_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "simulation_id") and r.simulation_id:
                created_ids.append(r.simulation_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_scenario_rubric_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    scenario_rubric_defs: list[dict],
) -> list[UUID]:
    """Run scenario_rubric seed definitions (resource-level create)."""
    from app.tools.resources.scenario_rubrics.create import (
        create_scenario_rubric,
    )

    created_ids: list[UUID] = []
    for sr in scenario_rubric_defs:
        async with pool.acquire() as conn:
            result = await create_scenario_rubric(
                conn,
                scenario_id=sr["scenario_id"],
                rubric_id=sr["rubric_id"],
                redis=redis,
                id=sr.get("id"),
            )
            created_ids.append(result.id)
            print("  OK: Scenario rubric created successfully")

    return created_ids


async def _run_field_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    field_defs: list[dict],
) -> list[UUID]:
    """Run field seed definitions through create_field_impl."""
    from app.infra.field.create import CreateFieldItem, create_field_impl

    items = [CreateFieldItem(**f) for f in field_defs]

    result = await create_field_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "field_id") and r.field_id:
                created_ids.append(r.field_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_parameter_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    parameter_defs: list[dict],
) -> list[UUID]:
    """Run parameter seed definitions through create_parameter_impl."""
    from app.infra.parameter.create import (
        CreateParameterItem,
        create_parameter_impl,
    )

    items = [CreateParameterItem(**p) for p in parameter_defs]

    result = await create_parameter_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "parameter_id") and r.parameter_id:
                created_ids.append(r.parameter_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_objective_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    objective_defs: list[dict],
) -> list[UUID]:
    """Run objective seed definitions (resource-level create)."""
    from app.tools.resources.objectives.create import create_objective

    created_ids: list[UUID] = []
    for o in objective_defs:
        async with pool.acquire() as conn:
            result = await create_objective(
                conn,
                objective=o["objective"],
                redis=redis,
                id=o.get("id"),
            )
            created_ids.append(result.id)
            print("  OK: Objective created successfully")

    return created_ids


async def _run_question_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    question_defs: list[dict],
) -> list[UUID]:
    """Run question seed definitions (resource-level create)."""
    from app.tools.resources.questions.create import create_question

    created_ids: list[UUID] = []
    for q in question_defs:
        async with pool.acquire() as conn:
            result = await create_question(
                conn,
                question_text=q["question_text"],
                time=q["time"],
                redis=redis,
                id=q.get("id"),
                allow_multiple=q.get("allow_multiple", False),
            )
            created_ids.append(result.id)
            print("  OK: Question created successfully")

    return created_ids


async def _run_option_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    option_defs: list[dict],
) -> list[UUID]:
    """Run option seed definitions (resource-level create)."""
    from app.tools.resources.options.create import create_option

    created_ids: list[UUID] = []
    for o in option_defs:
        async with pool.acquire() as conn:
            result = await create_option(
                conn,
                option_text=o["option_text"],
                redis=redis,
                id=o.get("id"),
                question_id=o.get("question_id"),
            )
            created_ids.append(result.id)
            print("  OK: Option created successfully")

    return created_ids


async def _run_rubric_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    rubric_defs: list[dict],
) -> list[UUID]:
    """Run rubric seed definitions through create_rubric_impl."""
    from app.infra.rubric.create import CreateRubricItem, create_rubric_impl

    items = [CreateRubricItem(**r) for r in rubric_defs]

    result = await create_rubric_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "rubric_id") and r.rubric_id:
                created_ids.append(r.rubric_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_profile_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    profile_defs: list[dict],
) -> list[UUID]:
    """Run profile seed definitions through create_profile_impl."""
    from app.infra.profile.create import CreateProfileItem, create_profile_impl
    from app.tools.resources.emails.create import create_email

    # Resolve email string → email_ids before creation
    for p in profile_defs:
        email = p.pop("email", None)
        if email and not p.get("email_ids"):
            async with pool.acquire() as conn:
                email_resp = await create_email(conn, email=email, redis=redis)
            p["email_ids"] = [email_resp.id]

    items = [CreateProfileItem(**p) for p in profile_defs]

    result = await create_profile_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "profile_id") and r.profile_id:
                created_ids.append(r.profile_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_key_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    mod: object,
) -> None:
    """Run key_resources, provider_keys, auth_item_keys, and auth_item_values."""
    from app.tools.resources.auth_item_keys.create import create_auth_item_key
    from app.tools.resources.keys.create import create_key
    from app.tools.resources.provider_keys.create import create_provider_key

    async with pool.acquire() as conn:
        # Create key resources first (provider API keys + auth credentials)
        if hasattr(mod, "key_resources") and mod.key_resources:
            for kr in mod.key_resources:
                await create_key(conn, redis=redis, **kr)
            print(f"  OK: {len(mod.key_resources)} key_resources created")

        # Link providers to their API keys
        for pk in mod.provider_keys:
            await create_provider_key(conn, redis=redis, **pk)
        print(f"  OK: {len(mod.provider_keys)} provider_keys created")

        # Link auth items to encrypted keys
        for aik in mod.auth_item_keys:
            await create_auth_item_key(conn, redis=redis, **aik)
        print(f"  OK: {len(mod.auth_item_keys)} auth_item_keys created")

        # Plaintext auth config values
        if hasattr(mod, "auth_item_values") and mod.auth_item_values:
            from app.tools.resources.auth_item_values.create import create_auth_item_value
            for aiv in mod.auth_item_values:
                await create_auth_item_value(conn, redis=redis, **aiv)
            print(f"  OK: {len(mod.auth_item_values)} auth_item_values created")


async def _run_setting_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    setting_defs: list[dict],
) -> list[UUID]:
    """Run setting seed definitions through create_setting_impl."""
    from app.infra.setting.create import CreateSettingItem, create_setting_impl

    items = [CreateSettingItem(**s) for s in setting_defs]

    result = await create_setting_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "setting_id") and r.setting_id:
                created_ids.append(r.setting_id)
            print(f"  OK: {r.message}")

    return created_ids



async def _run_color_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    color_defs: list[dict],
) -> list[UUID]:
    """Run color seed definitions (resource-level create)."""
    from app.tools.resources.colors.create import create_color

    created_ids: list[UUID] = []
    for c in color_defs:
        async with pool.acquire() as conn:
            result = await create_color(
                conn,
                name=c["name"],
                description=c["description"],
                hex_code=c["hex_code"],
                redis=redis,
                id=c.get("id"),
            )
            created_ids.append(result.id)
            print("  OK: Color created successfully")

    return created_ids


def _get_assets_dir() -> Path:
    """Return the root uploads/ folder as the source for text/file seed assets."""
    assets_dir = PROJECT_ROOT / "uploads"
    if not assets_dir.exists():
        raise FileNotFoundError(
            f"Assets directory not found: {assets_dir}\n"
            f"Copy source text/PDF files into the uploads/ folder before generating setup templates."
        )
    return assets_dir


async def _run_text_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    document_text_defs: list[dict],
    assets_dir: Path,
) -> None:
    """Run text seed definitions using create_document_text + update_document.

    Creates a session, then for each document-text mapping:
      1. Reads source text file from assets_dir
      2. Calls create_document_text (full entry chain)
      3. Calls update_document to link text_ids
    """
    from app.infra.tools.entries.create_document_text import create_document_text
    from app.tools.artifacts.document.update import update_document
    from app.tools.entries.sessions.create import create_session

    # Create a temp upload folder for text file writes
    upload_folder = Path(tempfile.mkdtemp(prefix="seed_uploads_"))

    # Create a session for entry ownership (no profile link — avoids FK issues)
    async with pool.acquire() as conn:
        session = await create_session(conn)
    session_id = session.id

    for dt in document_text_defs:
        source_path = assets_dir / dt["source_file"]
        content = source_path.read_text(encoding="utf-8")

        async with pool.acquire() as conn:
            result = await create_document_text(
                conn,
                redis,
                content=content,
                session_id=session_id,
                upload_folder=upload_folder,
            )

        async with pool.acquire() as conn:
            await update_document(
                conn,
                dt["document_id"],
                text_ids=[result.texts_resource_id],
            )

        print(f"  OK: Text linked to document {dt['document_id']}")


async def _run_file_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    document_file_defs: list[dict],
    assets_dir: Path,
) -> None:
    """Run file seed definitions using create_document_file.

    Creates a session, then for each document-file mapping:
      1. Copies source file from assets_dir
      2. Calls create_document_file (full entry chain)
      3. Links result to document via document_files_junction
    """
    from app.infra.tools.entries.create_document_file import create_document_file
    from app.tools.artifacts.document.update import update_document
    from app.tools.entries.sessions.create import create_session

    # Create a temp upload folder for file copies
    upload_folder = Path(tempfile.mkdtemp(prefix="seed_uploads_"))

    # Create a session for entry ownership (no profile link — avoids FK issues)
    async with pool.acquire() as conn:
        session = await create_session(conn)
    session_id = session.id

    for df in document_file_defs:
        source_path = assets_dir / df["source_file"]

        async with pool.acquire() as conn:
            result = await create_document_file(
                conn,
                redis,
                source_path=source_path,
                mime_type=df["mime_type"],
                session_id=session_id,
                upload_folder=upload_folder,
            )

        async with pool.acquire() as conn:
            await update_document(
                conn,
                df["document_id"],
                file_ids=[result.files_resource_id],
            )

        print(f"  OK: File linked to document {df['document_id']}")


async def _cleanup_deactivated_junctions(pool: asyncpg.Pool) -> list[str]:
    """Collect deactivated junction rows and generate UPDATE SQL.

    The update pass uses upsert_multi which soft-deletes old junction rows
    (active=false). But pg_dump --on-conflict-do-nothing can't propagate
    that deactivation to a target DB that already has those rows as active.

    This function:
      1. Finds all deactivated junction rows
      2. Generates UPDATE SQL to deactivate them in the target DB
      3. Deletes them from the testcontainer (so pg_dump doesn't emit
         conflicting INSERT ... ON CONFLICT DO NOTHING for them)

    Returns a list of SQL UPDATE statements to append to the seed file.
    """
    update_stmts: list[str] = []

    async with pool.acquire() as conn:
        junction_tables = await conn.fetch(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename LIKE '%\\_junction'"
        )
        total = 0
        for row in junction_tables:
            table = row["tablename"]
            has_active = await conn.fetchval(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.columns "
                "  WHERE table_schema = 'public' "
                "    AND table_name = $1 "
                "    AND column_name = 'active'"
                ")",
                table,
            )
            if not has_active:
                continue

            # Get PK columns for this junction table
            pk_cols = await conn.fetch(
                "SELECT a.attname "
                "FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "  AND a.attnum = ANY(i.indkey) "
                "JOIN pg_class c ON c.oid = i.indrelid "
                "WHERE c.relname = $1 AND i.indisprimary "
                "ORDER BY array_position(i.indkey, a.attnum)",
                table,
            )
            pk_col_names = [r["attname"] for r in pk_cols]
            if not pk_col_names:
                continue

            # Fetch deactivated rows
            deactivated = await conn.fetch(
                f"SELECT {', '.join(pk_col_names)} "  # noqa: S608
                f"FROM {table} WHERE active = false"
            )
            if not deactivated:
                continue

            # Generate UPDATE statements
            for drow in deactivated:
                where_parts = [f"{col} = '{drow[col]}'" for col in pk_col_names]
                where_clause = " AND ".join(where_parts)
                update_stmts.append(
                    f"UPDATE public.{table} SET active = false WHERE {where_clause};"
                )

            # Delete from testcontainer so pg_dump won't emit conflicting INSERTs
            result = await conn.execute(
                f"DELETE FROM {table} WHERE active = false"  # noqa: S608
            )
            count = int(result.split()[-1])
            total += count

        if total:
            print(f"  Cleaned up {total} deactivated junction row(s)")

    return update_stmts


async def _run_cohort_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    cohort_defs: list[dict],
) -> list[UUID]:
    """Run cohort seed definitions through create_cohort_impl."""
    from app.infra.cohort.create import CreateCohortItem, create_cohort_impl

    items = [CreateCohortItem(**c) for c in cohort_defs]

    result = await create_cohort_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        items=items,
    )

    created_ids: list[UUID] = []
    for r in result.results:
        if not r.success:
            print(f"  ERROR: {r.message}")
            if hasattr(r, "errors") and r.errors:
                for e in r.errors:
                    print(f"    - {e.field}: {e.message}")
        else:
            if hasattr(r, "cohort_id") and r.cohort_id:
                created_ids.append(r.cohort_id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_profile_persona_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    profile_persona_defs: list[dict],
) -> list[UUID]:
    """Run profile-persona seed definitions through create_profile_persona."""
    from app.tools.resources.profile_personas.create import create_profile_persona

    created_ids: list[UUID] = []
    async with pool.acquire() as conn:
        for pp in profile_persona_defs:
            try:
                result = await create_profile_persona(
                    conn,
                    profile_id=pp["profile_id"],
                    persona_id=pp["persona_id"],
                    redis=redis,
                    id=pp.get("id"),
                )
                created_ids.append(result.id)
                print(f"  OK: Profile persona created successfully")
            except Exception as e:
                print(f"  ERROR: {e}")

    return created_ids


# ---------------------------------------------------------------------------
# Tool seed execution (static definitions from tools_data.py)
# ---------------------------------------------------------------------------


async def _run_tool_instruction_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Create tool response template instructions before tools."""
    from app.tools.resources.instructions.create import create_instruction
    from database.seeds.tool_instructions import get_tool_instructions

    instructions = get_tool_instructions()
    if not instructions:
        print("  (no tool instructions to seed)")
        return

    async with pool.acquire() as conn:
        for i in instructions:
            await create_instruction(conn, template=i["template"], redis=redis, id=i["id"])
    print(f"  OK: {len(instructions)} tool instructions created")


async def _run_tool_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Create tools from static definitions in tools_data.py."""
    from app.infra.tool.create import CreateToolItem, create_tool_impl
    from database.seeds.resources.args import SHARED_ARGS
    from database.seeds.resources.args_outputs import SHARED_ARGS_OUTPUTS
    from database.seeds.tools import tools

    print(f"  Loading {len(tools)} tool definitions.")

    created = 0
    errors = 0

    for tool_def in tools:
        # Resolve arg keys → arg IDs from shared vocabulary
        arg_ids: list[UUID] = []
        for arg_key in tool_def.get("args", []):
            if arg_key in SHARED_ARGS:
                arg_ids.append(SHARED_ARGS[arg_key]["id"])
            else:
                print(f"  WARNING: Unknown arg key '{arg_key}' in tool '{tool_def['name']}'")

        # Resolve args_output keys → args_output IDs from shared vocabulary
        args_output_ids: list[UUID] = []
        for ao_key in tool_def.get("args_outputs", []):
            if ao_key in SHARED_ARGS_OUTPUTS:
                args_output_ids.append(SHARED_ARGS_OUTPUTS[ao_key]["id"])
            else:
                print(f"  WARNING: Unknown args_output key '{ao_key}' in tool '{tool_def['name']}'")

        # Create tool via create_tool_impl
        item = CreateToolItem(
            id=tool_def["id"],
            resource_id=tool_def.get("resource_id"),
            name=tool_def["name"],
            description=tool_def["description"],
            args_ids=arg_ids if arg_ids else None,
            args_outputs_ids=args_output_ids if args_output_ids else None,
            permission_ids=tool_def["permission_ids"],
            instruction_id=tool_def.get("instruction_id"),
        )

        try:
            result = await create_tool_impl(
                pool,
                redis,
                profile_id=SEED_PROFILE_ID,
                items=[item],
            )
            for r in result.results:
                if r.success:
                    created += 1
                else:
                    errors += 1
                    print(f"  ERROR: {tool_def['name']}: {r.message}")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {tool_def['name']}: {e}")

    print(f"  OK: {created} tools created, {errors} errors")


# ---------------------------------------------------------------------------
# SQL dump — pg_dump the testcontainer database
# ---------------------------------------------------------------------------


def _psql_load_file(pg: PostgresContainer, sql_file: Path) -> None:
    """Load a SQL file (including COPY format) via psql subprocess.

    asyncpg cannot handle pg_dump COPY format, so we shell out to psql.
    Wraps the file with session_replication_role = replica to disable FK checks.
    """
    pg_host = pg.get_container_host_ip()
    pg_port = pg.get_exposed_port(5432)
    pg_user = pg.username
    pg_password = pg.password
    pg_dbname = pg.dbname

    env = {**os.environ, "PGPASSWORD": pg_password}

    cmd = [
        "psql",
        f"--host={pg_host}",
        f"--port={pg_port}",
        f"--username={pg_user}",
        f"--dbname={pg_dbname}",
        "--quiet",
        "-v",
        "ON_ERROR_STOP=0",
    ]

    sql = (
        "SET session_replication_role = replica;\n"
        + sql_file.read_text()
        + "\nSET session_replication_role = DEFAULT;\n"
    )

    result = subprocess.run(cmd, input=sql, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        print(f"  psql FAILED: {result.stderr}")
        raise RuntimeError(f"psql failed: {result.stderr}")


def _pg_dump_data(
    pg: PostgresContainer,
    output_file: Path,
    label: str,
    exclude_tables: set[str] | None = None,
    on_conflict_do_nothing: bool = False,
) -> None:
    """Dump data from testcontainer DB using pg_dump --data-only.

    Uses pg_dump directly against the container, producing clean SQL
    that PostgreSQL itself generates.

    Args:
        exclude_tables: Tables to exclude from the dump (e.g., pre-loaded data).
        on_conflict_do_nothing: Use INSERT ... ON CONFLICT DO NOTHING instead
            of COPY. Useful for setup seeds that overlap with base-seed data.
    """
    # Extract connection params from the testcontainer
    pg_host = pg.get_container_host_ip()
    pg_port = pg.get_exposed_port(5432)
    pg_user = pg.username
    pg_password = pg.password
    pg_dbname = pg.dbname

    env = {**os.environ, "PGPASSWORD": pg_password}

    cmd = [
        "pg_dump",
        "--data-only",
        "--schema=public",
        "--no-owner",
        "--no-privileges",
        "--disable-triggers",
        f"--host={pg_host}",
        f"--port={pg_port}",
        f"--username={pg_user}",
        f"--dbname={pg_dbname}",
    ]

    if on_conflict_do_nothing:
        cmd.extend(["--inserts", "--on-conflict-do-nothing"])

    for table in sorted(exclude_tables or []):
        cmd.append(f"--exclude-table-data=public.{table}")

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        print(f"  pg_dump FAILED: {result.stderr}")
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    # Write with a header
    header = (
        f"-- {label}\n"
        "-- Generated by: database/seeds/runner.py (pg_dump --data-only)\n"
        "-- ============================================================\n\n"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(header + result.stdout)

    # Count data statements for summary
    if on_conflict_do_nothing:
        stmt_count = result.stdout.count("\nINSERT INTO ")
        print(f"  Wrote {output_file} ({stmt_count} inserts, ON CONFLICT DO NOTHING)")
    else:
        copy_count = result.stdout.count("\nCOPY ")
        line_count = result.stdout.count("\n")
        print(f"  Wrote {output_file} ({copy_count} tables, {line_count} lines)")


def _pg_dump_full(
    pg: PostgresContainer,
    output_file: Path,
    label: str,
) -> None:
    """Full pg_dump (schema + data) → gzipped SQL in history/.

    Produces a self-contained .sql.gz that can be loaded with:
        gunzip -c file.sql.gz | psql <conn>
    """
    import gzip

    pg_host = pg.get_container_host_ip()
    pg_port = pg.get_exposed_port(5432)
    pg_user = pg.username
    pg_password = pg.password
    pg_dbname = pg.dbname

    env = {**os.environ, "PGPASSWORD": pg_password}

    cmd = [
        "pg_dump",
        "--format=plain",
        "--no-owner",
        "--no-privileges",
        "--exclude-schema=keycloak",
        f"--host={pg_host}",
        f"--port={pg_port}",
        f"--username={pg_user}",
        f"--dbname={pg_dbname}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        print(f"  pg_dump FAILED: {result.stderr}")
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    header = (
        f"-- {label}\n"
        "-- Generated by: database/scripts/runner.py (pg_dump full)\n"
        "-- ============================================================\n\n"
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_file, "wt", encoding="utf-8") as f:
        f.write(header + result.stdout)

    size_kb = output_file.stat().st_size / 1024
    print(f"  Wrote {output_file} ({size_kb:.0f} KB)")


def _discover_setups() -> list[str]:
    """Auto-discover setup templates from database/seeds/setups/.

    Any subdirectory with an __init__.py defining SETUP_NAME and MODULES
    is a valid setup template.
    """
    setups_dir = SEEDS_DIR / "setups"
    return sorted(
        d.name
        for d in setups_dir.iterdir()
        if d.is_dir()
        and (d / "__init__.py").exists()
        and d.name != "__pycache__"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


_active_containers: list = []
_cleanup_registered = False


def _cleanup_containers():
    """Stop all active testcontainers — registered via atexit for crash safety."""
    for c in _active_containers:
        try:
            c.stop()
        except Exception:
            pass
    _active_containers.clear()


async def _start_containers() -> tuple:
    """Start Postgres and Redis testcontainers, return (pg, pg_url, redis_container, redis_url)."""
    global _cleanup_registered

    if not _cleanup_registered:
        import atexit
        atexit.register(_cleanup_containers)
        _cleanup_registered = True

    print("Starting Postgres container...")
    pg = PostgresContainer("postgres:18")
    pg.start()
    _active_containers.append(pg)
    pg_url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")

    print("Starting Redis container...")
    redis_container = RedisContainer("redis:7-alpine")
    redis_container.start()
    _active_containers.append(redis_container)
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)
    redis_url = f"redis://{redis_host}:{redis_port}/0"

    return pg, pg_url, redis_container, redis_url


async def _load_schema(conn: asyncpg.Connection) -> None:
    """Load schema into the database."""
    print("Loading schema...")
    await conn.execute("""
        CREATE SCHEMA IF NOT EXISTS keycloak;
        CREATE TABLE IF NOT EXISTS keycloak.org (id text PRIMARY KEY, alias text);
        CREATE TABLE IF NOT EXISTS keycloak.realm (name text PRIMARY KEY, ssl_required text);
    """)
    schema_sql = _filter_meta_commands(_concat_schema(SCHEMA_DIR))
    await conn.execute(schema_sql)
    print("  Schema loaded.")


async def _refresh_mvs(conn: asyncpg.Connection) -> None:
    """Refresh all unpopulated materialized views."""
    print("Refreshing materialized views...")
    unpopulated = await conn.fetch(
        "SELECT matviewname FROM pg_matviews WHERE NOT ispopulated"
    )
    for row in unpopulated:
        await conn.execute(f'REFRESH MATERIALIZED VIEW "{row["matviewname"]}"')
    print(f"  {len(unpopulated)} MVs refreshed.")


async def main_setup(setup: str = "university") -> None:
    """Seed a fully independent setup — base modules + setup-specific data.

    Each setup is self-contained: it creates ALL platform resources,
    bootstraps its own superadmin profile, then seeds setup-specific data.
    No base-seed.sql, no shared state between setups.

    Args:
        setup: Name of the setup to seed (must match a directory in seeds/setups/).
    """
    print(f"=== Seed Runner: {setup} ===\n")

    pg, pg_url, redis_container, redis_url = await _start_containers()

    try:
        conn = await asyncpg.connect(pg_url)
        await _load_schema(conn)
        await _refresh_mvs(conn)
        await conn.close()

        pool = await asyncpg.create_pool(pg_url)
        redis_client = Redis.from_url(redis_url)

        os.environ.setdefault("SECRET_KEY", "seed_runner_secret_key")
        os.environ.setdefault("AUTH_SECRET", "seed_runner_auth_secret")

        setup_module = importlib.import_module(f"database.seeds.setups.{setup}")

        # Disable FK checks for all creates (base + setup)
        async with pool.acquire() as conn:
            dbname = await conn.fetchval("SELECT current_database()")
            await conn.execute(
                f"ALTER DATABASE {dbname} SET session_replication_role = 'replica'"
            )
        await pool.close()
        pool = await asyncpg.create_pool(pg_url)
        print("  FK checks disabled")

        # ── Phase 1: Base platform modules ────────────────────────────
        # These are shared definitions — every setup creates them.

        print("\nSeeding base resources...")
        await _run_resource_seeds(pool, redis_client)

        # Bootstrap the setup's superadmin (for _impl profile_id)
        print("\nBootstrapping setup profile...")
        bootstrap = setup_module.BOOTSTRAP_PROFILE
        seed_profile_id = bootstrap["id"]
        from app.tools.artifacts.profile.create import (
            create_profile as create_profile_artifact,
        )
        from app.tools.resources.emails.create import create_email as create_email_resource
        from app.tools.resources.names.create import create_name
        from app.tools.resources.profiles.create import (
            create_profile as create_profile_resource,
        )
        async with pool.acquire() as conn:
            async with conn.transaction():
                name_resp = await create_name(conn, name=bootstrap["name"], redis=redis_client)
                email_ids = None
                if bootstrap.get("email"):
                    email_resp = await create_email_resource(conn, email=bootstrap["email"], redis=redis_client)
                    email_ids = [email_resp.id]
                profile_resource = await create_profile_resource(
                    conn, redis_client,
                    id=bootstrap.get("resource_id"),
                    name=bootstrap["name"],
                    department_ids=bootstrap.get("department_ids"),
                    role_id=bootstrap.get("role_id"),
                    emails=[bootstrap["email"]] if bootstrap.get("email") else None,
                    primary_email=bootstrap.get("email"),
                )
                await create_profile_artifact(
                    conn,
                    id=bootstrap["id"],
                    name_id=name_resp.id,
                    role_ids=[bootstrap["role_id"]] if bootstrap.get("role_id") else None,
                    flag_ids=bootstrap.get("flag_ids"),
                    profile_ids=[profile_resource.id],
                    email_ids=email_ids,
                    department_ids=bootstrap.get("department_ids"),
                    redis=redis_client,
                )
        print(f"  OK: {bootstrap['name']} bootstrapped ({seed_profile_id})")

        # Override SEED_PROFILE_ID for all _impl calls in this setup
        global SEED_PROFILE_ID
        original_seed_profile_id = SEED_PROFILE_ID
        SEED_PROFILE_ID = seed_profile_id

        print("\nSeeding providers...")
        await _run_provider_module_seeds(pool, redis_client)

        print("\nSeeding dynamic model resources...")
        from database.seeds.models import dynamic_pricing, dynamic_voices
        async with pool.acquire() as conn:
            if dynamic_pricing:
                await _seed_pricing(conn, redis_client, dynamic_pricing)
            if dynamic_voices:
                await _seed_voices(conn, redis_client, dynamic_voices)

        print("\nSeeding models...")
        await _run_model_module_seeds(pool, redis_client)

        print("\nSeeding prompts + instructions...")
        await _run_prompt_and_instruction_seeds(pool, redis_client)

        print("\nSeeding agents...")
        await _run_agent_module_seeds(pool, redis_client)

        print("\nSeeding auth...")
        await _run_auth_module_seeds(pool, redis_client)

        print("\nSeeding evals...")
        await _run_eval_module_seeds(pool, redis_client)

        print("\nSeeding systems...")
        await _run_system_module_seeds(pool, redis_client)

        print("\nSeeding rubrics...")
        await _run_rubric_module_seeds(pool, redis_client)

        print("\nSeeding tool instructions...")
        await _run_tool_instruction_seeds(pool, redis_client)

        print("\nSeeding tools...")
        await _run_tool_module_seeds(pool, redis_client)

        print("\nSeeding dynamic keys...")
        import database.seeds.dynamic_keys as dk_mod
        await _run_key_seeds(pool, redis_client, dk_mod)

        # ── Phase 2: Setup-specific modules ───────────────────────────

        for module_name in setup_module.MODULES:
            print(f"\nSeeding {module_name}...")
            mod = importlib.import_module(
                f"database.seeds.setups.{setup}.{module_name}"
            )

            if module_name == "departments":
                await _run_department_seeds(pool, redis_client, mod.departments)
            elif module_name == "documents":
                await _run_document_seeds(pool, redis_client, mod.documents)
            elif module_name == "personas":
                await _run_persona_seeds(pool, redis_client, mod.personas)
            elif module_name == "scenarios":
                await _run_scenario_seeds(pool, redis_client, mod.scenarios)
            elif module_name == "rubrics":
                await _run_rubric_seeds(pool, redis_client, mod.rubrics)
            elif module_name == "fields":
                await _run_field_seeds(pool, redis_client, mod.fields)
            elif module_name == "parameters":
                await _run_parameter_seeds(pool, redis_client, mod.parameters)
            elif module_name == "scenario_rubrics":
                await _run_scenario_rubric_seeds(
                    pool, redis_client, mod.scenario_rubrics
                )
            elif module_name == "content":
                await _run_objective_seeds(pool, redis_client, mod.objectives)
                await _run_question_seeds(pool, redis_client, mod.questions)
                await _run_option_seeds(pool, redis_client, mod.options)
            elif module_name == "simulations":
                await _run_simulation_seeds(pool, redis_client, mod.simulations)
            elif module_name == "cohorts":
                await _run_cohort_seeds(pool, redis_client, mod.cohorts)
            elif module_name == "profiles":
                if hasattr(mod, "profiles"):
                    await _run_profile_seeds(pool, redis_client, mod.profiles)
                if hasattr(mod, "setup_profiles"):
                    await _run_profile_seeds(pool, redis_client, mod.setup_profiles)
            elif module_name == "profile_personas":
                await _run_profile_persona_seeds(
                    pool, redis_client, mod.profile_personas
                )
            elif module_name == "keys":
                await _run_key_seeds(pool, redis_client, mod)
            elif module_name == "settings":
                await _run_setting_seeds(pool, redis_client, mod.settings)
            elif module_name == "colors":
                await _run_color_seeds(pool, redis_client, mod.colors)
            elif module_name == "texts":
                assets_dir = _get_assets_dir()
                await _run_text_seeds(
                    pool, redis_client, mod.document_texts, assets_dir
                )
            elif module_name == "files":
                assets_dir = _get_assets_dir()
                await _run_file_seeds(
                    pool, redis_client, mod.document_files, assets_dir
                )

        # Restore original SEED_PROFILE_ID
        SEED_PROFILE_ID = original_seed_profile_id

        # Re-enable FK checks
        async with pool.acquire() as conn:
            dbname = await conn.fetchval("SELECT current_database()")
            await conn.execute(
                f"ALTER DATABASE {dbname} RESET session_replication_role"
            )
        await pool.close()
        pool = await asyncpg.create_pool(pg_url)
        print("\n  FK checks re-enabled")

        await redis_client.aclose()
        await pool.close()

        # Full dump → history/{setup}.sql.gz
        history_dir = DATABASE_DIR.parent / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nGenerating template: {setup}...")
        _pg_dump_full(
            pg,
            history_dir / f"{setup}.sql.gz",
            f"Template: {setup} (fully independent)",
        )

    finally:
        pg.stop()
        redis_container.stop()

    print("\nDone!")


async def main_all() -> None:
    """Seed all discovered setups independently.

    Each setup creates everything from scratch — base platform resources
    + setup-specific data. No shared base-seed.sql.
    """
    setups = _discover_setups()
    print(f"Discovered setups: {', '.join(setups)}\n")

    for setup in setups:
        await main_setup(setup)

    history_dir = DATABASE_DIR.parent / "history"
    templates = sorted(f.name for f in history_dir.glob("*.sql.gz"))
    print(f"\n=== Templates regenerated: {', '.join(templates)} ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run seed definitions")
    parser.add_argument(
        "--setup", default=None, help="Setup name (auto-discovered from seeds/setups/)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Seed all setups → history/*.sql.gz",
    )
    args = parser.parse_args()

    if args.all:
        asyncio.run(main_all())
    else:
        asyncio.run(main_setup(args.setup or "university"))
