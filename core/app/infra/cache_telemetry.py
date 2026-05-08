"""Per-request cache telemetry — accumulator + one-line summary.

Replaces the per-event ``logger.debug("Cache hit/miss/write")`` and
``logger.info("Invalidated cache for tags: …")`` lines with a single
summary line emitted at request end (by the request middleware).

Mechanism: an asyncio-safe ``ContextVar`` holds a ``CacheTelemetry``
instance scoped to the current request. The cache helpers
(``get_cached``, ``set_cached``, ``invalidate_tags``) push counts
onto that instance via the ``record_*`` functions. The middleware
reads the accumulator on response and emits one log line if there
was meaningful activity.

When no telemetry is bound to the contextvar (background workers,
MV refresher, MCP dispatch outside an HTTP request, etc.), the
``record_*`` helpers no-op silently — no log, no error.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class CacheTelemetry:
    """Per-request cache activity accumulator."""

    hits: int = 0
    misses: int = 0
    writes: int = 0
    invalidated_tags: set[str] = field(default_factory=set)

    @property
    def total_events(self) -> int:
        return self.hits + self.misses + self.writes + len(self.invalidated_tags)

    def format_summary(self) -> str:
        """One-line human-readable summary. Skip zero counts; only show
        invalidations when present (they're sparse and signal a write)."""
        parts: list[str] = []
        if self.hits:
            parts.append(f"hit={self.hits}")
        if self.misses:
            parts.append(f"miss={self.misses}")
        if self.writes:
            parts.append(f"write={self.writes}")
        if self.invalidated_tags:
            tags = ",".join(sorted(self.invalidated_tags))
            parts.append(f"invalidated=[{tags}]")
        return " ".join(parts)

    def as_header(self) -> str:
        """Compact form for an X-Cache-Stats response header."""
        return ",".join(
            [
                f"hit={self.hits}",
                f"miss={self.misses}",
                f"write={self.writes}",
                f"inv={len(self.invalidated_tags)}",
            ]
        )


_cache_telemetry_ctx: contextvars.ContextVar[CacheTelemetry | None] = (
    contextvars.ContextVar("cache_telemetry", default=None)
)


def begin_request() -> CacheTelemetry:
    """Reset the contextvar at request entry. Returns the fresh
    accumulator so the caller can log/serialize it later."""
    tel = CacheTelemetry()
    _cache_telemetry_ctx.set(tel)
    return tel


def current() -> CacheTelemetry | None:
    """Active accumulator, or None if no request is in flight."""
    return _cache_telemetry_ctx.get()


def record_hit() -> None:
    tel = _cache_telemetry_ctx.get()
    if tel is not None:
        tel.hits += 1


def record_miss() -> None:
    tel = _cache_telemetry_ctx.get()
    if tel is not None:
        tel.misses += 1


def record_write() -> None:
    tel = _cache_telemetry_ctx.get()
    if tel is not None:
        tel.writes += 1


def record_invalidation(tags: Iterable[str]) -> None:
    tel = _cache_telemetry_ctx.get()
    if tel is not None:
        tel.invalidated_tags.update(tags)
