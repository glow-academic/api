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

# testcontainers is a dev-only dep — only needed for the dump-mode path
# that spins up throwaway pg + redis to produce history/*.sql.gz. The
# in-place mode (used by the `db-init` compose service in production)
# seeds the live DB directly and never needs it. Import lazily so the
# runner can run inside the production api image, which doesn't ship
# testcontainers.
try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer
except ModuleNotFoundError:
    PostgresContainer = None  # type: ignore[assignment,misc]
    RedisContainer = None  # type: ignore[assignment,misc]

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
        # Don't pop — Python caches imports, so this items list is shared
        # across setup iterations. Mutating it makes subsequent setups fall
        # through to the default. Same fix applied to _seed_flags in 69ff2fc1.
        clean = {k: v for k, v in item.items() if k != "type"}
        color_type = item.get("type", "primary")
        await create_color(conn, redis=redis, color_type=color_type, **clean)
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
        clean = {k: v for k, v in item.items() if k != "type"}
        threshold_type = item.get("type", "success")
        await create_threshold(conn, redis=redis, threshold_type=threshold_type, **clean)
    print(f"  OK: {len(items)} thresholds created")


async def _seed_points(
    conn: asyncpg.Connection, redis: Redis, items: list[dict]
) -> None:
    from app.tools.resources.points.create import create_point

    for item in items:
        clean = {k: v for k, v in item.items() if k != "type"}
        point_type = item.get("type", "total")
        await create_point(conn, redis=redis, point_type=point_type, **clean)
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
    from app.infra.provider.create import create_provider_impl
    from app.infra.provider.types import CreateProviderApiRequest, CreateProviderItem
    from database.seeds.providers import providers

    items = [CreateProviderItem(**d) for d in providers]
    await create_provider_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateProviderApiRequest(providers=items),
    )
    print(f"  OK: {len(providers)} providers created")


async def _run_model_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 03 — Create models via _impl."""
    from app.infra.model.create import create_model_impl
    from app.infra.model.types import CreateModelApiRequest, CreateModelItem
    from database.seeds.models import models

    items = [CreateModelItem(**d) for d in models]
    await create_model_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateModelApiRequest(models=items),
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
    default_department_ids: list | None = None,
) -> None:
    """Module 04 — Create agents via _impl.

    `default_department_ids` is the setup-specific fallback applied to
    every agent dict that doesn't already carry its own department_ids.
    Without this, search_agents filters on
    `agent.department_ids && user.department_ids` and excludes every
    agent for any departmented user (pickers like Setting's Systems/MCP
    go empty).
    """
    from app.infra.agent.create import create_agent_impl
    from app.infra.agent.types import CreateAgentApiRequest, CreateAgentItem
    from database.seeds.agents import agents

    items: list[CreateAgentItem] = []
    for d in agents:
        merged = dict(d)
        if default_department_ids and not merged.get("department_ids"):
            merged["department_ids"] = list(default_department_ids)
        items.append(CreateAgentItem(**merged))
    await create_agent_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateAgentApiRequest(agents=items),
    )
    print(f"  OK: {len(agents)} agents created")


async def _run_auth_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 06 — Create auths via _impl."""
    from app.infra.auth.create import create_auth_impl
    from app.infra.auth.types import CreateAuthApiRequest, CreateAuthItem
    from database.seeds.auths import auths

    items = [CreateAuthItem(**d) for d in auths]
    await create_auth_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateAuthApiRequest(auths=items),
    )
    print(f"  OK: {len(auths)} auths created")


async def _run_model_flag_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 07a — Create model_flags_resource rows.

    Pre-creates one (model, use_custom=true) row per seeded model so the
    eval module's eval_model_flags_junction inserts FK-resolve. Calls the
    black-box `create_model_flag` helper, which is idempotent on explicit
    id (ON CONFLICT DO UPDATE).
    """
    from app.tools.resources.model_flags.create import create_model_flag
    from database.seeds.model_flags import model_flags

    async with pool.acquire() as conn:
        for row in model_flags:
            await create_model_flag(
                conn,
                row["model_id"],
                row["flag_id"],
                redis,
                id=row["id"],
            )
    print(f"  OK: {len(model_flags)} model_flags created")


async def _run_model_rubric_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 07b — Create model_rubrics_resource rows.

    Pre-creates one (model, rubric) row per (model × rubric-used-by-eval)
    pair so the eval module's eval_model_rubrics_junction inserts
    FK-resolve. Calls the black-box `create_model_rubric` helper.
    """
    from app.tools.resources.model_rubrics.create import create_model_rubric
    from database.seeds.model_rubrics import model_rubrics

    async with pool.acquire() as conn:
        for row in model_rubrics:
            await create_model_rubric(
                conn,
                row["model_id"],
                row["rubric_id"],
                redis,
                id=row["id"],
            )
    print(f"  OK: {len(model_rubrics)} model_rubrics created")


