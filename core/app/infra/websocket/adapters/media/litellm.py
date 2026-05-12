"""LiteLLM-based media adapter for image/video generation."""

import uuid
from typing import Any

from app.infra.globals import get_pool, get_redis_client
from app.infra.media.upload import media_upload_impl
from app.infra.websocket.adapters.media.base import BaseMediaAdapter, MediaResult
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.utils.logging.db_logger import get_logger

try:
    import litellm  # type: ignore

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

logger = get_logger(__name__)


class LitellmMediaAdapter(BaseMediaAdapter):
    """Media adapter that uses litellm for image/video generation."""

    async def generate(
        self,
        modality: str,
        prompt: str,
        model: str,
        api_key: str,
        *,
        base_url: str | None = None,
        quality: str | None = None,
        extra_body: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> MediaResult:
        """Generate an image or video using litellm."""
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm is not available for media generation")

        ctx = context or {}
        sid = ctx.get("sid", "")
        run_id = ctx.get("run_id", "")
        group_id = ctx.get("group_id")
        artifact_type = ctx.get("artifact_type")
        resource_type = ctx.get("resource_type")
        resource_id = ctx.get("resource_id")
        # Pre-minted in ``execute_media_dispatch`` so the FE listener
        # can key its optimistic skeleton bubble by the same id as the
        # eventual persisted ``messages_entry`` row.
        message_id_for_emit = ctx.get("message_id")
        # Profile room for WS fan-out — every emit below stamps this
        # into ``rooms`` so observers beyond the originating socket
        # (other tabs, the make-debug panel) see media events too.
        profile_id = ctx.get("profile_id") or None
        metadata = ctx.get("metadata")

        await self._emitter.on_start(
            modality,
            sid=sid,
            run_id=run_id,
            group_id=group_id,
            artifact_type=artifact_type,
            resource_type=resource_type,
            resource_id=resource_id,
            message_id=message_id_for_emit,
            profile_id=profile_id,
            metadata=metadata,
        )

        try:
            if modality == "image":
                return await self._generate_image(
                    prompt=prompt,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    quality=quality,
                    extra_body=extra_body,
                    context=ctx,
                )
            elif modality == "video":
                return await self._generate_video(
                    prompt=prompt,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    quality=quality,
                    extra_body=extra_body,
                    context=ctx,
                )
            else:
                raise ValueError(f"Unsupported modality: {modality}")
        except Exception as e:
            logger.exception(
                "Media generation failed: modality=%s model=%s run_id=%s err=%s",
                modality, model, run_id, e,
            )
            await self._emitter.on_error(
                modality,
                sid=sid,
                run_id=run_id,
                group_id=group_id,
                artifact_type=artifact_type,
                resource_type=resource_type,
                resource_id=resource_id,
                message_id=message_id_for_emit,
                profile_id=profile_id,
                error_message=str(e),
                metadata=metadata,
            )
            raise

    async def _generate_image(
        self,
        prompt: str,
        model: str,
        api_key: str,
        *,
        base_url: str | None = None,
        quality: str | None = None,
        extra_body: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> MediaResult:
        """Generate an image using litellm.aimage_generation."""
        ctx = context or {}

        # Mirror the prefix logic from execute.py:_call_responses_api. LiteLLM
        # routes ``provider/model``; a bare custom alias like ``glow-image``
        # against a custom ``base_url`` raises ``BadRequestError: LLM Provider
        # NOT provided``. The ``openai/`` prefix tells LiteLLM to speak the
        # OpenAI-compatible protocol — which is what the LearnLoop proxy
        # implements — using ``base_url`` as the endpoint.
        effective_model = (
            f"openai/{model}" if base_url and "/" not in model else model
        )

        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "model": effective_model,
            "api_key": api_key,
        }
        if base_url:
            # litellm.aimage_generation routes through the OpenAI provider
            # client; that client honors ``api_base``, NOT ``base_url`` —
            # passing ``base_url`` is silently ignored and the request
            # hits OpenAI's real endpoint with our LearnLoop key, which
            # OpenAI rejects with ``invalid_api_key``. Same gotcha as
            # ``aresponses()`` in execute.py:_call_responses_api.
            kwargs["api_base"] = base_url
        if quality:
            kwargs["quality"] = quality
        if extra_body:
            kwargs.update(extra_body)

        logger.info(f"Image generation started: model={effective_model}")

        response = await litellm.aimage_generation(**kwargs)

        # Normalize: litellm.aimage_generation returns an ``ImageResponse``
        # pydantic-ish object whose ``.data`` is a list of ``ImageObject``
        # rows. Older paths returned plain dicts. Coerce both shapes into a
        # single ``data_list`` of dicts so the URL/b64 extraction below
        # doesn't have to handle two attribute styles.
        data_list: list[dict[str, Any]] | None = None
        if isinstance(response, dict):
            data_list = response.get("data")
        elif isinstance(response, str):
            data_list = [{"url": response}]
        elif hasattr(response, "data"):
            raw = response.data or []
            data_list = [
                d if isinstance(d, dict)
                else d.model_dump() if hasattr(d, "model_dump")
                else dict(d) if hasattr(d, "__iter__")
                else {"url": getattr(d, "url", None),
                       "b64_json": getattr(d, "b64_json", None)}
                for d in raw
            ]

        # Extract image URL or b64 from the first data item
        image_url = None
        image_bytes = None
        if data_list and len(data_list) > 0:
            data_item = data_list[0]
            image_url = data_item.get("url")
            if not image_url:
                b64_json = data_item.get("b64_json")
                if b64_json:
                    import base64
                    image_bytes = base64.b64decode(b64_json)

        if not image_url and not image_bytes:
            logger.error(
                "litellm.aimage_generation returned no usable data: "
                "type=%s repr=%.200s",
                type(response).__name__,
                repr(response),
            )
            raise RuntimeError("No image data returned from litellm")

        # Download image if URL provided
        if image_url and not image_bytes:
            import httpx

            async with httpx.AsyncClient() as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content

        if not image_bytes:
            raise RuntimeError("Failed to get image bytes")

        return await self._save_media(
            media_bytes=image_bytes,
            modality="image",
            context=ctx,
        )

    async def _generate_video(
        self,
        prompt: str,
        model: str,
        api_key: str,
        *,
        base_url: str | None = None,
        quality: str | None = None,
        extra_body: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> MediaResult:
        """Generate a video using litellm.avideo_generation + polling."""
        ctx = context or {}

        # See _generate_image for the prefix rationale.
        effective_model = (
            f"openai/{model}" if base_url and "/" not in model else model
        )

        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "model": effective_model,
            "api_key": api_key,
        }
        if base_url:
            # See _generate_image — avideo_generation also routes through
            # the OpenAI provider client, which honors ``api_base`` not
            # ``base_url``.
            kwargs["api_base"] = base_url
        if quality:
            kwargs["quality"] = quality
        if extra_body:
            kwargs.update(extra_body)

        logger.info(f"Video generation started: model={effective_model}")

        response = await litellm.avideo_generation(**kwargs)

        # Extract the polling handle. OpenAI's video API returns a
        # ``Video`` resource shaped like ``{"id": "video_…", "status":
        # "in_progress", …}``. Older / alternative clients sometimes
        # surface it as ``.generation_id``. Coerce any object shape
        # (pydantic ``Video``, plain object, ``ImageResponse``-style) to
        # a dict first so the field lookup below is uniform.
        if isinstance(response, dict):
            response_dict = response
        elif hasattr(response, "model_dump"):
            response_dict = response.model_dump()
        else:
            response_dict = {
                attr: getattr(response, attr, None)
                for attr in ("id", "generation_id", "status", "object")
                if hasattr(response, attr)
            }
        generation_id = (
            response_dict.get("generation_id")
            or response_dict.get("id")
        )

        if not generation_id:
            logger.error(
                "litellm.avideo_generation returned no id field: "
                "type=%s keys=%s repr=%.200s",
                type(response).__name__,
                sorted(response_dict.keys()),
                repr(response),
            )
            raise RuntimeError(
                "No generation_id returned from video generation",
            )

        # Poll for completion
        import asyncio
        import time

        sid = ctx.get("sid", "")
        run_id = ctx.get("run_id", "")
        group_id = ctx.get("group_id")
        artifact_type = ctx.get("artifact_type")
        resource_type = ctx.get("resource_type")
        resource_id = ctx.get("resource_id")
        metadata = ctx.get("metadata")

        # Poll cadence: tight at the start so cache hits (~100ms server-
        # side) round-trip in ~1s instead of waiting a full 5s tick, then
        # ramp to 5s for genuine generations. Same total budget (~10min)
        # at the wider tail. ``max_polls`` no longer corresponds to a
        # fixed wall-clock window — we cap on elapsed time instead.
        # Check-then-sleep order so the loop exits on the same tick the
        # status flips, not one tick after.
        first_interval_s = 0.3
        steady_interval_s = 5.0
        ramp_after_seconds = 5.0   # within first 5s, poll fast
        timeout_seconds = 600.0    # 10 min hard cap

        started_at = time.monotonic()
        poll_index = 0
        status = None
        status_dict: dict = {}
        while True:
            poll_index += 1
            try:
                status_response = await litellm.avideo_status(
                    video_id=generation_id,
                    api_key=api_key,
                    api_base=base_url if base_url else None,
                    # Pin the provider transformer. ``avideo_status`` has
                    # no ``model`` argument to anchor inference on, so
                    # without this litellm guesses — and a wrong guess
                    # would route to the wrong transformer and surface
                    # as a malformed-response error. We always speak the
                    # OpenAI-compatible protocol against the LearnLoop
                    # proxy, mirroring the generation call.
                    custom_llm_provider="openai",
                )
            except Exception as e:
                # Surface the raw upstream error so we can diagnose the
                # actual failure (e.g. proxy 500, missing route). Without
                # this the only signal is litellm's pydantic validation
                # error against the canned VideoObject shape — useless.
                logger.error(
                    "avideo_status failed: video_id=%s api_base=%s err_type=%s err=%.500s",
                    generation_id, base_url, type(e).__name__, repr(e),
                )
                raise

            # Normalize the status payload the same way we did for the
            # initial generation response — object / pydantic / dict all
            # collapse to ``status_dict`` so we don't fight three shapes.
            if isinstance(status_response, dict):
                status_dict = status_response
            elif hasattr(status_response, "model_dump"):
                status_dict = status_response.model_dump()
            else:
                status_dict = {
                    attr: getattr(status_response, attr, None)
                    for attr in ("status", "error", "id")
                    if hasattr(status_response, attr)
                }
            status = status_dict.get("status")

            if status == "complete" or status == "completed":
                break

            if status == "failed" or status == "error":
                error_msg = status_dict.get("error") or "Video generation failed"
                raise RuntimeError(error_msg)

            elapsed = time.monotonic() - started_at
            if elapsed >= timeout_seconds:
                raise RuntimeError("Video generation timed out")

            await self._emitter.on_progress(
                "video",
                sid=sid,
                run_id=run_id,
                group_id=group_id,
                artifact_type=artifact_type,
                resource_type=resource_type,
                resource_id=resource_id,
                message_id=ctx.get("message_id"),
                profile_id=ctx.get("profile_id") or None,
                message=f"Video generation in progress (poll #{poll_index})",
                metadata=metadata,
            )

            # Tight cadence for the first few seconds, then back off to
            # the steady interval. Cache hits land in the tight window;
            # real generations spend most of their time in the steady
            # phase where 5s polling is plenty.
            interval = (
                first_interval_s
                if elapsed < ramp_after_seconds
                else steady_interval_s
            )
            await asyncio.sleep(interval)

        # Get video content. The shape depends on the backend:
        #   - LearnLoop/OpenAI ``/v1/videos/{id}/content`` returns the
        #     raw mp4 bytes inline → we get ``bytes`` (or an httpx-
        #     style object with ``.content`` / ``.read()``).
        #   - Some clients return a JSON envelope with a signed URL
        #     pointing at object storage → we fetch from that URL.
        # Cover both without forcing one shape.
        content_response = await litellm.avideo_content(
            video_id=generation_id,
            api_key=api_key,
            api_base=base_url if base_url else None,
        )

        video_url = None
        video_bytes: bytes | None = None

        if isinstance(content_response, (bytes, bytearray)):
            video_bytes = bytes(content_response)
        elif hasattr(content_response, "content") and isinstance(
            getattr(content_response, "content"), (bytes, bytearray),
        ):
            video_bytes = bytes(content_response.content)
        elif hasattr(content_response, "read"):
            data = content_response.read()
            if asyncio.iscoroutine(data):
                data = await data
            if isinstance(data, (bytes, bytearray)):
                video_bytes = bytes(data)
        elif isinstance(content_response, dict):
            video_url = content_response.get("url")
            if not video_url and isinstance(content_response.get("data"), dict):
                video_url = content_response["data"].get("url")
        elif hasattr(content_response, "url"):
            video_url = content_response.url

        if video_url and not video_bytes:
            import httpx

            async with httpx.AsyncClient() as client:
                video_response = await client.get(video_url)
                video_response.raise_for_status()
                video_bytes = video_response.content

        if not video_bytes:
            logger.error(
                "litellm.avideo_content returned no usable bytes: type=%s repr=%.200s",
                type(content_response).__name__, repr(content_response),
            )
            raise RuntimeError("Failed to get video bytes")

        return await self._save_media(
            media_bytes=video_bytes,
            modality="video",
            context=ctx,
        )

    async def _save_media(
        self,
        media_bytes: bytes,
        modality: str,
        context: dict[str, Any],
    ) -> MediaResult:
        """Persist generated media via the canonical media upload chain.

        Format detection happens here; the full chain (uploads_entry →
        <m>s_resource → <m>s_entry + junction → <m>_uploads_entry) runs
        inside ``media_upload_impl``.
        """
        if modality == "image":
            file_ext, mime_type = self._detect_image_format(media_bytes)
        else:
            file_ext, mime_type = self._detect_video_format(media_bytes)

        filename = f"{uuid.uuid4()}{file_ext}"

        # Resolve session_id with the canonical caller-first precedence.
        # The agentic/tool-dispatch path (nested ``Scenario_Generate`` call)
        # has no fresh socket handshake, so the sid→session map in Redis
        # is empty for it — but ``prepared.session_id`` is the parent
        # caller's real session and gets threaded through context. The
        # FE-driven path may not pass session_id explicitly; fall back to
        # the socket lookup for that case.
        sid = context.get("sid", "")
        session_id_str = context.get("session_id")
        if not session_id_str and sid:
            session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            raise RuntimeError(
                "Session not resolvable — pass session_id in context "
                "or open a socket so find_session_by_socket can map sid."
            )
        session_uuid = (
            session_id_str if isinstance(session_id_str, uuid.UUID)
            else uuid.UUID(str(session_id_str))
        )

        # Attribute this upload to the current run so the canonical
        # ``run_id → message → upload`` junction exists (the same shape
        # ``create_tool_call`` writes for agentic tool-produced uploads).
        # Without this, pure media-dispatch runs leave no trace linking
        # the produced asset back to their run.
        run_id_str = context.get("run_id")
        run_uuid: uuid.UUID | None = None
        if run_id_str:
            try:
                run_uuid = uuid.UUID(str(run_id_str))
            except (ValueError, TypeError):
                run_uuid = None

        # Pre-minted by ``execute_media_dispatch`` so the FE listener's
        # skeleton (on ``image.start``) and the persisted message row
        # share the same id. ``media_upload_impl`` honors it as the
        # explicit ``id`` on the ``messages_entry`` INSERT.
        message_id_str = context.get("message_id")
        message_uuid: uuid.UUID | None = None
        if message_id_str:
            try:
                message_uuid = uuid.UUID(str(message_id_str))
            except (ValueError, TypeError):
                message_uuid = None

        upload_result = await media_upload_impl(
            get_pool(), get_redis_client(),
            modality=modality,
            session_id=session_uuid,
            file_bytes=media_bytes,
            filename=filename,
            content_type=mime_type,
            run_id=run_uuid,
            attribute_to_run=run_uuid is not None,
            message_id=message_uuid,
            # Caller-supplied label + derived description threaded
            # through by ``execute_media_dispatch``. Empty/None values
            # let ``media_upload_impl`` fall back to its UUID-based
            # default name and an empty description.
            name=context.get("title") or "",
            description=context.get("description") or "",
        )

        images_id = str(upload_result.resource_id) if modality == "image" else None
        videos_id = str(upload_result.resource_id) if modality == "video" else None
        audios_id = str(upload_result.resource_id) if modality == "audio" else None

        result = MediaResult(
            file_path=upload_result.file_path,
            mime_type=upload_result.mime_type,
            file_size=upload_result.file_size,
            upload_id=str(upload_result.upload_id),
            images_id=images_id,
            videos_id=videos_id,
            audios_id=audios_id,
            message_id=(
                str(upload_result.message_id)
                if upload_result.message_id else None
            ),
        )

        # Emit completion
        sid = context.get("sid", "")
        run_id = context.get("run_id", "")
        group_id = context.get("group_id")
        artifact_type = context.get("artifact_type")
        resource_type = context.get("resource_type")
        resource_id = context.get("resource_id")
        metadata = context.get("metadata")

        await self._emitter.on_complete(
            modality,
            sid=sid,
            run_id=run_id,
            group_id=group_id,
            artifact_type=artifact_type,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            profile_id=context.get("profile_id") or None,
            metadata=metadata,
        )

        logger.info(
            "Media generation completed: modality=%s, upload_id=%s, "
            "images_id=%s, videos_id=%s, file_path=%s, size=%s",
            modality, result.upload_id, result.images_id, result.videos_id,
            result.file_path, result.file_size,
        )

        return result

    @staticmethod
    def _detect_image_format(data: bytes) -> tuple[str, str]:
        """Detect image format from magic bytes."""
        if data.startswith(b"\x89PNG"):
            return ".png", "image/png"
        elif data.startswith(b"\xff\xd8"):
            return ".jpg", "image/jpeg"
        elif data.startswith(b"GIF"):
            return ".gif", "image/gif"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return ".webp", "image/webp"
        return ".png", "image/png"

    @staticmethod
    def _detect_video_format(data: bytes) -> tuple[str, str]:
        """Detect video format from magic bytes."""
        if data[4:8] == b"ftyp":
            return ".mp4", "video/mp4"
        elif data.startswith(b"\x1a\x45\xdf\xa3"):
            return ".webm", "video/webm"
        return ".mp4", "video/mp4"
