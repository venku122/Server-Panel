from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

from .db import Repository


ConnectionFactory = Callable[[], sqlite3.Connection]
OUTCOMES = ("success", "failure", "denied", "unknown")
_SENSITIVE_KEY = re.compile(
    r"authorization|cookie|credential|password|passwd|private.?key|secret|session|token|webhook|api.?key",
    re.IGNORECASE,
)
_MAX_DEPTH = 6
_MAX_ENTRIES = 50
_MAX_STRING_LENGTH = 4000
_MAX_PAGE_SIZE = 200
_PRIVATE_KEY_BEGIN = re.compile(r"-----BEGIN ([A-Z0-9 ]*PRIVATE KEY)-----", re.IGNORECASE)
LOGGER = logging.getLogger(__name__)
_LEGACY_ACTIONS = {
    "audit_logs_cleared": "panel.audit.cleared",
    "first_run_credentials_set": "panel.credentials.initialized",
    "ip_blocked": "panel.ip.blocked",
    "ip_unblocked": "panel.ip.unblocked",
    "login_success": "panel.login.succeeded",
    "logout": "panel.logout",
    "user_created": "panel.user.created",
    "user_deleted": "panel.user.deleted",
    "user_password_reset": "panel.user.password_reset",
}


def _redact_private_keys(value: str) -> str:
    cursor = 0
    output: list[str] = []
    while match := _PRIVATE_KEY_BEGIN.search(value, cursor):
        output.append(value[cursor : match.start()])
        output.append("[REDACTED PRIVATE KEY]")
        end_marker = f"-----END {match.group(1).upper()}-----"
        end_index = value.upper().find(end_marker, match.end())
        if end_index < 0:
            cursor = len(value)
            break
        cursor = end_index + len(end_marker)
    output.append(value[cursor:])
    return "".join(output)


