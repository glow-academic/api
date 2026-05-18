# server/app/main.py
"""Thin entry-point — delegates everything to app.server.

Usage:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from dotenv import load_dotenv

load_dotenv()

from app.server import app, fastapi_app  # noqa: F401, E402

if __name__ == "__main__":
    import uvicorn

    # timeout_graceful_shutdown caps how long uvicorn waits for in-flight
    # connections before force-closing on SIGTERM / --reload / CTRL+C. Without
    # this, a hung MCP streamable-HTTP session keeps the port bound and the
    # next `uvicorn` bind fails with [Errno 48] Address already in use.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        timeout_graceful_shutdown=10,
    )
