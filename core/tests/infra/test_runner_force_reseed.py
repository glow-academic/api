"""Guard tests for the db-init seed runner's FORCE_RESEED escape hatch.

``database.scripts.runner.main_setup`` runs in-place against the live DB
on the ``db-init`` compose service. Its idempotency guard skips reseeding
whenever the target already has public tables, which made reseeding an
already-seeded DB impossible. ``FORCE_RESEED=1`` now turns that skip into
a destructive reseed: drop the PUBLIC (app) schema + reseed, while the
``keycloak`` (auth) schema is left untouched.

These are modular guards over the three small, isolatable pieces of that
path (deps as params — env / count / connection passed in):

  * ``_force_reseed_requested`` — env parsing (truthy set only).
  * ``_inplace_reseed_decision`` — pure skip/seed/reseed branching.
  * ``_drop_app_schemas``       — drops public + types, NEVER keycloak.

The destructive drop is exercised against a throwaway scratch database so
the shared test clone is never disturbed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg
import pytest

# `database` is a top-level package at the repo root (sibling of `core`),
# which is not on the path under the `PYTHONPATH=core` test invocation.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.utils.test_db import get_test_db_url  # noqa: E402
from database.scripts.runner import (  # noqa: E402
    _drop_app_schemas,
    _force_reseed_requested,
    _inplace_reseed_decision,
)


# ---------------------------------------------------------------------------
# _force_reseed_requested — env parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", " on ", "On"])
def test_force_reseed_requested_truthy(monkeypatch, value):
    monkeypatch.setenv("FORCE_RESEED", value)
    assert _force_reseed_requested() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "nope"])
def test_force_reseed_requested_falsy(monkeypatch, value):
    monkeypatch.setenv("FORCE_RESEED", value)
    assert _force_reseed_requested() is False


def test_force_reseed_requested_unset_defaults_false(monkeypatch):
    # The critical safety default: absent env var → never destructive.
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    assert _force_reseed_requested() is False


# ---------------------------------------------------------------------------
# _inplace_reseed_decision — pure skip / seed / reseed branching
# ---------------------------------------------------------------------------


def test_decision_empty_db_seeds_regardless_of_force():
    # Empty target → always a normal seed (FORCE_RESEED set + empty DB
    # must seed normally, never attempt a drop).
    assert _inplace_reseed_decision(0, force_reseed=False) == "seed"
    assert _inplace_reseed_decision(0, force_reseed=True) == "seed"


def test_decision_seeded_db_unforced_skips():
    # FORCE_RESEED unset + tables present → idempotent skip (unchanged).
    assert _inplace_reseed_decision(42, force_reseed=False) == "skip"


def test_decision_seeded_db_forced_reseeds():
    # FORCE_RESEED set + tables present → does NOT skip; reseeds.
    assert _inplace_reseed_decision(42, force_reseed=True) == "reseed"


# ---------------------------------------------------------------------------
# _drop_app_schemas — public + types dropped, keycloak preserved
# ---------------------------------------------------------------------------


def _admin_url(db_url: str) -> str:
    return urlunparse(urlparse(db_url)._replace(path="/postgres"))


def _scratch_url(db_url: str, name: str) -> str:
    return urlunparse(urlparse(db_url)._replace(path=f"/{name}"))


@pytest.mark.asyncio
async def test_drop_app_schemas_drops_public_and_types_keeps_keycloak():
    """Force-reseed teardown: drop public (sentinel gone, fresh + empty) +
    drop types, while keycloak and its data survive intact."""
    base_url = get_test_db_url()
    assert base_url is not None, "test database URL not available"

    admin_url = _admin_url(base_url)
    scratch_db = "scratch_force_reseed_drop"
    scratch_url = _scratch_url(base_url, scratch_db)

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{scratch_db}"')
        await admin.execute(f'CREATE DATABASE "{scratch_db}"')
    finally:
        await admin.close()

    conn = await asyncpg.connect(scratch_url)
    try:
        # Stand up the three schemas with sentinels: a public app table,
        # the (empty) types schema, and a keycloak auth table + row.
        await conn.execute(
            """
            CREATE TABLE public.sentinel_app (id int PRIMARY KEY);
            INSERT INTO public.sentinel_app (id) VALUES (1);
            CREATE SCHEMA types;
            CREATE SCHEMA keycloak;
            CREATE TABLE keycloak.realm (name text PRIMARY KEY);
            INSERT INTO keycloak.realm (name) VALUES ('glow');
            """
        )

        # Sanity: everything present before the drop.
        assert await conn.fetchval(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='sentinel_app'"
        )
        assert await conn.fetchval(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name='types'"
        )

        # --- the destructive teardown under test ---
        await _drop_app_schemas(conn)

        # public exists again but is EMPTY — the sentinel is gone.
        assert await conn.fetchval(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name='public'"
        ), "public schema must be recreated"
        public_tables = await conn.fetchval(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public'"
        )
        assert public_tables == 0, "public must be wiped clean (sentinel dropped)"

        # types is dropped (the reload re-creates it non-idempotently).
        assert not await conn.fetchval(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name='types'"
        ), "types schema must be dropped"

        # keycloak schema, its table, AND its data all survive untouched.
        assert await conn.fetchval(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name='keycloak'"
        ), "keycloak schema must NOT be a drop target"
        survivors = await conn.fetchval("SELECT count(*) FROM keycloak.realm")
        assert survivors == 1, "keycloak data must survive a forced reseed"
        assert (
            await conn.fetchval("SELECT name FROM keycloak.realm") == "glow"
        )
    finally:
        await conn.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{scratch_db}"')
        finally:
            await admin.close()
