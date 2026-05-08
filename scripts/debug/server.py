"""External debug panel — `make debug`.

A standalone dev tool. Lives outside ``core/`` so it can never affect
the live API. Spawns a small FastAPI app on port 8765 that's a *client*
of the API, never a participant in it.

When you run ``make debug`` you get three things at once:

  1. A web panel at http://localhost:8765 with two views:
       - Persistent calls dashboard (polls /data on this server).
       - Live event sidebar (paste your JWT, it opens a socket.io
         connection straight to the running API at :8000 — exactly
         what a browser client would do).
  2. The browser is auto-opened to that URL.
  3. A live tail in the terminal: every NEW file dropped under
     ``uploads/call/`` is printed as a one-liner with tool, status,
     latency, and short call_id. Ctrl-C exits both.

One-shot mode::

    make debug ARGS="--show <call_id_prefix>"

prints a single call's full JSON and exits without starting the server.
"""

from __future__ import annotations

import os
import statistics
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Sibling import — dashboard.py is alongside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import (  # noqa: E402
    DEFAULT_CALLS_DIR,
    _build_aggregate,
    _failure_reason,
    _is_success,
    _latency_ms,
    _load_call,
    _parse_since,
    _tool_identity,
    render_show,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8765
DEFAULT_API_BASE = os.environ.get("DEBUG_API_BASE", "http://localhost:8000")
TAIL_POLL_S = 1.0

app = FastAPI(title="Glow Debug Panel", openapi_url=None, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/config")
def config() -> dict:
    return {"api_base": DEFAULT_API_BASE}


def _strip_body(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k != "body"}


@app.get("/data")
def data(
    since: str = Query("1d"),
    tool: str | None = Query(None),
    failures: bool = Query(False),
) -> JSONResponse:
    try:
        since_dt = _parse_since(since)
    except ValueError as e:
        raise HTTPException(400, str(e))

    agg = _build_aggregate(
        DEFAULT_CALLS_DIR, since_dt, tool, failures, quiet=True
    )
    stats = agg.finalize(html_mode=True)

    top_tools = []
    for tool_name, b in stats["top_tools"]:
        lats = b["latencies"]
        p50 = statistics.median(lats) if lats else None
        if lats:
            p95 = (
                sorted(lats)[max(0, int(len(lats) * 0.95) - 1)]
                if len(lats) >= 5
                else max(lats)
            )
        else:
            p95 = None
        top_tools.append(
            {
                "tool": tool_name,
                "count": b["count"],
                "failures": b["failures"],
                "p50_ms": p50,
                "p95_ms": p95,
            }
        )

    return JSONResponse(
        {
            "total": stats["total"],
            "failures": stats["failures"],
            "disk_bytes": stats["disk_bytes"],
            "first_mtime": stats["first_mtime"],
            "last_mtime": stats["last_mtime"],
            "top_tools": top_tools,
            "recent_activity": [_strip_body(r) for r in stats["recent_activity"]],
            "recent_failures": [_strip_body(r) for r in stats["recent_failures"]],
            "generated_at": time.time(),
        }
    )


@app.get("/calls/{call_id}")
def get_call(call_id: str) -> JSONResponse:
    # Defensive: only allow hex/uuid-ish ids — these are filenames on disk.
    safe = call_id.replace("-", "").replace("_", "")
    if not safe.isalnum() or len(call_id) > 80:
        raise HTTPException(400, "invalid call id")

    direct = DEFAULT_CALLS_DIR / f"{call_id}.json"
    path: Path | None = direct if direct.exists() else None
    if path is None:
        for entry in os.scandir(DEFAULT_CALLS_DIR):
            if entry.name.startswith(call_id) and entry.name.endswith(".json"):
                path = Path(entry.path)
                break
    if path is None:
        raise HTTPException(404, "call not found")

    body = _load_call(path)
    if body is None:
        raise HTTPException(500, "could not parse call json")
    return JSONResponse(body)


# ---------------------------------------------------------------------------
# Live terminal tail — prints every NEW call file as it lands.
# ---------------------------------------------------------------------------

# ANSI codes inline (sys.stdout.isatty() check at use-site). This module
# is only ever invoked from a terminal via `make debug`, so colors are
# safe — and the few escape sequences here aren't worth a helper.
_DIM   = "\033[2m"
_BOLD  = "\033[1m"
_GREEN = "\033[32m"
_RED   = "\033[31m"
_RESET = "\033[0m"
_USE_COLOR = sys.stdout.isatty()


def _color(s: str, code: str) -> str:
    return f"{code}{s}{_RESET}" if _USE_COLOR else s


def _format_latency(ms: float | None) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def _print_call_line(path: Path, mtime: float) -> None:
    call = _load_call(path)
    if not call:
        return
    ts = time.strftime("%H:%M:%S", time.localtime(mtime))
    tool = _tool_identity(call)
    ok = _is_success(call)
    latency = _format_latency(_latency_ms(call))
    short_id = (call.get("call_id") or path.stem)[:8]
    icon = _color("✓", _GREEN) if ok else _color("✗", _RED)
    line = (
        f"{_color(ts, _DIM)}  {icon} {tool:<32} "
        f"{_color(latency.rjust(7), _DIM)}  {_color(f'call={short_id}', _DIM)}"
    )
    if not ok:
        line += "  " + _color(_failure_reason(call)[:60], _RED)
    print(line, flush=True)


def _tail_calls_loop(stop: threading.Event) -> None:
    """Poll uploads/call/ once a second; print only files we haven't
    seen yet. We seed `seen` with the current contents at startup so
    we don't dump the entire backlog on launch."""
    seen: set[str] = set()
    if DEFAULT_CALLS_DIR.exists():
        for entry in os.scandir(DEFAULT_CALLS_DIR):
            if entry.name.endswith(".json"):
                seen.add(entry.name)

    while not stop.is_set():
        try:
            if DEFAULT_CALLS_DIR.exists():
                new: list[tuple[float, Path]] = []
                for entry in os.scandir(DEFAULT_CALLS_DIR):
                    if not entry.name.endswith(".json") or entry.name in seen:
                        continue
                    seen.add(entry.name)
                    try:
                        new.append((entry.stat().st_mtime, Path(entry.path)))
                    except OSError:
                        pass
                new.sort()
                for mtime, path in new:
                    _print_call_line(path, mtime)
        except Exception as e:
            # A single bad iteration must not kill the tail thread.
            print(_color(f"[tail] error: {e!r}", _RED), flush=True)
        stop.wait(TAIL_POLL_S)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def _open_browser(port: int) -> None:
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass


def main() -> None:
    argv = sys.argv[1:]

    # One-shot subcommand: print one call's full JSON and exit.
    if len(argv) >= 2 and argv[0] == "--show":
        print(render_show(argv[1], DEFAULT_CALLS_DIR))
        return

    port = int(os.environ.get("DEBUG_PORT", DEFAULT_PORT))
    if not os.environ.get("DEBUG_NO_OPEN"):
        threading.Timer(0.8, _open_browser, args=(port,)).start()

    banner_label = _color("glow-debug", _BOLD)
    url = f"http://localhost:{port}"
    print(f"{banner_label} · {url}  (api={DEFAULT_API_BASE})")
    print(_color(
        f"  tailing {DEFAULT_CALLS_DIR} — new calls print below. Ctrl-C to exit.",
        _DIM,
    ))

    stop = threading.Event()
    tail = threading.Thread(target=_tail_calls_loop, args=(stop,), daemon=True)
    tail.start()

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        stop.set()


if __name__ == "__main__":
    main()
