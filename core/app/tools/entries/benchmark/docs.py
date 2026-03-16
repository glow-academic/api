"""Benchmark entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.get import get_benchmarks
from app.tools.entries.benchmark.search import search_benchmarks


async def get_benchmark_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the benchmark entry."""
    mv_info = await get_mv_info(conn, "benchmark_mv")
    entry_table = await get_table_info(conn, "benchmark_entry")
    evals_connection = await get_table_info(conn, "benchmark_evals_connection")
    profiles_connection = await get_table_info(conn, "benchmark_profiles_connection")
    departments_connection = await get_table_info(
        conn, "benchmark_departments_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            evals_connection,
            profiles_connection,
            departments_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="benchmark",
        type="entry",
        description=(
            "Benchmark entries define test scenarios for evaluation and comparison. "
            "Each benchmark can link to evaluations, profiles, and departments via connection tables. "
            "Reads are served from the benchmark_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_benchmark,
                description=(
                    "Creates a new benchmark entry with optional connections to evals, "
                    "profiles, and departments."
                ),
            ),
            get_operation_info(
                get_benchmarks,
                description="Batch retrieves benchmark entries by IDs from benchmark_mv.",
            ),
            get_operation_info(
                search_benchmarks,
                description="Filtered paginated search against benchmark_mv.",
            ),
        ],
    )
