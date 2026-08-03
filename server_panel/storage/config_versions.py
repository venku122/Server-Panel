from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from .db import Repository, connect

RESOURCE_TYPES = frozenset({"dedicated_server_config", "startup_settings", "noblackbox_config"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_content(value: Any) -> Any:
    """Return deterministic JSON content without changing meaningful list order."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(value, dict):
        return {
            str(key): normalize_content(item) for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (list, tuple)):
        return [normalize_content(item) for item in value]
    return str(value)


def canonical_content(value: Any) -> tuple[Any, str, str]:
    normalized = normalize_content(value)
    serialized = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return normalized, serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConfigVersion:
    id: str
    resource_type: str
    resource_id: str
    server_id: str
    version_number: int
    content_json: str
    content_hash: str
    created_by: str
    created_at: str
    change_summary: str
    restored_from_version_id: str | None
    restart_required: bool

    @property
    def content(self) -> Any:
        return json.loads(self.content_json)

    def to_dict(self, *, include_content: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "server_id": self.server_id,
            "version_number": self.version_number,
            "content_hash": self.content_hash,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "change_summary": self.change_summary,
            "restored_from_version_id": self.restored_from_version_id,
            "restart_required": self.restart_required,
        }
        if include_content:
            payload["content"] = self.content
        return payload


class ConfigVersionRepository(Repository):
    @staticmethod
    def _version(row: sqlite3.Row) -> ConfigVersion:
        return ConfigVersion(
            id=str(row["id"]),
            resource_type=str(row["resource_type"]),
            resource_id=str(row["resource_id"]),
            server_id=str(row["server_id"]),
            version_number=int(row["version_number"]),
            content_json=str(row["content_json"]),
            content_hash=str(row["content_hash"]),
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
            change_summary=str(row["change_summary"]),
            restored_from_version_id=(
                str(row["restored_from_version_id"]) if row["restored_from_version_id"] is not None else None
            ),
            restart_required=bool(row["restart_required"]),
        )

    def get(self, version_id: str) -> ConfigVersion | None:
        row = self.connection.execute("SELECT * FROM config_versions WHERE id = ?", (version_id,)).fetchone()
        return self._version(row) if row is not None else None

    def latest(self, resource_type: str, resource_id: str) -> ConfigVersion | None:
        row = self.connection.execute(
            """
            SELECT * FROM config_versions
            WHERE resource_type = ? AND resource_id = ?
            ORDER BY version_number DESC LIMIT 1
            """,
            (resource_type, resource_id),
        ).fetchone()
        return self._version(row) if row is not None else None

    def previous(self, version: ConfigVersion) -> ConfigVersion | None:
        row = self.connection.execute(
            """
            SELECT * FROM config_versions
            WHERE resource_type = ? AND resource_id = ? AND version_number < ?
            ORDER BY version_number DESC LIMIT 1
            """,
            (version.resource_type, version.resource_id, version.version_number),
        ).fetchone()
        return self._version(row) if row is not None else None

    def list_versions(
        self,
        *,
        server_id: str,
        resource_type: str | None = None,
        limit: int = 200,
    ) -> list[ConfigVersion]:
        bounded = max(1, min(int(limit), 500))
        if resource_type:
            rows = self.connection.execute(
                """
                SELECT * FROM config_versions
                WHERE server_id = ? AND resource_type = ?
                ORDER BY created_at DESC, version_number DESC LIMIT ?
                """,
                (server_id, resource_type, bounded),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM config_versions
                WHERE server_id = ?
                ORDER BY created_at DESC, resource_type, version_number DESC LIMIT ?
                """,
                (server_id, bounded),
            ).fetchall()
        return [self._version(row) for row in rows]

    def insert(
        self,
        *,
        resource_type: str,
        resource_id: str,
        server_id: str,
        version_number: int,
        content_json: str,
        content_hash: str,
        created_by: str,
        change_summary: str,
        restored_from_version_id: str | None,
        restart_required: bool,
    ) -> ConfigVersion:
        version_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO config_versions (
                id, resource_type, resource_id, server_id, version_number, content_json,
                content_hash, created_by, created_at, change_summary,
                restored_from_version_id, restart_required
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                resource_type,
                resource_id,
                server_id,
                version_number,
                content_json,
                content_hash,
                created_by,
                _utc_now(),
                change_summary,
                restored_from_version_id,
                int(restart_required),
            ),
        )
        created = self.get(version_id)
        if created is None:
            raise RuntimeError("Configuration version was not readable after insert.")
        return created


def _diff_values(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                changes.append({"path": child, "kind": "added", "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "kind": "removed", "before": before[key]})
            else:
                changes.extend(_diff_values(before[key], after[key], child))
        return changes
    if isinstance(before, str) and isinstance(after, str) and ("\n" in before or "\n" in after):
        unified = list(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile="before",
                tofile="after",
                lineterm="",
            )
        )
        return [{"path": path, "kind": "changed", "before": before, "after": after, "unified": unified}]
    return [{"path": path, "kind": "changed", "before": before, "after": after}]


class ConfigVersionService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def _connection(self) -> sqlite3.Connection:
        return cast(sqlite3.Connection, connect(self.database_path))

    @staticmethod
    def _validate_resource(resource_type: str) -> None:
        if resource_type not in RESOURCE_TYPES:
            raise ValueError(f"Unsupported configuration resource: {resource_type}")

    def save(
        self,
        *,
        resource_type: str,
        resource_id: str,
        server_id: str,
        content: Any,
        created_by: str,
        change_summary: str,
        restored_from_version_id: str | None = None,
        restart_required: bool = False,
        force: bool = False,
    ) -> tuple[ConfigVersion, bool]:
        self._validate_resource(resource_type)
        _normalized, content_json, content_hash = canonical_content(content)
        connection = self._connection()
        try:
            repository = ConfigVersionRepository(connection)
            with repository.transaction():
                latest = repository.latest(resource_type, resource_id)
                if latest is not None and latest.content_hash == content_hash and not force:
                    return latest, False
                version = repository.insert(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    server_id=server_id,
                    version_number=1 if latest is None else latest.version_number + 1,
                    content_json=content_json,
                    content_hash=content_hash,
                    created_by=created_by,
                    change_summary=change_summary,
                    restored_from_version_id=restored_from_version_id,
                    restart_required=restart_required,
                )
                return version, True
        finally:
            connection.close()

    def get(self, version_id: str) -> ConfigVersion | None:
        connection = self._connection()
        try:
            return ConfigVersionRepository(connection).get(version_id)
        finally:
            connection.close()

    def list(self, *, server_id: str, resource_type: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if resource_type:
            self._validate_resource(resource_type)
        connection = self._connection()
        try:
            versions = ConfigVersionRepository(connection).list_versions(
                server_id=server_id,
                resource_type=resource_type,
                limit=limit,
            )
            return [version.to_dict(include_content=False) for version in versions]
        finally:
            connection.close()

    def diff(self, version_id: str, against_id: str | None = None) -> dict[str, Any]:
        connection = self._connection()
        try:
            repository = ConfigVersionRepository(connection)
            version = repository.get(version_id)
            if version is None:
                raise KeyError(version_id)
            against = repository.get(against_id) if against_id else repository.previous(version)
            if against is not None and (
                against.resource_type != version.resource_type or against.resource_id != version.resource_id
            ):
                raise ValueError("Compared versions must describe the same resource.")
            before = against.content if against is not None else None
            return {
                "version": version.to_dict(include_content=False),
                "against": against.to_dict(include_content=False) if against is not None else None,
                "changes": _diff_values(before, version.content),
            }
        finally:
            connection.close()