async def _run_model_position_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 07c — Create model_positions_resource rows.

    Pre-creates one (model, value=index) row per (model × eval) pair so the
    eval module's eval_model_positions_junction inserts FK-resolve. Calls
    the black-box `create_model_position` helper.
    """
    from app.tools.resources.model_positions.create import create_model_position
    from database.seeds.model_positions import model_positions

    async with pool.acquire() as conn:
        for row in model_positions:
            await create_model_position(
                conn,
                row["model_id"],
                row["value"],
                redis,
                id=row["id"],
            )
    print(f"  OK: {len(model_positions)} model_positions created")


async def _run_eval_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Module 08 — Create evals via _impl."""
    from app.infra.eval.create import create_eval_impl
    from app.infra.eval.types import CreateEvalApiRequest, CreateEvalItem
    from database.seeds.evals import evals

    items = [CreateEvalItem(**d) for d in evals]
    await create_eval_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateEvalApiRequest(evals=items),
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
    from app.infra.rubric.create import create_rubric_impl
    from app.infra.rubric.types import CreateRubricApiRequest, CreateRubricItem
    from database.seeds.rubrics import rubrics

    items = [CreateRubricItem(**d) for d in rubrics]
    result = await create_rubric_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateRubricApiRequest(rubrics=items),
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
    from app.infra.document.create import create_document_impl
    from app.infra.document.types import CreateDocumentApiRequest, CreateDocumentItem

    items = [CreateDocumentItem(**d) for d in document_defs]

    result = await create_document_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateDocumentApiRequest(documents=items),
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
    from app.infra.department.create import create_department_impl
    from app.infra.department.types import CreateDepartmentApiRequest, CreateDepartmentItem

    items = [CreateDepartmentItem(**d) for d in department_defs]

    result = await create_department_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateDepartmentApiRequest(departments=items),
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
    from app.infra.persona.create import create_persona_impl
    from app.infra.persona.types import CreatePersonaApiRequest, CreatePersonaItem

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
            if hasattr(r, "id") and r.id:
                created_ids.append(r.id)
            print(f"  OK: {r.message}")

    return created_ids


async def _run_scenario_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    scenario_defs: list[dict],
) -> list[UUID]:
    """Run scenario seed definitions through create_scenario_impl."""
    from app.infra.scenario.create import create_scenario_impl
    from app.infra.scenario.types import CreateScenarioApiRequest, CreateScenarioItem

    items = [CreateScenarioItem(**s) for s in scenario_defs]

    result = await create_scenario_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateScenarioApiRequest(scenarios=items),
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
    from app.infra.simulation.create import create_simulation_impl
    from app.infra.simulation.types import CreateSimulationApiRequest, CreateSimulationItem

    items = [CreateSimulationItem(**s) for s in simulation_defs]

    result = await create_simulation_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateSimulationApiRequest(simulations=items),
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
    from app.infra.field.create import create_field_impl
    from app.infra.field.types import CreateFieldApiRequest, CreateFieldItem

    items = [CreateFieldItem(**f) for f in field_defs]

    result = await create_field_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateFieldApiRequest(fields=items),
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


async def _run_conditional_parameter_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    conditional_parameter_defs: list[dict],
) -> list[UUID]:
    """Create conditional_parameters_resource entries."""
    from app.tools.resources.conditional_parameters.create import create_conditional_parameter

    created_ids: list[UUID] = []
    async with pool.acquire() as conn:
        for cp in conditional_parameter_defs:
            result = await create_conditional_parameter(
                conn,
                parameter_id=cp["parameter_id"],
                redis=redis,
                id=cp["id"],
            )
            created_ids.append(result.id)
    print(f"  OK: {len(created_ids)} conditional parameters created")
    return created_ids


