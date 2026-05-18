"""Bootstrap litellm SDK with model metadata from the LiteLLM proxy.

Called at startup so the SDK knows custom model aliases (e.g. glow-text)
support native streaming. Without this, litellm falls back to
MockResponsesAPIStreamingIterator for unknown models, which buffers
tool call events instead of streaming them.
"""

import os

import httpx

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def bootstrap_litellm_from_proxy() -> None:
    """Fetch model list from LiteLLM proxy and register in the SDK."""
    try:
        import litellm
    except ImportError:
        logger.debug("litellm not installed, skipping bootstrap")
        return

    proxy_url = os.getenv("AI_BASE_URL", "http://localhost:4000")
    api_key = os.getenv("AI_API_KEY", "")

    if not proxy_url:
        logger.debug("AI_BASE_URL not set, skipping litellm bootstrap")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{proxy_url}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            )
            resp.raise_for_status()
            data = resp.json()

        models = data.get("data", [])
        if not models:
            logger.warning("No models returned from proxy, skipping litellm bootstrap")
            return

        registered = 0
        for model in models:
            model_id = model.get("id", "")
            if not model_id:
                continue

            # Register with openai/ prefix (the protocol hint litellm SDK needs)
            key = f"openai/{model_id}"
            if key not in litellm.model_cost:
                litellm.model_cost[key] = {
                    "supports_native_streaming": True,
                    "max_tokens": 128000,
                    "input_cost_per_token": 0,
                    "output_cost_per_token": 0,
                }
                registered += 1

        logger.info(
            f"Registered {registered} proxy models in litellm SDK "
            f"(from {proxy_url}/v1/models)"
        )
    except Exception as e:
        logger.warning(f"litellm bootstrap failed (non-blocking): {e}")
