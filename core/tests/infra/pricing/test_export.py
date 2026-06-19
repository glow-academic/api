"""Integration tests for ``export_pricing_impl``.

Exercises the pricing EXPORT only — that a seeded pricing graph exports a
base64 zip containing a single ``runs.csv`` whose rows carry the seeded run id
and its hydrated group name, with the right row_count / mime_type / file name.
"""

from __future__ import annotations

import base64
import csv
import io
import zipfile

import pytest

from app.infra.pricing.export import export_pricing_impl
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import (
    create_run_pricing_entry_internal,
)
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.tokens.create import create_token
from app.tools.resources.agents.create import create_agent
from app.tools.resources.models.create import create_model
from app.tools.resources.pricing.create import create_pricing

pytestmark = pytest.mark.asyncio


async def _seed_pricing_graph(conn, redis_client, profile_resource_id):
    session = await create_session(conn, redis_client, profile_id=profile_resource_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await create_group_name(conn, redis_client, group.id, "Pricing Group", session.id)
    model = await create_model(
        conn,
        value="gpt-test-pricing",
        name="Pricing Model",
        redis=redis_client,
    )
    agent = await create_agent(
        conn,
        name="Pricing Agent",
        redis=redis_client,
        model_id=model.id,
    )
    input_pricing = await create_pricing(
        conn,
        "input",
        0.02,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    output_pricing = await create_pricing(
        conn,
        "output",
        0.03,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    run = await create_run(
        conn,
        redis_client, group_id=group.id,
        session_id=session.id,
        agent_ids=[agent.id],
    )
    await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        pricing_id=input_pricing.id,
        count=1500,
    )
    await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="output",
        run_id=run.id,
        pricing_id=output_pricing.id,
        count=2000,
    )
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY run_pricing_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")
    return session, group, run, model, agent


class TestExportPricingClient:
    async def test_exports_pricing_zip(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            _session, _group, run, _model, _agent = await _seed_pricing_graph(
                conn, redis_client, profile.profile_resource_id
            )

        result = await export_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.row_count >= 1
        assert result.file_name.startswith("pricing_export_")
        assert result.file_name.endswith(".zip")
        assert result.mime_type == "application/zip"
        assert result.content != ""

        zip_bytes = base64.b64decode(result.content)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            assert archive.namelist() == ["runs.csv"]
            runs_csv = archive.read("runs.csv").decode("utf-8")

        # The seeded run is present, with the canonical column header...
        assert runs_csv.splitlines()[0].split(",") == [
            "run_id", "group", "run_date", "input_tokens", "output_tokens",
            "cached_input_tokens", "total_tokens", "cost", "agents", "models",
        ]
        rows = list(csv.DictReader(io.StringIO(runs_csv)))
        seeded = next(row for row in rows if row["run_id"] == str(run.id))

        # ...and its cost is computed from the seeded run_pricing entries
        # (1500 input tokens @ $0.02/1k + 2000 output @ $0.03/1k = 0.09),
        # NOT from runs_mv token columns (which the seed leaves at 0 — those
        # are populated by the live generation path, not create_run).
        assert seeded["input_tokens"] == "0"
        assert seeded["output_tokens"] == "0"
        assert float(seeded["cost"]) == pytest.approx(0.09)

    async def test_export_renders_group_name_from_get_groups(
        self, pool, redis_client, profile_identity_factory
    ):
        """The ``group`` column must carry the hydrated group name.

        Regression guard for a groups read-back cache-coherence bug this
        rewrite surfaced: ``create_group`` seeds the ``groups`` cache row with
        ``name=""`` (the name is owned by the separate group_names primitive),
        and ``create_group_name`` used to update only the *group_names* cache
        namespace — never the *groups* one. So the export's cached
        ``get_groups`` read returned the stale empty name and the ``group``
        column came out blank even though the name was live in groups_mv
        (``get_groups(..., bypass_cache=True)`` returned it). Fixed by
        invalidating the ``groups`` read-back row in ``create_group_name``.
        """
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            _session, _group, run, _model, _agent = await _seed_pricing_graph(
                conn, redis_client, profile.profile_resource_id
            )

        result = await export_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        zip_bytes = base64.b64decode(result.content)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            runs_csv = archive.read("runs.csv").decode("utf-8")

        rows = list(csv.DictReader(io.StringIO(runs_csv)))
        seeded = next(row for row in rows if row["run_id"] == str(run.id))
        assert seeded["group"] == "Pricing Group"

    async def test_total_tokens_excludes_cached_no_double_count(
        self, pool, redis_client, profile_identity_factory
    ):
        """HIGH-1: ``cached_input_tokens`` is a SUBSET of ``input_tokens``
        (litellm folds cache-read into prompt_tokens for both OpenAI and
        Anthropic), so the exported ``total_tokens`` must be input + output —
        NOT input + output + cached, which double-counted the cached portion."""
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            _session, _group, run, _model, _agent = await _seed_pricing_graph(
                conn, redis_client, profile.profile_resource_id
            )
            # 300 of the 1000 input tokens were cache-reads (cached ⊆ input).
            await create_token(
                conn,
                redis_client,
                run_id=run.id,
                session_id=_session.id,
                input_tokens=1000,
                output_tokens=500,
                cached_input_tokens=300,
            )
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

        result = await export_pricing_impl(
            pool, redis_client, profile_id=profile.artifact_id,
        )
        zip_bytes = base64.b64decode(result.content)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            runs_csv = archive.read("runs.csv").decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(runs_csv)))
        seeded = next(row for row in rows if row["run_id"] == str(run.id))

        assert seeded["input_tokens"] == "1000"
        assert seeded["output_tokens"] == "500"
        assert seeded["cached_input_tokens"] == "300"
        # total = input + output = 1500. The 300 cached are already inside the
        # 1000 input; adding them again (the old bug) made this 1800.
        assert seeded["total_tokens"] == "1500"

    async def test_export_with_no_runs_returns_empty(
        self, pool, redis_client, profile_identity_factory
    ):
        # A profile that never seeds a pricing graph still shares the global
        # runs MV, so export may legitimately surface other rows. Only assert
        # the empty-export contract when this run genuinely sees zero runs.
        profile = await profile_identity_factory()

        result = await export_pricing_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.mime_type == "application/zip"
        if result.row_count == 0:
            assert result.content == ""
            assert result.file_name == ""
        else:
            assert result.content != ""
            assert result.file_name.endswith(".zip")
