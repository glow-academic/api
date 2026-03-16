"""Tests for test DB URL helper."""

import app.infra.globals as globals_mod
from app.utils.test_db import get_test_db_url


class _FakeContainer:
    def get_connection_url(self) -> str:
        return "postgresql+psycopg2://user:pass@localhost:5432/testdb"


def test_get_test_db_url_prefers_explicit_cloned_url():
    original_container = globals_mod._test_container
    original_url = globals_mod._test_db_url
    try:
        globals_mod._test_container = _FakeContainer()
        globals_mod._test_db_url = "postgresql://explicit-host/clone_db"

        assert get_test_db_url() == "postgresql://explicit-host/clone_db"
    finally:
        globals_mod._test_container = original_container
        globals_mod._test_db_url = original_url


def test_get_test_db_url_derives_from_container_connection_url():
    original_container = globals_mod._test_container
    original_url = globals_mod._test_db_url
    try:
        globals_mod._test_container = _FakeContainer()
        globals_mod._test_db_url = None

        assert get_test_db_url() == "postgresql://user:pass@localhost:5432/testdb"
    finally:
        globals_mod._test_container = original_container
        globals_mod._test_db_url = original_url


def test_get_test_db_url_returns_none_without_container_or_explicit_url():
    original_container = globals_mod._test_container
    original_url = globals_mod._test_db_url
    try:
        globals_mod._test_container = None
        globals_mod._test_db_url = None

        assert get_test_db_url() is None
    finally:
        globals_mod._test_container = original_container
        globals_mod._test_db_url = original_url
