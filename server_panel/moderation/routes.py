"""Flask routes for the extracted moderation feature."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request, session

from .models import InstallRequest, ServiceResult, TicketAction
from .service import ModerationService

LoginDecorator = Callable[..., Callable[[Callable[..., Any]], Callable[..., Any]]]
ProxyCallback = Callable[[str, str, dict[str, Any], int], tuple[dict[str, Any], int] | None]
ClusterVerifier = Callable[[str, dict[str, Any]], None]
SignedVerifier = Callable[[], tuple[bool, str]]
ServerIdResolver = Callable[[], str | None]


def _response(result: ServiceResult):
    return jsonify(result.payload), result.status


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
    """Build the route-compatible moderation blueprint."""
    blueprint = Blueprint("moderation", __name__, template_folder="templates", static_folder="static")

    @blueprint.get("/api/moderation/status")
    @requires_login()
    def status():
        server_id = str(request_server_id() or "").strip()
        proxied = proxy(server_id, "/api/cluster/servers/moderation/status", {}, 20)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.status(server_id))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @blueprint.get("/api/moderation/job")
    @requires_login()
    def install_job():
        server_id = str(request_server_id() or "").strip()
        proxied = proxy(server_id, "/api/cluster/servers/moderation/job", {}, 15)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        return _response(service.install_job(server_id))

    @blueprint.post("/api/moderation/install")
    @requires_login("admin")
    def install():
        data = request.get_json(silent=True) or {}
        server_id = str(data.get("server_id") or request_server_id() or "").strip()
        dll_url = str(data.get("dll_url") or default_dll_url).strip() or default_dll_url
        proxied = proxy(
            server_id,
            "/api/cluster/servers/moderation/install",
            {"server_id": server_id, "dll_url": dll_url},
            60,
        )
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.start_install(InstallRequest(server_id, dll_url)))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @blueprint.get("/api/moderation/state")
    @requires_login()
    def state():
        server_id = str(request.args.get("server_id") or "").strip()
        proxied = proxy(server_id, "/api/cluster/servers/moderation/get_state", {}, 20)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.state(server_id))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 500

    @blueprint.post("/api/moderation/settings")
    @requires_login(role="admin")
    def settings():
        data = request.get_json(force=True, silent=True) or {}
        server_id = str(data.get("server_id") or "").strip()
        proxied = proxy(server_id, "/api/cluster/servers/moderation/set_settings", data, 20)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            return _response(service.save_settings(server_id, data))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 500

    @blueprint.post("/api/moderation/ticket_action")
    @requires_login()
    def ticket_action():
        data = request.get_json(force=True, silent=True) or {}
        server_id = str(data.get("server_id") or "").strip()
        actor = str(data.get("actor") or session.get("username") or "panel").strip() or "panel"
        data["actor"] = actor
        proxied = proxy(server_id, "/api/cluster/servers/moderation/ticket_action", data, 30)
        if proxied:
            return jsonify(proxied[0]), proxied[1]
        try:
            action = TicketAction(
                server_id=server_id,
                steam_id=str(data.get("steam_id") or "").strip(),
                action=str(data.get("action") or "").strip(),
                actor=actor,
                text=str(data.get("text")) if data.get("text") is not None else None,
            )
            return _response(service.ticket_action(action))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 500

    @blueprint.post("/api/cluster/servers/moderation/status")
    def cluster_status():
        try:
            data = request.get_json(silent=True) or {}
            server_id = str(data.get("server_id") or "").strip()
            verify_cluster_payload(server_id, data)
            return _response(service.status(server_id))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @blueprint.post("/api/cluster/servers/moderation/job")
    def cluster_job():
        try:
            data = request.get_json(silent=True) or {}
            server_id = str(data.get("server_id") or "").strip()
            verify_cluster_payload(server_id, data)
            return _response(service.install_job(server_id))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @blueprint.post("/api/cluster/servers/moderation/install")
    def cluster_install():
        try:
            data = request.get_json(silent=True) or {}
            server_id = str(data.get("server_id") or "").strip()
            dll_url = str(data.get("dll_url") or default_dll_url).strip() or default_dll_url
            verify_cluster_payload(server_id, data)
            return _response(service.start_install(InstallRequest(server_id, dll_url)))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @blueprint.post("/api/cluster/servers/moderation/get_state")
    def cluster_state():
        verified, message = verify_signed_request()
        if not verified:
            return jsonify({"success": False, "error": message}), 401
        data = request.get_json(force=True, silent=True) or {}
        try:
            return _response(service.state(str(data.get("server_id") or "").strip()))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 500

    @blueprint.post("/api/cluster/servers/moderation/set_settings")
    def cluster_settings():
        verified, message = verify_signed_request()
        if not verified:
            return jsonify({"success": False, "error": message}), 401
        data = request.get_json(force=True, silent=True) or {}
        try:
            return _response(service.save_settings(str(data.get("server_id") or "").strip(), data))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 500

    @blueprint.post("/api/cluster/servers/moderation/ticket_action")
    def cluster_ticket_action():
        verified, message = verify_signed_request()
        if not verified:
            return jsonify({"success": False, "error": message}), 401
        data = request.get_json(force=True, silent=True) or {}
        try:
            action = TicketAction(
                server_id=str(data.get("server_id") or "").strip(),
                steam_id=str(data.get("steam_id") or "").strip(),
                action=str(data.get("action") or "").strip(),
                actor=str(data.get("actor") or "panel").strip() or "panel",
                text=str(data.get("text")) if data.get("text") is not None else None,
            )
            return _response(service.ticket_action(action))
        except Exception as error:
            return jsonify({"success": False, "error": str(error)}), 500

    return blueprint