async def _run_parameter_field_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    parameter_field_defs: list[dict],
) -> list[UUID]:
    """Create parameter_fields_resource entries linking parameters to fields."""
    from app.tools.resources.parameter_fields.create import create_parameter_field

    created_ids: list[UUID] = []
    async with pool.acquire() as conn:
        for pf in parameter_field_defs:
            result = await create_parameter_field(
                conn,
                field_id=pf["field_id"],
                parameter_id=pf["parameter_id"],
                redis=redis,
                id=pf["id"],
            )
            created_ids.append(result.id)
    print(f"  OK: {len(created_ids)} parameter fields created")
    return created_ids


async def _run_parameter_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    parameter_defs: list[dict],
) -> list[UUID]:
    """Run parameter seed definitions through create_parameter_impl."""
    from app.infra.parameter.create import create_parameter_impl
    from app.infra.parameter.types import CreateParameterApiRequest, CreateParameterItem

    items = [CreateParameterItem(**p) for p in parameter_defs]

    result = await create_parameter_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateParameterApiRequest(parameters=items),
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
    from app.infra.rubric.create import create_rubric_impl
    from app.infra.rubric.types import CreateRubricApiRequest, CreateRubricItem

    items = [CreateRubricItem(**r) for r in rubric_defs]

    result = await create_rubric_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateRubricApiRequest(rubrics=items),
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
    from app.infra.profile.create import create_profile_impl
    from app.infra.profile.types import CreateProfileApiRequest, CreateProfileItem
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
        request=CreateProfileApiRequest(profiles=items),
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


async def _seed_logins(
    pool: asyncpg.Pool,
    redis: Redis,
    login_defs: list[dict],
) -> list[UUID]:
    """Create logins_resource entries from login definitions."""
    from app.tools.resources.logins.create import create_logins

    created_ids: list[UUID] = []
    async with pool.acquire() as conn:
        for lg in login_defs:
            result = await create_logins(
                conn,
                id=lg.get("id"),
                profile_id=lg.get("profile_id"),
                auth_id=lg.get("auth_id"),
                icon_id=lg.get("icon_id"),
                display_name=lg.get("display_name", ""),
                login_type=lg.get("login_type", "auth"),
                redis=redis,
            )
            created_ids.append(result.id)
    print(f"  OK: {len(created_ids)} logins created")
    return created_ids


async def _run_setting_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    setting_defs: list[dict],
) -> list[UUID]:
    """Run setting seed definitions through create_setting_impl."""
    from app.infra.setting.create import create_setting_impl
    from app.infra.setting.types import CreateSettingApiRequest, CreateSettingItem

    items = [CreateSettingItem(**s) for s in setting_defs]

    result = await create_setting_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateSettingApiRequest(settings=items),
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
                color_type=c.get("type", "primary"),
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
    from app.tools.entries.sessions.create import create_session

    # Use the project uploads/ dir so text files survive seed generation
    upload_folder = assets_dir
    upload_folder.mkdir(parents=True, exist_ok=True)

    # Create a session for entry ownership (no profile link — avoids FK issues)
    async with pool.acquire() as conn:
        session = await create_session(conn, redis)
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
                texts_resource_id=dt.get("texts_resource_id"),
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
    from app.tools.entries.sessions.create import create_session

    # Use the project uploads/ dir so UUID-named copies survive seed generation
    # and are available at runtime when the template is loaded.
    upload_folder = assets_dir
    upload_folder.mkdir(parents=True, exist_ok=True)

    # Create a session for entry ownership (no profile link — avoids FK issues)
    async with pool.acquire() as conn:
        session = await create_session(conn, redis)
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
                files_resource_id=df.get("files_resource_id"),
            )

        print(f"  OK: File linked to document {df['document_id']}")


async def _run_video_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    scenario_video_defs: list[dict],
    assets_dir: Path,
) -> None:
    """Run video seed definitions using create_scenario_video."""
    from app.infra.tools.entries.create_scenario_video import create_scenario_video
    from app.tools.entries.sessions.create import create_session

    upload_folder = assets_dir
    upload_folder.mkdir(parents=True, exist_ok=True)

    async with pool.acquire() as conn:
        session = await create_session(conn, redis)
    session_id = session.id

    for sv in scenario_video_defs:
        source_path = assets_dir / sv["source_file"]

        async with pool.acquire() as conn:
            await create_scenario_video(
                conn,
                redis,
                source_path=source_path,
                mime_type=sv["mime_type"],
                session_id=session_id,
                upload_folder=upload_folder,
                videos_resource_id=sv.get("videos_resource_id"),
                name=sv.get("name", ""),
                description=sv.get("description", ""),
                length_seconds=sv.get("length_seconds", 0),
            )

        print(f"  OK: Video linked to scenario {sv['scenario_id']}")


