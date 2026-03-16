"""Benchmark test bridge entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.benchmark_test.create import create_benchmark_test
from app.tools.entries.benchmark_test.get import get_benchmark_tests
from app.tools.entries.benchmark_test.refresh import refresh_benchmark_test
from app.tools.entries.benchmark_test.search import search_benchmark_tests


async def get_benchmark_test_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the benchmark_test entry."""
    mv_info = await get_mv_info(conn, "benchmark_test_mv")
    entry_table = await get_table_info(conn, "benchmark_test_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="benchmark_test",
        type="entry",
        description=(
            "Benchmark test bridge entries link benchmarks to tests via a session. "
            "This bridge table connects the benchmark and test domains. "
            "Reads are served from the benchmark_test_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_benchmark_test,
                description=(
                    "Creates a new benchmark_test entry linking a benchmark "
                    "to a test within a session."
                ),
            ),
            get_operation_info(
                get_benchmark_tests,
                description="Retrieves benchmark_test entries by benchmark IDs from MV.",
            ),
            get_operation_info(
                refresh_benchmark_test,
                description="Refreshes benchmark_test_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                search_benchmark_tests,
                description="Filtered paginated search against benchmark_test_mv.",
            ),
        ],
    )
