"""Flask routes for the extracted moderation feature."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request, session
from pydantic import ValidationError

from server_panel.contracts import validation_failure
from server_panel.contracts.moderation import ServerTarget

from .models import InstallRequest, ModerationSettingsUpdate, ServiceResult, TicketAction
from .service import ModerationService

LoginDecorator = Callable[..., Callable[[Callable[..., Any]], Callable[..., Any]]]
ProxyCallback = Callable[[str, str, dict[str, Any], int], tuple[dict[str, Any], int] | None]
ClusterVerifier = Callable[[str, dict[str, Any]], None]
SignedVerifier = Callable[[], tuple[bool, str]]
ServerIdResolver = Callable[[], str | None]


def _response(result: ServiceResult):
    return jsonify(result.payload), result.status


def _validation_response(error: ValidationError):
    return jsonify(validation_failure(error)), 400


def _error_response(error: Exception):
    if isinstance(error, KeyError):
        return jsonify({"success": False, "error": str(error).strip("'")}), 404
    if isinstance(error, PermissionError):
        return jsonify({"success": False, "error": str(error)}), 403
    if isinstance(error, ValueError):
        return jsonify({"success": False, "error": str(error)}), 400
    return jsonify({"success": False, "error": str(error)}), 500


def create_routes(
    service: ModerationService,
    *,
    requires_login: LoginDecorator,
    proxy: ProxyCallback,
    verify_cluster_payload: ClusterVerifier,
    verify_signed_request: SignedVerifier,
    request_server_id: ServerIdResolver,
    default_dll_url: str,
) -> Blueprint:
    """Build route-compatible moderation handlers with strict request models."""
    del verify_cluster_payload
    blueprint = Blueprint("moderation", __name__, template_folder="templates", static_folder="static")

    def target(value: str) -> ServerTarget:
        return ServerTarget(server_id=value)

    def signed_failure():
        verified, message = verify_signed_request()
        if not verified:
            return jsonify({"success": False, "error": message}), 401
        return None

    @blueprint.get("/api/moderation/status")
    @requires_login()
    def status():
        try:
            server_id = target(str(request_server_id() or "")).server_id
        except ValidationError as error:
            return _validation_response(error)
        proxied = proxy(server_id, "/api/cluster/servers/moderation/status", {}, 20)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.status(server_id))
        except Exception as error:  # noqa: BLE001 - adapter maps stable public statuses
            return _error_response(error)

    @blueprint.get("/api/moderation/job")
    @requires_login()
    def install_job():
        try:
            server_id = target(str(request_server_id() or "")).server_id
        except ValidationError as error:
            return _validation_response(error)
        proxied = proxy(server_id, "/api/cluster/servers/moderation/job", {}, 15)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.install_job(server_id))
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/moderation/install")
    @requires_login("admin")
    def install():
        data = request.get_json(silent=True) or {}
        try:
            candidate = {
                **data,
                "server_id": data.get("server_id") or request_server_id() or "",
                "dll_url": data.get("dll_url") or default_dll_url,
            }
            install_request = InstallRequest.model_validate(candidate)
        except (TypeError, ValidationError) as error:
            if isinstance(error, ValidationError):
                return _validation_response(error)
            return jsonify({"success": False, "error": "Invalid request: JSON object required"}), 400
        payload = install_request.model_dump(mode="json")
        proxied = proxy(install_request.server_id, "/api/cluster/servers/moderation/install", payload, 60)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.start_install(install_request))
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.get("/api/moderation/state")
    @requires_login()
    def state():
        try:
            server_id = target(str(request.args.get("server_id") or "")).server_id
        except ValidationError as error:
            return _validation_response(error)
        proxied = proxy(server_id, "/api/cluster/servers/moderation/get_state", {}, 20)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.state(server_id))
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/moderation/settings")
    @requires_login(role="admin")
    def settings():
        data = request.get_json(force=True, silent=True) or {}
        try:
            update = ModerationSettingsUpdate.model_validate(data)
        except ValidationError as error:
            return _validation_response(error)
        payload = update.model_dump(mode="json", exclude_none=True)
        proxied = proxy(update.server_id, "/api/cluster/servers/moderation/set_settings", payload, 20)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.save_settings(update))
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/moderation/ticket_action")
    @requires_login()
    def ticket_action():
        data = request.get_json(force=True, silent=True) or {}
        try:
            action = TicketAction.model_validate(
                {**data, "actor": str(session.get("username") or "panel").strip() or "panel"}
            )
        except (TypeError, ValidationError) as error:
            if isinstance(error, ValidationError):
                return _validation_response(error)
            return jsonify({"success": False, "error": "Invalid request: JSON object required"}), 400
        payload = action.model_dump(mode="json", exclude_none=True)
        proxied = proxy(action.server_id, "/api/cluster/servers/moderation/ticket_action", payload, 30)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.ticket_action(action))
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/cluster/servers/moderation/status")
    def cluster_status():
        if failure := signed_failure():
            return failure
        try:
            value = ServerTarget.model_validate(request.get_json(silent=True) or {})
            return _response(service.status(value.server_id))
        except ValidationError as error:
            return _validation_response(error)
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/cluster/servers/moderation/job")
    def cluster_job():
        if failure := signed_failure():
            return failure
        try:
            value = ServerTarget.model_validate(request.get_json(silent=True) or {})
            return _response(service.install_job(value.server_id))
        except ValidationError as error:
            return _validation_response(error)
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/cluster/servers/moderation/install")
    def cluster_install():
        if failure := signed_failure():
            return failure
        data = request.get_json(silent=True) or {}
        try:
            value = InstallRequest.model_validate({**data, "dll_url": data.get("dll_url") or default_dll_url})
            return _response(service.start_install(value))
        except (TypeError, ValidationError) as error:
            if isinstance(error, ValidationError):
                return _validation_response(error)
            return jsonify({"success": False, "error": "Invalid request: JSON object required"}), 400
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/cluster/servers/moderation/get_state")
    def cluster_state():
        if failure := signed_failure():
            return failure
        try:
            value = ServerTarget.model_validate(request.get_json(force=True, silent=True) or {})
            return _response(service.state(value.server_id))
        except ValidationError as error:
            return _validation_response(error)
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/cluster/servers/moderation/set_settings")
    def cluster_settings():
        if failure := signed_failure():
            return failure
        try:
            value = ModerationSettingsUpdate.model_validate(request.get_json(force=True, silent=True) or {})
            return _response(service.save_settings(value))
        except ValidationError as error:
            return _validation_response(error)
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    @blueprint.post("/api/cluster/servers/moderation/ticket_action")
    def cluster_ticket_action():
        if failure := signed_failure():
            return failure
        try:
            action = TicketAction.model_validate(request.get_json(force=True, silent=True) or {})
            return _response(service.ticket_action(action))
        except ValidationError as error:
            return _validation_response(error)
        except Exception as error:  # noqa: BLE001
            return _error_response(error)

    return blueprint
