"""LiteLLM-based media adapter for image/video generation."""

import logging
import uuid
from pathlib import Path
from typing import Any

from app.infra.globals import IMAGE_FOLDER, UPLOAD_FOLDER, VIDEO_FOLDER, get_pool
from app.infra.websocket.adapters.media.base import BaseMediaAdapter, MediaResult
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.tools.entries.uploads.create import create_upload

try:
    import litellm  # type: ignore

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

logger = logging.getLogger(__name__)


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
        metadata = ctx.get("metadata")

        await self._emitter.on_start(
            modality,
            sid=sid,
            run_id=run_id,
            group_id=group_id,
            artifact_type=artifact_type,
            resource_type=resource_type,
            resource_id=resource_id,
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
            await self._emitter.on_error(
                modality,
                sid=sid,
                run_id=run_id,
                group_id=group_id,
                artifact_type=artifact_type,
                resource_type=resource_type,
                resource_id=resource_id,
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

        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        if quality:
            kwargs["quality"] = quality
        if extra_body:
            kwargs.update(extra_body)

        logger.info(f"Image generation started: model={model}")

        response = await litellm.aimage_generation(**kwargs)

        # Extract image URL or b64 from response
        image_url = None
        image_bytes = None

        if isinstance(response, dict):
            if "data" in response and len(response["data"]) > 0:
                data_item = response["data"][0]
                image_url = data_item.get("url")
                if not image_url:
                    b64_json = data_item.get("b64_json")
                    if b64_json:
                        import base64

                        image_bytes = base64.b64decode(b64_json)
        elif isinstance(response, str):
            image_url = response

        if not image_url and not image_bytes:
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
            folder=IMAGE_FOLDER,
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

        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        if quality:
            kwargs["quality"] = quality
        if extra_body:
            kwargs.update(extra_body)

        logger.info(f"Video generation started: model={model}")

        response = await litellm.avideo_generation(**kwargs)

        # Extract generation_id for polling
        generation_id = None
        if isinstance(response, dict):
            generation_id = response.get("generation_id") or response.get("id")
        elif hasattr(response, "generation_id"):
            generation_id = response.generation_id

        if not generation_id:
            raise RuntimeError("No generation_id returned from video generation")

        # Poll for completion
        import asyncio

        sid = ctx.get("sid", "")
        run_id = ctx.get("run_id", "")
        group_id = ctx.get("group_id")
        artifact_type = ctx.get("artifact_type")
        resource_type = ctx.get("resource_type")
        resource_id = ctx.get("resource_id")
        metadata = ctx.get("metadata")

        max_polls = 120  # 10 minutes at 5s intervals
        for i in range(max_polls):
            await asyncio.sleep(5)

            status_response = await litellm.avideo_status(
                generation_id=generation_id,
                api_key=api_key,
                base_url=base_url if base_url else None,
            )

            status = None
            if isinstance(status_response, dict):
                status = status_response.get("status")
            elif hasattr(status_response, "status"):
                status = status_response.status

            if status == "complete" or status == "completed":
                break

            await self._emitter.on_progress(
                "video",
                sid=sid,
                run_id=run_id,
                group_id=group_id,
                artifact_type=artifact_type,
                resource_type=resource_type,
                resource_id=resource_id,
                message=f"Video generation in progress ({i + 1}/{max_polls})",
                metadata=metadata,
            )

            if status == "failed" or status == "error":
                error_msg = "Video generation failed"
                if isinstance(status_response, dict):
                    error_msg = status_response.get("error", error_msg)
                raise RuntimeError(error_msg)
        else:
            raise RuntimeError("Video generation timed out")

        # Get video content
        content_response = await litellm.avideo_content(
            generation_id=generation_id,
            api_key=api_key,
            base_url=base_url if base_url else None,
        )

        video_url = None
        video_bytes = None

        if isinstance(content_response, dict):
            video_url = content_response.get("url")
            if not video_url and "data" in content_response:
                video_url = content_response["data"].get("url")
        elif hasattr(content_response, "url"):
            video_url = content_response.url

        if video_url:
            import httpx

            async with httpx.AsyncClient() as client:
                video_response = await client.get(video_url)
                video_response.raise_for_status()
                video_bytes = video_response.content

        if not video_bytes:
            raise RuntimeError("Failed to get video bytes")

        return await self._save_media(
            media_bytes=video_bytes,
            folder=VIDEO_FOLDER,
            modality="video",
            context=ctx,
        )

    async def _save_media(
        self,
        media_bytes: bytes,
        folder: "Path",
        modality: str,
        context: dict[str, Any],
    ) -> MediaResult:
        """Save media bytes to disk and create upload record."""
        # Detect format and determine extension/mime
        if modality == "image":
            file_ext, mime_type = self._detect_image_format(media_bytes)
        else:
            file_ext, mime_type = self._detect_video_format(media_bytes)

        # Generate UUID filename and save
        upload_uuid = uuid.uuid4()
        file_path = f"{upload_uuid}{file_ext}"
        full_path = folder / file_path

        folder.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(media_bytes)

        file_size = len(media_bytes)

        # Relative path from UPLOAD_FOLDER for storage
        relative_path = str(full_path.relative_to(UPLOAD_FOLDER))

        # Resolve session from socket context
        sid = context.get("sid", "")
        session_id_str = await find_session_by_socket(sid) if sid else None
        if not session_id_str:
            raise RuntimeError("Session not found for socket — cannot create upload")

        pool = get_pool()
        async with pool.acquire() as conn:
            upload_result = await create_upload(
                conn,
                session_id=uuid.UUID(session_id_str),
                file_path=relative_path,
                mime_type=mime_type,
                size=file_size,
            )

        upload_id = str(upload_result.id)

        result = MediaResult(
            file_path=relative_path,
            mime_type=mime_type,
            file_size=file_size,
            upload_id=upload_id,
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
            metadata=metadata,
        )

        logger.info(
            f"Media generation completed: modality={modality}, "
            f"upload_id={upload_id}, file_path={relative_path}, size={file_size}"
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
