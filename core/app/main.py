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

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
