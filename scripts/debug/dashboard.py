"""Aggregator + helpers for the call-audit corpus in ``uploads/call/``.

This module is a *library*. ``server.py`` imports from it to power the
debug panel's `/data` endpoint and live terminal tail. There is no CLI
entry point — everything is launched through ``make debug``.

Each file under ``uploads/call/<call_id>.json`` is one record::

    {
      "call_id":   "<uuid>",
      "tool_id":   "<uuid>",
      "arguments": { ... },
      "output":    "<rendered template result>",
      "raw_output": { "success": true, ... },
      "events": [
        {"event": "attempt.chat_message.started",   "timestamp": "..."},
        {"event": "attempt.chat_message.completed", "timestamp": "..."}
      ]
    }

Tool identity is read from ``events[].event`` (e.g. ``attempt.chat_message``
stripped of the ``.started/.completed/.failed`` suffix). If the call has
no events the truncated ``tool_id`` is shown.

Stdlib only — reads files lazily, mtime filter skips most files without
parsing JSON.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


# Repo-root anchored: this file is at scripts/debug/dashboard.py, so
# parents[2] is the repo root.
DEFAULT_CALLS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "call"
RECENT_ACTIVITY_N = 10
RECENT_FAILURES_N = 5
RECENT_ACTIVITY_HTML_N = 50   # web panel uses the wider slice
RECENT_FAILURES_HTML_N = 25
TOP_TOOLS_N = 10


_USE_COLOR = sys.stdout.isatty()


def _c(s: str, code: str) -> str:
    if not _USE_COLOR:
        return s
    return f"\033[{code}m{s}\033[0m"


def red(s: str) -> str:
    return _c(s, "31")


def yellow(s: str) -> str:
    return _c(s, "33")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_since(spec: str | None) -> datetime | None:
    """Convert "1h", "30m", "2d" → cutoff datetime in UTC. None → no filter."""
    if not spec:
        return None
    spec = spec.strip().lower()
    if spec == "all":
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if spec[-1] in units and spec[:-1].isdigit():
        seconds = int(spec[:-1]) * units[spec[-1]]
        return datetime.now(timezone.utc) - timedelta(seconds=seconds)
    if spec.isdigit():
        return datetime.now(timezone.utc) - timedelta(seconds=int(spec))
    raise ValueError(f"unrecognized --since value: {spec!r}")


def _walk_calls(
    folder: Path, since: datetime | None
) -> Iterator[tuple[Path, float]]:
    """Yield (path, mtime) for *.json files in folder, optionally filtered
    to mtime >= since. mtime filter is cheap (no JSON parse) — used to
    skip 95% of files for last-N-window queries."""
    if not folder.exists():
        return
    cutoff_ts = since.timestamp() if since else None
    for entry in os.scandir(folder):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        st = entry.stat()
        if cutoff_ts is not None and st.st_mtime < cutoff_ts:
            continue
        yield Path(entry.path), st.st_mtime


def _load_call(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _tool_identity(call: dict[str, Any]) -> str:
    """Extract a readable tool identity from the call record.

    Prefer the artifact.operation prefix from the first event (e.g.
    'attempt.chat_message' from 'attempt.chat_message.completed'). Fall
    back to the truncated tool_id when no events exist."""
    events = call.get("events") or []
    if events:
        ev = events[0].get("event") or ""
        for suffix in (".started", ".completed", ".failed"):
            if ev.endswith(suffix):
                return ev[: -len(suffix)]
        if ev:
            return ev
    tid = call.get("tool_id") or ""
    return f"tool:{tid[:8]}" if tid else "<unknown>"


def _is_success(call: dict[str, Any]) -> bool:
    raw = call.get("raw_output") or {}
    if isinstance(raw, dict) and "success" in raw:
        return bool(raw["success"])
    for ev in call.get("events") or []:
        if (ev.get("event") or "").endswith(".failed"):
            return False
    return True


def _failure_reason(call: dict[str, Any]) -> str:
    raw = call.get("raw_output") or {}
    if isinstance(raw, dict):
        msg = raw.get("message") or raw.get("error") or ""
        if msg:
            return str(msg)[:80]
    for ev in call.get("events") or []:
        if (ev.get("event") or "").endswith(".failed"):
            data = ev.get("data") or {}
            return str(data.get("message") or data.get("error_type") or "failed")[:80]
    return "<no error message>"


def _latency_ms(call: dict[str, Any]) -> float | None:
    """Time between first and last event, in milliseconds."""
    events = call.get("events") or []
    if len(events) < 2:
        return None
    try:
        t0 = datetime.fromisoformat(str(events[0]["timestamp"]).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(events[-1]["timestamp"]).replace("Z", "+00:00"))
        return (t1 - t0).total_seconds() * 1000.0
    except (KeyError, ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


class Aggregate:
    """Streaming aggregator — keeps per-tool stats + recent events + ranges."""

    def __init__(self, top_n: int = TOP_TOOLS_N) -> None:
        self.total = 0
        self.failures = 0
        self.disk_bytes = 0
        self.first_mtime: float | None = None
        self.last_mtime: float | None = None
        self.per_tool: dict[str, dict[str, Any]] = {}
        self.recent_activity: list[dict[str, Any]] = []
        self.recent_failures: list[dict[str, Any]] = []
        self.top_n = top_n

    def add(self, path: Path, mtime: float, call: dict[str, Any]) -> None:
        self.total += 1
        try:
            self.disk_bytes += path.stat().st_size
        except OSError:
            pass

        if self.first_mtime is None or mtime < self.first_mtime:
            self.first_mtime = mtime
        if self.last_mtime is None or mtime > self.last_mtime:
            self.last_mtime = mtime

        tool = _tool_identity(call)
        ok = _is_success(call)
        latency = _latency_ms(call)

        bucket = self.per_tool.setdefault(
            tool,
            {"count": 0, "failures": 0, "latencies": []},
        )
        bucket["count"] += 1
        if not ok:
            bucket["failures"] += 1
            self.failures += 1
        if latency is not None:
            bucket["latencies"].append(latency)

        record = {
            "mtime": mtime,
            "tool": tool,
            "ok": ok,
            "latency_ms": latency,
            "call_id": call.get("call_id") or path.stem,
        }

        activity_cap = RECENT_ACTIVITY_HTML_N
        self.recent_activity.append(record)
        if len(self.recent_activity) > activity_cap * 4:
            self.recent_activity.sort(key=lambda r: r["mtime"], reverse=True)
            self.recent_activity = self.recent_activity[: activity_cap * 2]

        if not ok:
            failure = dict(record)
            failure["reason"] = _failure_reason(call)
            self.recent_failures.append(failure)
            failure_cap = RECENT_FAILURES_HTML_N
            if len(self.recent_failures) > failure_cap * 4:
                self.recent_failures.sort(key=lambda r: r["mtime"], reverse=True)
                self.recent_failures = self.recent_failures[: failure_cap * 2]

    def finalize(self, html_mode: bool = False) -> dict[str, Any]:
        self.recent_activity.sort(key=lambda r: r["mtime"], reverse=True)
        self.recent_failures.sort(key=lambda r: r["mtime"], reverse=True)
        top_tools = sorted(
            self.per_tool.items(), key=lambda kv: kv[1]["count"], reverse=True
        )[: self.top_n]
        activity_n = RECENT_ACTIVITY_HTML_N if html_mode else RECENT_ACTIVITY_N
        failures_n = RECENT_FAILURES_HTML_N if html_mode else RECENT_FAILURES_N
        return {
            "total": self.total,
            "failures": self.failures,
            "disk_bytes": self.disk_bytes,
            "first_mtime": self.first_mtime,
            "last_mtime": self.last_mtime,
            "top_tools": top_tools,
            "recent_activity": self.recent_activity[:activity_n],
            "recent_failures": self.recent_failures[:failures_n],
        }


def _build_aggregate(
    folder: Path,
    since: datetime | None,
    tool_filter: str | None,
    failures_only: bool,
    quiet: bool = False,
) -> Aggregate:
    paths_with_mtime = list(_walk_calls(folder, since))
    if not quiet and len(paths_with_mtime) > 2000:
        print(
            f"Scanning {len(paths_with_mtime):,} call records...",
            file=sys.stderr,
            flush=True,
        )

    agg = Aggregate()
    for path, mtime in paths_with_mtime:
        call = _load_call(path)
        if call is None:
            continue
        if tool_filter and tool_filter not in _tool_identity(call):
            continue
        if failures_only and _is_success(call):
            continue
        agg.add(path, mtime, call)
    return agg


# ---------------------------------------------------------------------------
# Single-call view (used by server.py `--show <id>`)
# ---------------------------------------------------------------------------


def render_show(call_id_prefix: str, folder: Path) -> str:
    """Pretty-print a single call by call_id prefix match."""
    matches: list[Path] = []
    for entry in os.scandir(folder):
        if entry.name.startswith(call_id_prefix) and entry.name.endswith(".json"):
            matches.append(Path(entry.path))
            if len(matches) > 5:
                break
    if not matches:
        return red(f"No call matching prefix {call_id_prefix!r}")
    if len(matches) > 1:
        listing = "\n".join(f"  - {p.name}" for p in matches[:10])
        return yellow(f"Ambiguous prefix {call_id_prefix!r} — matches:\n{listing}")

    call = _load_call(matches[0])
    if call is None:
        return red(f"Failed to parse {matches[0]}")
    return json.dumps(call, indent=2, default=str)
