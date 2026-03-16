"""WebSocket handler wrapper for consistency."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.typed_emit import emit_to_client

TRequest = TypeVar("TRequest", bound=BaseModel)
TResponse = TypeVar("TResponse", bound=BaseModel)


def is_generate_error_event(error_event_name: str | None) -> bool:
    """Return whether the error should route through the generate_error path."""
    return error_event_name == "generate_error"


def find_profile_id_for_sid(
    socket_owner: dict[str, str],
    sid: str,
) -> str | None:
    """Reverse-lookup a profile id from the in-memory socket owner mapping."""
    for profile_id, owner_sid in socket_owner.items():
        if owner_sid == sid:
            return profile_id
    return None


def build_client_error_payload(message: str) -> dict[str, Any]:
    """Build the standard client-facing error payload shape."""
    return {
        "success": False,
        "message": message,
    }


def build_profile_lookup_failed_message(lookup_error: Exception) -> str:
    """Build a consistent lookup failure message."""
    return f"Profile lookup failed: {str(lookup_error)}"


def build_handler_error_message(error: Exception) -> str:
    """Build a consistent handler failure message."""
    return f"Handler error: {str(error)}"


def build_validation_payload(
    data: dict[str, Any],
    request_type: type[TRequest],
) -> dict[str, Any]:
    """Strip transport-only fields unless the request model declares them."""
    model_fields = getattr(request_type, "model_fields", {})
    fields_to_remove = []
    if "sid" not in model_fields:
        fields_to_remove.append("sid")
    if "group_id" not in model_fields:
        fields_to_remove.append("group_id")
    return {k: v for k, v in data.items() if k not in fields_to_remove}


def build_generate_error_forward_payload(
    sid: str,
    data: dict[str, Any],
    error_message: str,
) -> dict[str, Any]:
    """Build the internal payload forwarded to generate_error handlers."""
    return {
        "sid": sid,
        "error_message": error_message,
        "resource_id": data.get("resource_id"),
        "group_id": data.get("group_id"),
        "resource_type": data.get("resource_type"),
    }


def build_generate_error_validation_payload(
    sid: str,
    data: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    """Build a validation-style payload for generate_error emission."""
    return {
        "sid": sid,
        "success": False,
        "message": message,
        "resource_id": data.get("resource_id"),
        "group_id": data.get("group_id"),
    }


async def handle_client_event(
    sid: str,
    data: dict[str, Any],
    request_type: type[TRequest],
    handler: Callable[[str, TRequest, uuid.UUID], Awaitable[None]],
    error_event_name: str | None = None,
    error_response_type: type[TResponse] | None = None,
) -> None:
    """Wrapper for client-to-server event handlers.

    Handles:
    - Profile ID lookup from sid
    - Request validation with auto-generated types
    - Error handling and emission

    Args:
        sid: Socket ID
        data: Raw event data
        request_type: Auto-generated ApiRequest type
        handler: Implementation function (sid, validated_request, profile_id)
        error_event_name: Optional error event name for error emission
        error_response_type: Optional error response type
    """
    try:
        # Get profile_id from sid (O(1) Redis lookup)
        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            if error_event_name and error_response_type:
                await emit_to_client(
                    error_event_name,
                    error_response_type(
                        success=False,
                        message="No profile found for socket",
                    ),
                    room=sid,
                )
            return

        profile_id = uuid.UUID(profile_id_str)

        # Validate with auto-generated type
        validated = request_type(**data)
        await handler(sid, validated, profile_id)
        return
    except ValidationError:
        # Socket.IO logs validation errors automatically
        if error_event_name and error_response_type:
            await emit_to_client(
                error_event_name,
                error_response_type(
                    success=False,
                    message="Invalid payload",
                ),
                room=sid,
            )


async def handle_internal_event(
    data: dict[str, Any],
    request_type: type[TRequest],
    handler: Callable[[str, TRequest, uuid.UUID, uuid.UUID | None], Awaitable[None]],
    error_event_name: str | None = None,
    error_response_type: type[TResponse] | None = None,
) -> None:
    """Wrapper for internal (server-to-server) event handlers.

    Handles:
    - sid extraction
    - Profile ID lookup
    - group_id extraction
    - Request validation
    - Error handling

    Args:
        data: Raw event data with sid and group_id
        request_type: Auto-generated ApiRequest type
        handler: Implementation function (sid, validated_request, profile_id, group_id)
        error_event_name: Optional error event name
        error_response_type: Optional error response type
    """
    sid = data.get("sid")
    if not sid:
        return  # Socket.IO logs missing sid automatically

    try:
        # Get profile_id from sid (O(1) Redis lookup)
        # Wrap in try-catch to prevent recursion if lookup fails
        profile_id_str = None
        try:
            profile_id_str = await find_profile_by_socket(sid)
        except Exception as lookup_error:
            # If Redis lookup fails (e.g., recursion error), try in-memory fallback
            # This prevents infinite recursion while still allowing error propagation
            try:
                from app.infra.globals import get_socket_owner_dict

                socket_owner = get_socket_owner_dict()
                profile_id_str = find_profile_id_for_sid(socket_owner, sid)
            except Exception:
                # If even in-memory lookup fails, we can't proceed
                # But we should still emit an error to the client
                if error_event_name:
                    try:
                        # Emit error directly to client using sid as room (doesn't require profile lookup)
                        from app.infra.globals import sio

                        if is_generate_error_event(error_event_name):
                            # For generate_error, emit to internal bus
                            from app.infra.globals import get_internal_sio

                            internal_sio = get_internal_sio()
                            await internal_sio.emit(
                                error_event_name,
                                build_generate_error_forward_payload(
                                    sid,
                                    data,
                                    build_profile_lookup_failed_message(lookup_error),
                                ),
                            )
                        else:
                            # For other errors, emit directly to client
                            await sio.emit(
                                error_event_name,
                                build_client_error_payload(
                                    build_profile_lookup_failed_message(lookup_error)
                                ),
                                room=sid,
                            )
                    except Exception:
                        # If emitting also fails, just return silently to prevent infinite recursion
                        pass
                return

        if not profile_id_str:
            if error_event_name and error_response_type:
                # Special handling for generate_error - emit to internal bus
                if is_generate_error_event(error_event_name):
                    try:
                        from app.infra.globals import get_internal_sio

                        internal_sio = get_internal_sio()
                        await internal_sio.emit(
                            error_event_name,
                            build_generate_error_forward_payload(
                                sid,
                                data,
                                "No profile found for socket",
                            ),
                        )
                    except Exception:
                        pass
                else:
                    try:
                        await emit_to_client(
                            error_event_name,
                            error_response_type(
                                success=False,
                                message="No profile found for socket",
                            ),
                            room=sid,
                        )
                    except Exception:
                        pass
            return

        profile_id_uuid = uuid.UUID(profile_id_str)

        # Extract group_id (required for grouping runs)
        group_id_str = data.get("group_id")
        group_id_uuid = uuid.UUID(group_id_str) if group_id_str else None

        # Remove sid and group_id before validation (not in ApiRequest)
        # EXCEPTION: Some ApiRequest models (like GenerateErrorApiRequest) include sid as a field
        # Check if the model has 'sid' as a field - if so, keep it
        payload_dict = build_validation_payload(data, request_type)
        validated = request_type(**payload_dict)
        await handler(sid, validated, profile_id_uuid, group_id_uuid)
        return
    except ValidationError:
        # Socket.IO logs validation errors automatically
        # Special handling for generate_error - emit directly to avoid recursion
        if is_generate_error_event(error_event_name):
            if sid:
                try:
                    from app.infra.globals import get_internal_sio

                    internal_sio = get_internal_sio()
                    await internal_sio.emit(
                        "generate_error",
                        build_generate_error_validation_payload(
                            sid,
                            data,
                            "An error occurred while processing your request. Please try again or reconnect.",
                        ),
                    )
                except Exception:
                    pass
            return

        if error_event_name and error_response_type:
            # For other error events (not generate_error), try to emit to client
            if not is_generate_error_event(error_event_name):
                # For other error events, try to emit to client
                # But only if the error_response_type has the expected fields
                try:
                    await emit_to_client(
                        error_event_name,
                        error_response_type(
                            success=False,
                            message="Invalid payload",
                        ),
                        room=sid,
                    )
                except Exception:
                    # If error_response_type doesn't match, log and skip
                    pass
    except Exception as e:
        # Catch any other exceptions (like recursion errors) and prevent infinite loops
        # Don't try to emit errors from error handlers - just log and return
        if is_generate_error_event(error_event_name):
            # If we're in generate_error handler and hit an exception, don't recurse
            return
        # For other handlers, try to emit error but catch exceptions to prevent recursion
        if error_event_name and error_response_type and sid:
            try:
                if is_generate_error_event(error_event_name):
                    from app.infra.globals import get_internal_sio

                    internal_sio = get_internal_sio()
                    await internal_sio.emit(
                        error_event_name,
                        build_generate_error_forward_payload(
                            sid,
                            data,
                            build_handler_error_message(e),
                        ),
                    )
                else:
                    await emit_to_client(
                        error_event_name,
                        error_response_type(
                            success=False,
                            message=build_handler_error_message(e),
                        ),
                        room=sid,
                    )
            except Exception:
                # If emitting fails, don't recurse - just return
                pass
