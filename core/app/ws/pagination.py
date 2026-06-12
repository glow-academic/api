"""Shared pagination bases for WebSocket search payloads.

The ``le=200`` page-size DoS cap originally landed only on the *HTTP*
request models (#336) and, later, the single WS ``attempt.search`` model
(#354 B1). Every other WS search payload defined its own
``page_size: int = Field(<default>)`` with **no upper bound**, so a socket
sending ``{"page_size": 10_000_000}`` flowed unclamped into the same
``search_*_impl`` LIMIT (often ``limit + offset + 1000``), driving an
unbounded scan + in-memory row materialization (OOM / box-hang).

To stop HTTP/WS drift from re-opening the gap one endpoint at a time, all
WS search payloads inherit one of the bases below. The bound lives in a
single shared place; subclasses keep their own field defaults (e.g. 12)
but can never raise the ceiling.

Two bases exist only because the WS search family uses two pagination
conventions:

* ``PaginatedWsSearch`` — ``page_size`` + ``page_offset`` (the majority).
* ``PagedWsSearch``     — ``page_size`` + ``page`` (activity / pricing).

A subclass that needs a non-default ``page_size`` redeclares the field
*with the same bounds*, e.g. ``page_size: int = Field(12, ge=1, le=200)``.
``MAX_WS_PAGE_SIZE`` is exported so subclasses (and tests) reference one
constant instead of copying ``200`` around.
"""

from pydantic import BaseModel, Field

from app.infra.shared_types import MAX_PAGE_SIZE

# Upper bound on any WS search ``page_size``. Re-exported from the single
# shared ``MAX_PAGE_SIZE`` (= 200) used by the HTTP request models (#336) and
# the WS attempt.search cap (#354 B1) so the HTTP and WS caps can never drift
# apart. Aliased to ``MAX_WS_PAGE_SIZE`` for readable WS-side references.
MAX_WS_PAGE_SIZE = MAX_PAGE_SIZE


class PaginatedWsSearch(BaseModel):
    """Base for WS search payloads paginated by ``page_offset``.

    ``page_size`` is bounded to ``[1, MAX_WS_PAGE_SIZE]`` and ``page_offset``
    to ``>= 0``. Subclasses override the ``page_size`` default by
    redeclaring the field with the same ``ge``/``le`` bounds.
    """

    page_size: int = Field(12, ge=1, le=MAX_WS_PAGE_SIZE)
    page_offset: int = Field(0, ge=0)


class PagedWsSearch(BaseModel):
    """Base for WS search payloads paginated by ``page`` (page index).

    Same bound on ``page_size``; ``page`` is a zero-based index ``>= 0``.
    """

    page: int = Field(0, ge=0)
    page_size: int = Field(50, ge=1, le=MAX_WS_PAGE_SIZE)
