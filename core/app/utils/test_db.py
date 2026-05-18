"""Test database utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - runtime import happens lazily
    pass  # type: ignore


def get_test_db_url() -> str | None:
    """Get the test database connection URL (for test fixtures).

    Returns None if not in test mode or container not started.
    Prefers the explicit _test_db_url (set during template clone flow),
    falls back to deriving from the container.
    """
    from app.infra.globals import _test_container, _test_db_url

    # If conftest set an explicit URL (e.g. after cloning a template DB), use it
    if _test_db_url is not None:
        return _test_db_url

    # Fallback: derive from the container
    if _test_container is None:
        return None
    raw_url = _test_container.get_connection_url()
    return raw_url.replace("postgresql+psycopg2://", "postgresql://")  # type: ignore