async def _run_image_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
    standalone_image_defs: list[dict],
    document_image_defs: list[dict],
    assets_dir: Path,
) -> None:
    """Run image seed definitions using create_document_image."""
    from app.infra.tools.entries.create_document_image import create_document_image
    from app.tools.entries.sessions.create import create_session

    upload_folder = assets_dir
    upload_folder.mkdir(parents=True, exist_ok=True)

    async with pool.acquire() as conn:
        session = await create_session(conn, redis)
    session_id = session.id

    for si in standalone_image_defs:
        source_path = assets_dir / si["source_file"]

        async with pool.acquire() as conn:
            await create_document_image(
                conn,
                redis,
                source_path=source_path,
                mime_type=si["mime_type"],
                session_id=session_id,
                upload_folder=upload_folder,
                images_resource_id=si.get("images_resource_id"),
                name=si.get("name", ""),
                description=si.get("description", ""),
            )

        print(f"  OK: Standalone image created: {si.get('name', '')}")

    for di in document_image_defs:
        source_path = assets_dir / di["source_file"]

        async with pool.acquire() as conn:
            await create_document_image(
                conn,
                redis,
                source_path=source_path,
                mime_type=di["mime_type"],
                session_id=session_id,
                upload_folder=upload_folder,
                images_resource_id=di.get("images_resource_id"),
                name=di.get("name", ""),
                description=di.get("description", ""),
            )

        print(f"  OK: Image linked to document {di['document_id']}")


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
    from app.infra.cohort.create import create_cohort_impl
    from app.infra.cohort.types import CreateCohortApiRequest, CreateCohortItem

    items = [CreateCohortItem(**c) for c in cohort_defs]

    result = await create_cohort_impl(
        pool,
        redis,
        profile_id=SEED_PROFILE_ID,
        request=CreateCohortApiRequest(cohorts=items),
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


async def _run_mcp_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Create mcp_resource rows. Runs after agents (FK is an agents_resource id)
    and before the setup-specific loop that seeds settings referencing them."""
    from app.tools.resources.mcp.create import create_mcp
    from database.seeds.mcps import mcp_resources

    async with pool.acquire() as conn:
        for m in mcp_resources:
            await create_mcp(
                conn,
                agent_id=m["agent_id"],
                name=m["name"],
                description=m["description"],
                id=m["id"],
                redis=redis,
            )
    print(f"  OK: {len(mcp_resources)} mcp resources created")


async def _run_tool_module_seeds(
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Create tools from static definitions in tools_data.py."""
    from app.infra.tool.create import create_tool_impl
    from app.infra.tool.types import CreateToolApiRequest, CreateToolItem
    from database.seeds.resources.args import SHARED_ARGS
    from database.seeds.resources.args_outputs import SHARED_ARGS_OUTPUTS
    from database.seeds.tools import tools

    print(f"  Loading {len(tools)} tool definitions.")

    created = 0
    errors = 0
    _total = len(tools)
    _last_progress_pct = -1

    for _idx, tool_def in enumerate(tools):
        # Progress every 10% — 330 tools × ~50ms each is ~15-30s of
        # otherwise-silent work; emit a heartbeat so it doesn't look hung.
        _pct = int(_idx * 10 / _total)
        if _pct != _last_progress_pct:
            _last_progress_pct = _pct
            print(
                f"  ... {_idx}/{_total} tools processed",
                flush=True,
            )
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
            agent_id=tool_def.get("agent_id"),
            instruction_id=tool_def.get("instruction_id"),
        )

        try:
            result = await create_tool_impl(
                pool,
                redis,
                profile_id=SEED_PROFILE_ID,
                request=CreateToolApiRequest(tools=[item]),
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

    # Schema audit: for each tool, check that its declared args_outputs are
    # accepted by the union of its permissions' handler signatures + item
    # classes. Warn-mode — we don't fail the seed run; we surface counts for
    # triage. Dead permissions show up as "no surface" which looks like a
    # mismatch here; that's fine — both need cleanup.
    from app.infra.tool.schema_derive import derive_schema_for_permissions
    from database.seeds.resources.permissions import (
        permissions as _all_permissions,
    )

    perm_by_id = {p["id"]: (p["artifact"], p["operation"]) for p in _all_permissions}
    hard = 0
    varkw = 0
    for tool_def in tools:
        output_names = [
            SHARED_ARGS_OUTPUTS[k]["name"]
            for k in tool_def.get("args_outputs", [])
            if k in SHARED_ARGS_OUTPUTS
        ]
        perm_pairs = [
            perm_by_id[pid]
            for pid in tool_def.get("permission_ids", [])
            if pid in perm_by_id
        ]
        schema = derive_schema_for_permissions(perm_pairs)
        if schema.has_var_kwargs_handler:
            if schema.validate_output_keys(output_names, strict=True):
                varkw += 1
        else:
            if schema.validate_output_keys(output_names):
                hard += 1

    if hard or varkw:
        print(
            f"  ⚠ Schema audit: {hard} tool(s) with unaccepted args_outputs, "
            f"{varkw} tool(s) using **kwargs handlers. "
            "See notes/tool-schema-audit.txt for details."
        )


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

    if PostgresContainer is None or RedisContainer is None:
        raise RuntimeError(
            "testcontainers is not installed — dump mode is unavailable. "
            "Install dev requirements, or use --target-pg-url/--target-redis-url "
            "for in-place seeding."
        )

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


def _force_reseed_requested() -> bool:
    """True only when FORCE_RESEED is explicitly enabled in the environment.

    Mirrors the file's other env-read idioms. An unset, empty, or any
    non-truthy value yields False, so the default deploy behavior (an
    idempotent skip of already-seeded DBs) is never destructive.
    """
    return os.environ.get("FORCE_RESEED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _inplace_reseed_decision(table_count: int, *, force_reseed: bool) -> str:
    """Pure decision for the in-place seed guard (deps as params, no I/O).

    Returns one of:
      - ``"seed"``   : empty target — load schema + seed normally.
      - ``"skip"``   : already-seeded target, not forced — idempotent
                       no-op. This is the safe default and is byte-for-byte
                       the historical behavior, so an unset/empty
                       FORCE_RESEED can never trigger a drop.
      - ``"reseed"`` : already-seeded target AND FORCE_RESEED set — drop the
                       public app schema, then seed from scratch.
    """
    if table_count and table_count > 0:
        return "reseed" if force_reseed else "skip"
    return "seed"


async def _drop_app_schemas(conn: asyncpg.Connection) -> None:
    """Destructively reset the app-owned schemas for a forced reseed.

    Drops ONLY the application schemas: ``public`` (immediately recreated
    empty, which also restores the default schema grants) and the empty
    ``types`` schema. CASCADE clears every app table/view plus the
    public-resident extensions (pgcrypto, uuid-ossp); the subsequent
    reload restores them via ``CREATE EXTENSION IF NOT EXISTS ... WITH
    SCHEMA public``. ``types`` must be dropped too because the reload
    re-creates it with a non-idempotent ``CREATE SCHEMA types;``.

    The ``keycloak`` schema is deliberately NEVER touched — it holds auth
    state and the pre-deploy pg_dump excludes it
    (``--exclude-schema=keycloak``). Keeping the drop public-only ensures
    a forced reseed cannot orphan the auth realm.
    """
    await conn.execute(
        "DROP SCHEMA IF EXISTS public CASCADE; "
        "CREATE SCHEMA public; "
        "DROP SCHEMA IF EXISTS types CASCADE;"
    )


async def _load_schema(conn: asyncpg.Connection) -> None:
    """Load schema into the database."""
    print("Loading schema...")
    # Create the keycloak schema (its JDBC URL uses ?currentSchema=keycloak,
    # which fails at connect time if the schema doesn't exist). Don't
    # pre-create realm/org tables — keycloak's liquibase migrations
    # create them itself on first boot, and stub tables here cause
    # `relation "realm" already exists` failures under F2 in-place mode.
    await conn.execute("CREATE SCHEMA IF NOT EXISTS keycloak;")
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


async def main_setup(
    setup: str = "university",
    *,
    target_pg_url: str | None = None,
    target_redis_url: str | None = None,
) -> None:
    """Seed a fully independent setup — base modules + setup-specific data.

    Each setup is self-contained: it creates ALL platform resources,
    bootstraps its own superadmin profile, then seeds setup-specific data.
    No base-seed.sql, no shared state between setups.

    Two modes:
      - Dump mode (default): spin up testcontainers, seed, pg_dump to
        history/{setup}.sql.gz. Used by `make seed-gen` for dev/CI.
      - In-place mode (target_pg_url + target_redis_url set): seed the
        live DB directly, skip the dump step. Used by the `db-init`
        compose service at first deploy. Re-runs no-op when the target
        DB already has tables.

    Args:
        setup: Name of the setup to seed (must match a directory in seeds/setups/).
        target_pg_url: Live postgres URL to seed into. When set, in-place mode.
        target_redis_url: Live redis URL paired with target_pg_url.
    """
    in_place = target_pg_url is not None and target_redis_url is not None
    print(f"=== Seed Runner: {setup} ({'in-place' if in_place else 'dump'}) ===\n")

    force_reseed = _force_reseed_requested()
    force_reseed_applied = False
    if in_place:
        # Idempotency guard: if the target DB already has user tables,
        # treat this as an already-seeded deploy and exit silently. This
        # makes db-init safe to re-run on every `compose up`.
        #
        # Escape hatch: FORCE_RESEED=1 turns this into a destructive
        # reseed — the public schema is dropped + rebuilt below. Without
        # it the skip is preserved exactly (the safe default).
        guard_conn = await asyncpg.connect(target_pg_url)
        try:
            table_count = await guard_conn.fetchval(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            decision = _inplace_reseed_decision(
                table_count or 0, force_reseed=force_reseed
            )
            if decision == "skip":
                print(
                    f"  Target DB already has {table_count} public tables "
                    "— skipping seed."
                )
                return
            if decision == "reseed":
                # Destructive reseed of an already-seeded DB. Tear down the
                # public (app) schema only — keycloak/auth is left intact —
                # then fall through to the normal load_schema → seed flow.
                print("FORCE_RESEED: dropping public schema + reseeding")
                await _drop_app_schemas(guard_conn)
                force_reseed_applied = True
        finally:
            await guard_conn.close()
        pg, pg_url, redis_container, redis_url = None, target_pg_url, None, target_redis_url
    else:
        pg, pg_url, redis_container, redis_url = await _start_containers()

    try:
        conn = await asyncpg.connect(pg_url)
        await _load_schema(conn)
        await _refresh_mvs(conn)
        await conn.close()

        pool = await asyncpg.create_pool(pg_url)
        redis_client = Redis.from_url(redis_url)

        # Forced reseed dropped the public schema above; flush the live
        # redis too so stale cache (resource caches, lookups) from the
        # prior seed can't survive into the freshly reseeded DB.
        if force_reseed_applied:
            await redis_client.flushdb()
            print("  FORCE_RESEED: redis cache flushed")

        # The seed runner runs OUTSIDE the FastAPI lifespan, so the
        # globals singletons (redis_client, _db_pool) are never set by
        # the normal startup path. Bind them manually — many infra
        # functions (e.g. sync_benchmark_entries, keycloak sync) do
        # lazy get_redis_client() / get_pool() lookups, and under our
        # strict-Redis contract those raise / report unavailable
        # instead of silently no-oping.
        from app.infra import globals as _app_globals
        _app_globals.redis_client = redis_client
        _app_globals._db_pool = pool

        os.environ.setdefault("SECRET_KEY", "seed_runner_secret_key")
        os.environ.setdefault("AUTH_SECRET", "seed_runner_auth_secret")
        # Keycloak isn't running during seed generation — short-circuit
        # the auth-create sync hook so we don't block 30s on retries.
        os.environ.setdefault("SKIP_KEYCLOAK_SYNC", "1")

        setup_module = importlib.import_module(f"database.seeds.setups.{setup}")

        # Disable FK checks for all creates (base + setup)
        async with pool.acquire() as conn:
            dbname = await conn.fetchval("SELECT current_database()")
            await conn.execute(
                f"ALTER DATABASE {dbname} SET session_replication_role = 'replica'"
            )
        await pool.close()
        pool = await asyncpg.create_pool(pg_url)
        # Pool was recreated — rebind the globals singleton.
        _app_globals._db_pool = pool
        print("  FK checks disabled")

        # ── Phase 1: Base platform modules ────────────────────────────
        # These are shared definitions — every setup creates them.

        print("\nSeeding base resources...")
        await _run_resource_seeds(pool, redis_client)

        # Bootstrap the setup's superadmin (for _impl profile_id)
        print("\nBootstrapping setup profile...")
        bootstrap = setup_module.BOOTSTRAP_PROFILE
        seed_profile_id = bootstrap["id"]
        from app.infra.profile.primary_department import (
            resolve_primary_departments_id,
        )
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
                # Resolve primary_department_id → primary_departments_resource catalog
                # id so create_profile_artifact writes the SINGLE_JUNCTION row that
                # downstream settings_id lookup depends on.
                primary_departments_id = await resolve_primary_departments_id(
                    conn,
                    redis_client,
                    departments_id=bootstrap.get("primary_department_id"),
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
                    primary_departments_id=primary_departments_id,
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
        await _run_agent_module_seeds(
            pool,
            redis_client,
            default_department_ids=getattr(setup_module, "AGENT_DEPARTMENT_IDS", None),
        )

        print("\nSeeding auth...")
        await _run_auth_module_seeds(pool, redis_client)

        # Rubrics must run before evals — the eval seed dicts attach a
        # per-model rubric (model_rubrics_resource.rubric_id) that FKs to
        # rubrics_resource.id. The same applies to the three model_* steps:
        # they materialize the per-(model, *) resource rows that the eval
        # junction inserts reference, so they all run between rubrics and
        # evals to satisfy FKs and unblock benchmark sync on eval create.
        print("\nSeeding rubrics...")
        await _run_rubric_module_seeds(pool, redis_client)

        print("\nSeeding model flags...")
        await _run_model_flag_module_seeds(pool, redis_client)

        print("\nSeeding model rubrics...")
        await _run_model_rubric_module_seeds(pool, redis_client)

        print("\nSeeding model positions...")
        await _run_model_position_module_seeds(pool, redis_client)

        print("\nSeeding evals...")
        await _run_eval_module_seeds(pool, redis_client)

        print("\nSeeding systems...")
        await _run_system_module_seeds(pool, redis_client)

        print("\nSeeding tool instructions...")
        await _run_tool_instruction_seeds(pool, redis_client)

        print("\nSeeding tools...")
        await _run_tool_module_seeds(pool, redis_client)

        print("\nSeeding mcp resources...")
        await _run_mcp_module_seeds(pool, redis_client)

        print("\nSeeding dynamic keys...")
        import database.seeds.dynamic_keys as dk_mod
        await _run_key_seeds(pool, redis_client, dk_mod)

        print("\nSeeding base auth logins...")
        from database.seeds.logins import AUTH_LOGINS
        if AUTH_LOGINS:
            await _seed_logins(pool, redis_client, AUTH_LOGINS)
        else:
            print("  (no auth logins to seed — no auth providers in config)")

        # ── Phase 2: Setup-specific modules ───────────────────────────

        for module_name in setup_module.MODULES:
            print(f"\nSeeding {module_name}...")
            mod = importlib.import_module(
                f"database.seeds.setups.{setup}.{module_name}"
            )

            if module_name == "departments":
                await _run_department_seeds(pool, redis_client, mod.departments)
            elif module_name == "auths":
                # Setup-specific auth providers. Reuses create_auth_impl (same
                # black box as the config-driven base auths) so artifact +
                # resource snapshot are created consistently from one item.
                from app.infra.auth.create import create_auth_impl
                from app.infra.auth.types import (
                    CreateAuthApiRequest,
                    CreateAuthItem,
                )

                _auth_items = [CreateAuthItem(**d) for d in mod.auths]
                _auth_result = await create_auth_impl(
                    pool,
                    redis_client,
                    profile_id=SEED_PROFILE_ID,
                    request=CreateAuthApiRequest(auths=_auth_items),
                )
                _auth_ok = sum(1 for r in _auth_result.results if r.success)
                for r in _auth_result.results:
                    if not r.success:
                        print(f"  ERROR: {r.message}")
                print(f"  OK: {_auth_ok} setup auths created")
            elif module_name == "pricing":
                # Setup-specific pricing resources with non-zero rates so the
                # analytics seed can attach real spend (config models are $0).
                async with pool.acquire() as _pricing_conn:
                    await _seed_pricing(_pricing_conn, redis_client, mod.pricing)
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
            elif module_name == "parameter_fields":
                await _run_parameter_field_seeds(pool, redis_client, mod.parameter_fields)
            elif module_name == "conditional_parameters":
                await _run_conditional_parameter_seeds(pool, redis_client, mod.conditional_parameters)
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
            elif module_name == "logins":
                await _seed_logins(pool, redis_client, mod.logins)
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
            elif module_name == "videos":
                assets_dir = _get_assets_dir()
                await _run_video_seeds(
                    pool, redis_client, mod.scenario_videos, assets_dir
                )
            elif module_name == "images":
                assets_dir = _get_assets_dir()
                await _run_image_seeds(
                    pool, redis_client, mod.standalone_images, mod.document_images, assets_dir
                )

        # ── Phase 3: Analytical seeds ─────────────────────────────────
        # Synthetic attempt + test history so the dashboards (Activity,
        # Reports, Pricing, Leaderboard, Eval detail, Test list) have
        # data on first load. Each seed discovers its own FK targets
        # via canonical search black-boxes — no inline SQL — and skips
        # gracefully if a setup lacks the needed resources.
        #
        # MVs need a refresh before discovery: the per-MV canonical
        # `refresh_*` helpers in app/tools/entries/<x>/refresh.py all
        # use REFRESH ... CONCURRENTLY which fails for MVs without a
        # unique index (e.g. chat_mv). The runner's `_refresh_mvs`
        # uses plain non-concurrent refresh and handles all MVs in
        # one shot — exactly what we want post-seed.
        print("\nRefreshing materialized views before analytics seeds...")
        async with pool.acquire() as _refresh_conn:
            await _refresh_conn.execute(
                'SELECT matviewname FROM pg_matviews'
            )
            mvs_rows = await _refresh_conn.fetch(
                'SELECT matviewname FROM pg_matviews'
            )
            for row in mvs_rows:
                try:
                    await _refresh_conn.execute(
                        f'REFRESH MATERIALIZED VIEW "{row["matviewname"]}"'
                    )
                except Exception as e:
                    print(f"  (skipped {row['matviewname']}: {e})")
        print(f"  {len(mvs_rows)} MVs refreshed.")

        print("\nSeeding attempt analytics...")
        from database.seeds.attempts_analytics import seed as _seed_attempts_analytics
        await _seed_attempts_analytics(pool, redis_client)

        print("\nSeeding test analytics...")
        from database.seeds.tests_analytics import seed as _seed_tests_analytics
        await _seed_tests_analytics(pool, redis_client)

        print("\nRefreshing materialized views after analytics seeds...")
        async with pool.acquire() as _refresh_conn:
            mvs_rows = await _refresh_conn.fetch(
                'SELECT matviewname FROM pg_matviews'
            )
            for row in mvs_rows:
                try:
                    await _refresh_conn.execute(
                        f'REFRESH MATERIALIZED VIEW "{row["matviewname"]}"'
                    )
                except Exception as e:
                    print(f"  (skipped {row['matviewname']}: {e})")
        print(f"  {len(mvs_rows)} MVs refreshed.")

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

        if not in_place:
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
        # Unbind the runner's pool + redis client from globals so a
        # long-running process that re-runs seeds doesn't pick up
        # closed handles.
        from app.infra import globals as _app_globals
        _app_globals.redis_client = None
        _app_globals._db_pool = None
        if pg is not None:
            pg.stop()
        if redis_container is not None:
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
    parser.add_argument(
        "--target-pg-url",
        default=os.environ.get("SEED_TARGET_PG_URL"),
        help="Live postgres URL to seed in place (skips testcontainer + pg_dump). "
        "Env: SEED_TARGET_PG_URL.",
    )
    parser.add_argument(
        "--target-redis-url",
        default=os.environ.get("SEED_TARGET_REDIS_URL"),
        help="Live redis URL paired with --target-pg-url. Env: SEED_TARGET_REDIS_URL.",
    )
    args = parser.parse_args()

    if args.all:
        if args.target_pg_url:
            parser.error("--all is incompatible with --target-pg-url (in-place mode is per-setup)")
        asyncio.run(main_all())
    else:
        asyncio.run(
            main_setup(
                args.setup or "university",
                target_pg_url=args.target_pg_url,
                target_redis_url=args.target_redis_url,
            )
        )
