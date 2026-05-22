"""Server-Timing header support (W3C spec).

A request-scoped timing recorder + ASGI middleware. Any code path inside a
request can wrap a block in ``with timed("phase"):`` to record its elapsed
time. The middleware sums durations per phase across the request and emits
them as a ``Server-Timing`` HTTP response header.

Example output::

    Server-Timing: identity;dur=12.3, group;dur=4.5, artifact;dur=89.1, total;dur=120.4

Browsers expose this header in DevTools → Network → Timing tab; curl users
can see it with ``curl -i``. CORS clients need ``Access-Control-Expose-Headers``
to include ``Server-Timing`` (handled by the existing CORSMiddleware config
if exposed; not required for server-to-server probes).

Usage:

    from app.infra.server_timing import timed

    async def get_persona_impl(...):
        with timed("identity"):
            profile = await resolve_profile_identity_context(...)
        with timed("artifact"):
            artifacts = await get_personas(...)
        ...

Multiple ``timed("X")`` blocks with the same name accumulate (e.g. timed("db")
in a loop sums total DB time across iterations). Outside a request scope
(background tasks, scripts) ``timed`` is a no-op so callers don't have to
branch.
"""

from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager
from typing import Iterator

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Per-request store of {phase_name: cumulative_ms}. ContextVar so async tasks
# spawned inside the request inherit it correctly (asyncio propagates).
_timings: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "server_timings", default=None
)


@contextmanager
def timed(phase: str) -> Iterator[None]:
    """Record elapsed time for ``phase`` in the current request's timing store.

    Nested timings work fine — each block records its own elapsed independently.
    Multiple calls with the same ``phase`` accumulate.

    Outside a request scope, this is a no-op (cheap try/finally, no errors).
    """
    store = _timings.get()
    if store is None:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        store[phase] = store.get(phase, 0.0) + elapsed_ms


class ServerTimingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that emits the W3C Server-Timing response header.

    Sets up a per-request timing dict in a ContextVar before the route runs,
    records the total request time, and writes the aggregated phases to the
    response header on the way out.
    """

    async def dispatch(self, request: Request, call_next):
        store: dict[str, float] = {}
        token = _timings.set(store)
        t0 = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            _timings.reset(token)

        store["total"] = (time.perf_counter() - t0) * 1000

        # Compose header value. Order: insertion order (Python 3.7+ dict),
        # with "total" guaranteed last for readability.
        ordered = [(k, v) for k, v in store.items() if k != "total"]
        ordered.append(("total", store["total"]))
        response.headers["Server-Timing"] = ", ".join(
            f"{name};dur={dur:.1f}" for name, dur in ordered
        )
        return response
