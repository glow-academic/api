"""LearnLoop API client — phone-home for usage authorization."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.infra.ledger.types import LearnLoopCheckpoint
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

DEFAULT_LEARNLOOP_URL = "https://api.learnloop.co"
PHONE_HOME_TIMEOUT = 10  # seconds


def _learnloop_url() -> str:
    return os.getenv("LEARNLOOP_API_URL", DEFAULT_LEARNLOOP_URL).rstrip("/")


def _deployment_token() -> str:
    token = os.getenv("DEPLOYMENT_TOKEN", "")
    if not token:
        raise RuntimeError("DEPLOYMENT_TOKEN is required for usage verification")
    return token


async def phone_home(
    *,
    current_sequence: int,
    current_hash: str,
    attempts_since_last_check: int,
) -> LearnLoopCheckpoint:
    """Call LearnLoop to report usage and get authorization.

    Sends the current ledger state so LearnLoop can verify chain integrity
    on its end. Returns checkpoint metadata (authorized, num_left, etc.).
    """
    url = f"{_learnloop_url()}/provision/usage/check"
    payload: dict[str, Any] = {
        "current_sequence": current_sequence,
        "current_hash": current_hash,
        "attempts_since_last_check": attempts_since_last_check,
    }
    headers = {
        "Authorization": f"Bearer {_deployment_token()}",
    }

    try:
        async with httpx.AsyncClient(timeout=PHONE_HOME_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return LearnLoopCheckpoint(**data)
    except httpx.HTTPStatusError as e:
        logger.error(f"LearnLoop returned {e.response.status_code}: {e.response.text}")
        raise
    except httpx.ConnectError:
        logger.error("LearnLoop unreachable — cannot phone home")
        raise
    except Exception:
        logger.exception("Unexpected error during LearnLoop phone-home")
        raise
