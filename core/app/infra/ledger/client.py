"""LearnLoop API client — phone-home for usage authorization."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.infra.ledger.types import LearnLoopCheckpoint, UserUsage
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
    started: int = 0,
    completed: int = 0,
    passed: int = 0,
    user_usage: list[UserUsage] | None = None,
    current_profile_id: str | None = None,
    current_email: str | None = None,
    current_name: str | None = None,
) -> LearnLoopCheckpoint:
    """Call LearnLoop to report usage and get authorization.

    Sends the current ledger state + outcome counters (running totals).
    LearnLoop diffs against its last known state to record deltas.

    Also sends:
    - user_usage: per-user deltas since last checkpoint (for auditing/billing)
    - current_profile_id/email/name: the user requesting this attempt
      (so LearnLoop can make per-user authorization decisions)
    """
    url = f"{_learnloop_url()}/provision/usage/check"
    payload: dict[str, Any] = {
        "current_sequence": current_sequence,
        "current_hash": current_hash,
        "attempts_since_last_check": attempts_since_last_check,
        "started": started,
        "completed": completed,
        "passed": passed,
    }
    # Per-user usage deltas since last checkpoint
    if user_usage:
        payload["user_usage"] = [u.model_dump(exclude_none=True) for u in user_usage]
    # Current user requesting this attempt (for per-user auth decisions)
    if current_profile_id:
        payload["current_user"] = {
            "profile_id": current_profile_id,
            **({"email": current_email} if current_email else {}),
            **({"name": current_name} if current_name else {}),
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