def _redact_string(value: str) -> str:
    redacted = _redact_private_keys(value)
    redacted = re.sub(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+", r"\1[REDACTED]", redacted)
    redacted = re.sub(
        r"(?i)([?&](?:password|passwd|secret|token|access_token|api_key|key|signature|sig)=)[^&#\s]+",
        r"\1[REDACTED]",
        redacted,
    )
    if len(redacted) > _MAX_STRING_LENGTH:
        return redacted[:_MAX_STRING_LENGTH] + "… [truncated]"
    return redacted


def redact_payload(value: Any, depth: int = 0, seen: set[int] | None = None) -> Any:
    """Return bounded JSON-safe data with credential-shaped values removed."""
    if isinstance(value, str):
        return _redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth >= _MAX_DEPTH:
        return "[MAX DEPTH]"
    seen = seen if seen is not None else set()
    identity = id(value)
    if identity in seen:
        return "[CIRCULAR]"
    seen.add(identity)
    try:
        if isinstance(value, (list, tuple)):
            items = [redact_payload(item, depth + 1, seen) for item in value[:_MAX_ENTRIES]]
            if len(value) > _MAX_ENTRIES:
                items.append(f"[{len(value) - _MAX_ENTRIES} more items]")
            return items
        if isinstance(value, dict):
            output: dict[str, Any] = {}
            entries = list(value.items())
            for key, item in entries[:_MAX_ENTRIES]:
                normalized_key = str(key)
                output[normalized_key] = (
                    "[REDACTED]" if _SENSITIVE_KEY.search(normalized_key) else redact_payload(item, depth + 1, seen)
                )
            if len(entries) > _MAX_ENTRIES:
                output["__truncated__"] = f"{len(entries) - _MAX_ENTRIES} more keys"
            return output
        return _redact_string(str(value))
    finally:
        seen.remove(identity)


def serialize_payload(value: Any | None) -> str | None:
    if value is None:
        return None
    return json.dumps(redact_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deserialize_payload(value: str | None) -> Any | None:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return _redact_string(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalize_action(action: str) -> str:
    value = str(action or "unknown").strip()
    return _LEGACY_ACTIONS.get(value, value.replace("_", "."))


def _normalize_outcome(outcome: str | None) -> str:
    value = str(outcome or "success").strip().lower()
    return value if value in OUTCOMES else "unknown"


@dataclass(frozen=True)
class AuditEvent:
    id: int
    correlation_id: str
    actor: str
    action: str
    scope_type: str
    server_id: str | None
    target_type: str | None
    target_id: str | None
    outcome: str
    summary: str
    request_json: str | None
    response_json: str | None
    job_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        request_payload = _deserialize_payload(self.request_json)
        response_payload = _deserialize_payload(self.response_json)
        return {
            "id": self.id,
            "correlation_id": self.correlation_id,
            "actor": self.actor,
            "action": self.action,
            "action_label": self.action.replace(".", " ").replace("_", " ").title(),
            "scope_type": self.scope_type,
            "server_id": self.server_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_label": self.target_id or self.server_id or "Panel",
            "outcome": self.outcome,
            "summary": self.summary,
            "request": request_payload,
            "request_pretty": json.dumps(request_payload, ensure_ascii=False, indent=2)
            if request_payload is not None
            else None,
            "response": response_payload,
            "response_pretty": json.dumps(response_payload, ensure_ascii=False, indent=2)
            if response_payload is not None
            else None,
            "job_id": self.job_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AuditPage:
    events: tuple[AuditEvent, ...]
    next_cursor: str | None
    previous_cursor: str | None
    limit: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "next_cursor": self.next_cursor,
            "previous_cursor": self.previous_cursor,
            "limit": self.limit,
        }


def _encode_cursor(event: AuditEvent, direction: str) -> str:
    payload = json.dumps(
        {"created_at": event.created_at, "id": event.id, "direction": direction},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[str, int, str] | None:
    if not cursor:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
        created_at = str(payload["created_at"])
        event_id = int(payload["id"])
        direction = str(payload["direction"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("Invalid audit pagination cursor.") from error
    if not created_at or event_id < 1 or direction not in {"before", "after"}:
        raise ValueError("Invalid audit pagination cursor.")
    return created_at, event_id, direction


class AuditRepository(Repository):
    def _row_to_event(self, row: sqlite3.Row) -> AuditEvent:
        return AuditEvent(
            id=int(row["id"]),
            correlation_id=str(row["correlation_id"]),
            actor=str(row["actor"]),
            action=str(row["action"]),
            scope_type=str(row["scope_type"]),
            server_id=str(row["server_id"]) if row["server_id"] is not None else None,
            target_type=str(row["target_type"]) if row["target_type"] is not None else None,
            target_id=str(row["target_id"]) if row["target_id"] is not None else None,
            outcome=str(row["outcome"]),
            summary=str(row["summary"]),
            request_json=str(row["request_json"]) if row["request_json"] is not None else None,
            response_json=str(row["response_json"]) if row["response_json"] is not None else None,
            job_id=str(row["job_id"]) if row["job_id"] is not None else None,
            created_at=str(row["created_at"]),
        )

    def insert(
        self,
        *,
        correlation_id: str,
        actor: str,
        action: str,
        scope_type: str,
        server_id: str | None,
        target_type: str | None,
        target_id: str | None,
        outcome: str,
        summary: str,
        request_json: str | None,
        response_json: str | None,
        job_id: str | None,
        created_at: str,
        legacy_key: str,
    ) -> tuple[AuditEvent, bool]:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO audit_events (
                correlation_id, actor, action, scope_type, server_id, target_type, target_id,
                outcome, summary, request_json, response_json, job_id, legacy_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correlation_id,
                actor,
                action,
                scope_type,
                server_id,
                target_type,
                target_id,
                outcome,
                summary,
                request_json,
                response_json,
                job_id,
                legacy_key,
                created_at,
            ),
        )
        inserted = cursor.rowcount == 1
        row = self.connection.execute("SELECT * FROM audit_events WHERE legacy_key = ?", (legacy_key,)).fetchone()
        if row is None:
            raise RuntimeError("Audit event insert did not produce a readable record.")
        return self._row_to_event(row), inserted

    def list_events(
        self,
        *,
        server_id: str | None = None,
        outcome: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> AuditPage:
        clauses: list[str] = []
        parameters: list[Any] = []
        if server_id:
            clauses.append("server_id = ?")
            parameters.append(server_id)
        if outcome:
            clauses.append("outcome = ?")
            parameters.append(_normalize_outcome(outcome))
        if actor:
            clauses.append("actor = ?")
            parameters.append(actor)
        if action:
            clauses.append("action = ?")
            parameters.append(_normalize_action(action))
        decoded_cursor = _decode_cursor(cursor)
        direction = "before"
        if decoded_cursor is not None:
            created_at, event_id, direction = decoded_cursor
            operator = "<" if direction == "before" else ">"
            clauses.append(f"(created_at {operator} ? OR (created_at = ? AND id {operator} ?))")
            parameters.extend((created_at, created_at, event_id))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        page_size = max(1, min(int(limit), _MAX_PAGE_SIZE))
        parameters.append(page_size + 1)
        order = "ASC" if direction == "after" else "DESC"
        rows = self.connection.execute(
            f"SELECT * FROM audit_events{where} ORDER BY created_at {order}, id {order} LIMIT ?",  # noqa: S608
            parameters,
        ).fetchall()
        has_more_in_direction = len(rows) > page_size
        selected_rows = rows[:page_size]
        if direction == "after":
            selected_rows.reverse()
        events = tuple(self._row_to_event(row) for row in selected_rows)
        if not events:
            return AuditPage((), None, None, page_size)

        has_newer = has_more_in_direction if direction == "after" else decoded_cursor is not None
        has_older = has_more_in_direction if direction == "before" else decoded_cursor is not None
        return AuditPage(
            events,
            _encode_cursor(events[-1], "before") if has_older else None,
            _encode_cursor(events[0], "after") if has_newer else None,
            page_size,
        )

    def clear(self) -> None:
        self.connection.execute("DELETE FROM audit_events")


class AuditService:
    def __init__(self, connection_factory: ConnectionFactory, legacy_path: Path) -> None:
        self.connection_factory = connection_factory
        self.legacy_path = legacy_path
        self._mirror_lock = threading.Lock()
        self._mirror_failures = 0
        self._mirror_last_error: str | None = None
        self._mirror_last_failed_at: str | None = None

    def record(
        self,
        *,
        actor: str | None,
        action: str,
        correlation_id: str | None = None,
        scope_type: str = "global",
        server_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        outcome: str = "success",
        summary: str | None = None,
        request_payload: Any | None = None,
        response_payload: Any | None = None,
        job_id: str | None = None,
        created_at: str | None = None,
        legacy_key: str | None = None,
        mirror_legacy: bool = True,
    ) -> tuple[AuditEvent, bool]:
        normalized_action = _normalize_action(action)
        normalized_scope = scope_type if scope_type in {"global", "server", "system"} else "system"
        normalized_correlation = str(correlation_id or uuid.uuid4())
        normalized_legacy_key = legacy_key or f"live:{normalized_correlation}:{uuid.uuid4()}"
        repository = AuditRepository(self.connection_factory())
        with repository.transaction():
            event, inserted = repository.insert(
                correlation_id=normalized_correlation,
                actor=str(actor or "system"),
                action=normalized_action,
                scope_type=normalized_scope,
                server_id=str(server_id) if server_id else None,
                target_type=str(target_type) if target_type else None,
                target_id=str(target_id) if target_id else None,
                outcome=_normalize_outcome(outcome),
                summary=_redact_string(str(summary or normalized_action.replace(".", " ").capitalize())),
                request_json=serialize_payload(request_payload),
                response_json=serialize_payload(response_payload),
                job_id=str(job_id) if job_id else None,
                created_at=str(created_at or _utc_now()),
                legacy_key=normalized_legacy_key,
            )
        if inserted and mirror_legacy:
            self._append_legacy(event, normalized_legacy_key)
        return event, inserted

    def record_legacy_action(
        self,
        action: str,
        details: dict[str, Any] | None,
        *,
        actor: str | None,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> AuditEvent:
        payload = dict(details or {})
        server_id = str(payload.get("server_id") or "").strip() or None
        if server_id:
            target_type, target_id, scope_type = "server", server_id, "server"
        elif payload.get("username"):
            target_type, target_id, scope_type = "panel_user", str(payload["username"]), "global"
        elif payload.get("ip"):
            target_type, target_id, scope_type = "ip", str(payload["ip"]), "global"
        else:
            target_type, target_id, scope_type = None, None, "global"
        if ip_address:
            payload.setdefault("ip", ip_address)
        event, _inserted = self.record(
            actor=actor,
            action=action,
            correlation_id=correlation_id,
            scope_type=scope_type,
            server_id=server_id,
            target_type=target_type,
            target_id=target_id,
            outcome=str(payload.pop("outcome", "success")),
            summary=str(payload.pop("summary", "") or _normalize_action(action).replace(".", " ").capitalize()),
            request_payload=payload,
        )
        return event

    def list_events(
        self,
        *,
        server_id: str | None = None,
        outcome: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            self.list_events_page(
                server_id=server_id,
                outcome=outcome,
                actor=actor,
                action=action,
                cursor=cursor,
                limit=limit,
            )["events"],
        )

    def list_events_page(
        self,
        *,
        server_id: str | None = None,
        outcome: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        repository = AuditRepository(self.connection_factory())
        return repository.list_events(
            server_id=server_id,
            outcome=outcome,
            actor=actor,
            action=action,
            cursor=cursor,
            limit=limit,
        ).to_dict()

    def mirror_status(self) -> dict[str, Any]:
        with self._mirror_lock:
            return {
                "authoritative_store": "sqlite",
                "compatibility_mirror": "jsonl",
                "degraded": self._mirror_failures > 0,
                "failure_count": self._mirror_failures,
                "last_error": self._mirror_last_error,
                "last_failed_at": self._mirror_last_failed_at,
            }

    def _mark_mirror_failure(self, operation: str, error: OSError) -> None:
        with self._mirror_lock:
            self._mirror_failures += 1
            self._mirror_last_error = _redact_string(str(error))
            self._mirror_last_failed_at = _utc_now()
        LOGGER.warning(
            "Audit JSONL compatibility mirror %s failed; SQLite remains authoritative: %s",
            operation,
            error,
        )

    def clear(self) -> None:
        repository = AuditRepository(self.connection_factory())
        with repository.transaction():
            repository.clear()
        try:
            self.legacy_path.parent.mkdir(parents=True, exist_ok=True)
            self.legacy_path.write_text("", encoding="utf-8")
        except OSError as error:
            self._mark_mirror_failure("reset", error)

    def import_legacy(self) -> int:
        if not self.legacy_path.is_file():
            return 0
        imported = 0
        for raw_line in self.legacy_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            details_payload = record.get("details")
            details = details_payload if isinstance(details_payload, dict) else {}
            legacy_key = str(record.get("legacy_key") or f"jsonl:{hashlib.sha256(line.encode('utf-8')).hexdigest()}")
            server_id = str(details.get("server_id") or "").strip() or None
            target_type = (
                "server"
                if server_id
                else ("panel_user" if details.get("username") else ("ip" if details.get("ip") else None))
            )
            target_id = server_id or details.get("username") or details.get("ip")
            _event, inserted = self.record(
                actor=str(record.get("user") or record.get("actor") or "system"),
                action=str(record.get("event") or record.get("action") or "legacy.event"),
                correlation_id=str(record.get("correlation_id") or uuid.uuid4()),
                scope_type="server" if server_id else "global",
                server_id=server_id,
                target_type=target_type,
                target_id=str(target_id) if target_id else None,
                outcome=str(record.get("outcome") or "success"),
                summary=str(record.get("summary") or "Imported legacy panel action"),
                request_payload=details,
                created_at=str(record.get("created_at") or record.get("time") or _utc_now()),
                legacy_key=legacy_key,
                mirror_legacy=False,
            )
            imported += int(inserted)
        return imported

    def _append_legacy(self, event: AuditEvent, legacy_key: str) -> None:
        record = {
            "ts": datetime.now(timezone.utc).timestamp(),
            "time": event.created_at,
            "user": event.actor,
            "event": event.action,
            "details": _deserialize_payload(event.request_json) or {},
            "outcome": event.outcome,
            "summary": event.summary,
            "correlation_id": event.correlation_id,
            "legacy_key": legacy_key,
            "sqlite_audit_id": event.id,
        }
        try:
            self.legacy_path.parent.mkdir(parents=True, exist_ok=True)
            with self.legacy_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as error:
            self._mark_mirror_failure("append", error)
