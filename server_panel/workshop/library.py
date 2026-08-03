"""Index the Workshop content already present on the panel host.

This module deliberately has no Steam Web API client. Public upstream provides a
local Workshop-cache sync, so local files are the authority and missing remote
metadata remains missing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from server_panel.contracts.workshop import WorkshopItemView, WorkshopResolveRequest

_IGNORED_JSON_NAMES = {
    "meta.json",
    "workshop.json",
    "catalog_1.json",
    "catalog_workshop.json",
}
_ID_PATTERN = re.compile(r"^[0-9]{1,20}$")
MAX_ITEM_DIRECTORIES = 2_000
MAX_FILES_PER_ITEM = 128
MAX_RECURSIVE_DEPTH = 4
MAX_METADATA_BYTES = 1_000_000
MAX_MISSION_BYTES = 10_000_000
MAX_SCAN_SECONDS = 5.0
CACHE_TTL_SECONDS = 30.0
MISSION_SIGNATURE_KEYS = frozenset(
    {
        "mission",
        "Mission",
        "MissionName",
        "MissionObjects",
        "objectives",
        "Objectives",
        "teams",
        "Teams",
        "units",
        "Units",
    }
)

_INDEX_CACHE: dict[tuple[str, ...], tuple[float, str, list["WorkshopItem"]]] = {}
_CACHE_LOCK = threading.Lock()


def invalidate_workshop_cache() -> None:
    with _CACHE_LOCK:
        _INDEX_CACHE.clear()


@dataclass(frozen=True)
class WorkshopReference:
    """A normalized Workshop item/collection reference."""

    item_id: str
    source: str


@dataclass
class WorkshopItem:
    """A locally discoverable Workshop item or panel mission."""

    item_id: str
    title: str
    author: str | None
    content_type: str
    source: str
    installed: bool
    local: bool
    updated_at: str | None
    metadata_available: bool
    mission_names: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)
    playlist_memberships: list[str] = field(default_factory=list)
    path: Path | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return the safe, browser-facing representation."""
        return cast(
            dict[str, Any],
            WorkshopItemView(
                id=self.item_id,
                title=self.title,
                author=self.author,
                content_type=self.content_type,
                source=self.source,
                installed=self.installed,
                local=self.local,
                updated_at=self.updated_at,
                metadata_available=self.metadata_available,
                mission_names=list(self.mission_names),
                child_ids=list(self.child_ids),
                playlist_memberships=list(self.playlist_memberships),
                can_add=bool(self.mission_names or self.child_ids),
            ).model_dump(mode="json"),
        )


def parse_workshop_reference(value: str) -> WorkshopReference:
    """Parse a numeric ID or a Steam Community item/collection URL."""
    candidate = str(value or "").strip()
    if _ID_PATTERN.fullmatch(candidate):
        return WorkshopReference(item_id=candidate, source="numeric_id")
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host not in {"steamcommunity.com", "www.steamcommunity.com"}:
        raise ValueError("Enter a numeric Workshop ID or a steamcommunity.com URL.")
    if parsed.path.rstrip("/").lower() != "/sharedfiles/filedetails":
        raise ValueError("That Steam URL is not a Workshop item or collection URL.")
    ids = parse_qs(parsed.query).get("id", [])
    if not ids or not _ID_PATTERN.fullmatch(ids[0]):
        raise ValueError("The Steam Workshop URL does not contain a valid numeric ID.")
    return WorkshopReference(item_id=ids[0], source="steam_url")


def _read_object(path: Path, *, max_bytes: int = MAX_METADATA_BYTES) -> dict[str, Any]:
    try:
        if path.stat().st_size > max_bytes:
            return {}
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_text(objects: Iterable[dict[str, Any]], keys: Iterable[str]) -> str | None:
    for payload in objects:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, (str, int)):
        text = str(value).strip()
        if _ID_PATTERN.fullmatch(text):
            found.append(text)
    elif isinstance(value, list):
        for entry in value:
            found.extend(_extract_ids(entry))
    elif isinstance(value, dict):
        for key in ("id", "publishedfileid", "published_file_id", "workshop_id"):
            found.extend(_extract_ids(value.get(key)))
    return found


def _child_ids(objects: Iterable[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for payload in objects:
        for key in (
            "children",
            "Children",
            "child_ids",
            "ChildIds",
            "publishedfileids",
            "collection_items",
        ):
            found.extend(_extract_ids(payload.get(key)))
    return list(dict.fromkeys(found))


def _is_mission_json(path: Path) -> bool:
    payload = _read_object(path, max_bytes=MAX_MISSION_BYTES)
    return bool(payload and MISSION_SIGNATURE_KEYS.intersection(payload))


def _mission_jsons(item_dir: Path, *, deadline: float | None = None) -> list[Path]:
    candidates: list[Path] = []
    inspected = 0
    try:
        for root, directories, filenames in os.walk(item_dir):
            relative_root = Path(root).relative_to(item_dir)
            if len(relative_root.parts) >= MAX_RECURSIVE_DEPTH:
                directories[:] = []
            directories[:] = sorted(directories)[:MAX_FILES_PER_ITEM]
            for filename in sorted(filenames):
                if deadline is not None and time.monotonic() >= deadline:
                    return sorted(candidates)
                inspected += 1
                if inspected > MAX_FILES_PER_ITEM:
                    return sorted(candidates)
                path = Path(root) / filename
                name = filename.lower()
                if not name.endswith(".json") or name in _IGNORED_JSON_NAMES or name.startswith("catalog_"):
                    continue
                if path.is_file() and path.stat().st_size <= MAX_MISSION_BYTES and _is_mission_json(path):
                    candidates.append(path)
            if inspected >= MAX_FILES_PER_ITEM:
                break
    except OSError:
        return []
    return sorted(candidates)


@dataclass(frozen=True)
class WorkshopCandidate:
    item_id: str
    mission_name: str
    source: Path
    metadata: Path | None
    destination: Path
    source_hash: str
    destination_hash: str | None

    @property
    def conflict(self) -> str:
        if self.destination_hash is None:
            return "new"
        return "identical" if self.source_hash == self.destination_hash else "different"


@dataclass
class WorkshopMutationPlan:
    item_id: str
    candidates: list[WorkshopCandidate]
    missing_child_ids: list[str]
    partial_acknowledged: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "mission_names": [candidate.mission_name for candidate in self.candidates],
            "missing_child_ids": list(self.missing_child_ids),
            "partial_acknowledgement_required": bool(self.missing_child_ids and not self.partial_acknowledged),
            "conflicts": [
                {
                    "mission_name": candidate.mission_name,
                    "state": candidate.conflict,
                    "replacement_required": candidate.conflict == "different",
                }
                for candidate in self.candidates
            ],
        }

    def replacements(self, conflict_policy: str) -> tuple[dict[Path, bytes], list[str]]:
        policy = str(conflict_policy or "error").strip().lower()
        if policy not in {"error", "replace", "skip", "rename"}:
            raise ValueError("conflict_policy must be error, replace, skip, or rename")
        if self.missing_child_ids and not self.partial_acknowledged:
            raise ValueError(
                "Collection is incomplete. Acknowledge the missing child IDs before applying locally available items."
            )
        replacements: dict[Path, bytes] = {}
        installed: list[str] = []
        for candidate in self.candidates:
            destination = candidate.destination
            mission_name = candidate.mission_name
            if candidate.conflict == "identical":
                installed.append(mission_name)
                continue
            if candidate.conflict == "different":
                if policy == "error":
                    raise ValueError(
                        f"Mission {mission_name} already exists with different content; choose replace, skip, or rename."
                    )
                if policy == "skip":
                    continue
                if policy == "rename":
                    mission_name = _safe_mission_name(f"{mission_name}-workshop-{candidate.item_id}")
                    destination = destination.parent.parent / mission_name / f"{mission_name}.json"
                    suffix = 2
                    while destination.exists() or destination in replacements:
                        mission_name = _safe_mission_name(
                            f"{candidate.mission_name}-workshop-{candidate.item_id}-{suffix}"
                        )
                        destination = destination.parent.parent / mission_name / f"{mission_name}.json"
                        suffix += 1
                elif policy == "replace":
                    backup = destination.with_name(f".{destination.name}.workshop-backup-{candidate.item_id}")
                    replacements[backup] = destination.read_bytes()
            content = candidate.source.read_bytes()
            if destination in replacements and replacements[destination] != content:
                raise ValueError(f"Multiple cached items provide different content for mission {mission_name}.")
            replacements[destination] = content
            if candidate.metadata is not None and candidate.metadata.is_file():
                replacements[destination.parent / "meta.json"] = candidate.metadata.read_bytes()
            installed.append(mission_name)
        return replacements, installed


def _modified_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _safe_mission_name(value: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", value.strip().strip("."))
    return re.sub(r"\s+", " ", name).strip()[:120]


class WorkshopLibrary:
    """Build and query a bounded, local-only Workshop library."""

    def __init__(
        self,
        workshop_roots: Iterable[Path],
        missions_root: Path,
        playlist_memberships: dict[str, Iterable[str]] | None = None,
    ) -> None:
        self.workshop_roots = [Path(path) for path in workshop_roots]
        self.missions_root = Path(missions_root)
        self.playlist_memberships = {
            str(name): {str(mission) for mission in missions} for name, missions in (playlist_memberships or {}).items()
        }
        self._last_refresh_at: str | None = None

    @property
    def last_refresh_at(self) -> str | None:
        return self._last_refresh_at

    def scan(self, *, force: bool = False) -> list[WorkshopItem]:
        """Return cached items and panel missions, de-duplicated by identity."""
        key = tuple(str(path.resolve()) for path in [*self.workshop_roots, self.missions_root])
        now = time.monotonic()
        if not force:
            with _CACHE_LOCK:
                cached = _INDEX_CACHE.get(key)
            if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
                self._last_refresh_at = cached[1]
                return self._with_memberships(deepcopy(cached[2]))

        started = time.monotonic()
        deadline = started + MAX_SCAN_SECONDS
        items: dict[str, WorkshopItem] = {}
        for root in self.workshop_roots:
            if time.monotonic() >= deadline:
                break
            try:
                directories = sorted(path for path in root.iterdir() if path.is_dir())[:MAX_ITEM_DIRECTORIES]
            except OSError:
                continue
            for item_dir in directories:
                if time.monotonic() >= deadline:
                    break
                if not _ID_PATTERN.fullmatch(item_dir.name):
                    continue
                items[item_dir.name] = self._cached_item(item_dir, deadline=deadline)

        try:
            mission_paths = sorted(self.missions_root.iterdir())
        except OSError:
            mission_paths = []
        for path in mission_paths[:MAX_ITEM_DIRECTORIES]:
            if time.monotonic() >= deadline:
                break
            mission_name = path.stem if path.is_file() else path.name
            if not mission_name or not self._panel_mission_exists(path, mission_name):
                continue
            item_id = f"mission:{mission_name}"
            if any(mission_name in item.mission_names for item in items.values()):
                continue
            meta_path = path / "meta.json" if path.is_dir() else path.with_name("meta.json")
            metadata = _read_object(meta_path)
            title = _first_text([metadata], ("title", "Title", "name", "Name")) or mission_name
            item = WorkshopItem(
                item_id=item_id,
                title=title,
                author=_first_text([metadata], ("author", "Author", "creator", "Creator")),
                content_type="mission",
                source="panel_missions",
                installed=True,
                local=True,
                updated_at=_modified_iso(path),
                metadata_available=bool(metadata),
                mission_names=[mission_name],
                path=path,
            )
            items[item_id] = item
        output = sorted(items.values(), key=lambda item: (item.title.casefold(), item.item_id))
        refreshed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _CACHE_LOCK:
            _INDEX_CACHE[key] = (started, refreshed_at, deepcopy(output))
        self._last_refresh_at = refreshed_at
        return self._with_memberships(output)

    def refresh(self) -> list[WorkshopItem]:
        return self.scan(force=True)

    def search(self, query: str = "", filter_name: str = "all") -> list[WorkshopItem]:
        """Search by title or ID and filter the local index."""
        needle = str(query or "").strip().casefold()
        filter_key = str(filter_name or "all").strip().lower()
        output: list[WorkshopItem] = []
        for item in self.scan():
            if needle and needle not in item.title.casefold() and needle not in item.item_id.casefold():
                continue
            if filter_key == "installed" and not item.installed:
                continue
            if filter_key == "local" and not item.local:
                continue
            if filter_key == "playlist" and not item.playlist_memberships:
                continue
            output.append(item)
        return output

    def resolve(self, request: WorkshopResolveRequest | str) -> dict[str, Any]:
        """Resolve input against local files and expand locally known collections."""
        value = request.reference if isinstance(request, WorkshopResolveRequest) else request
        reference = parse_workshop_reference(value)
        by_id = {item.item_id: item for item in self.scan()}
        item = by_id.get(reference.item_id)
        if item is None:
            return {
                "reference": {"id": reference.item_id, "source": reference.source},
                "resolved": False,
                "remote_lookup_available": False,
                "message": (
                    "This ID is not present in the local Workshop cache. Subscribe or download it "
                    "in Steam, then queue a library refresh."
                ),
            }
        children = [by_id[child].to_dict() for child in item.child_ids if child in by_id]
        missing = [child for child in item.child_ids if child not in by_id]
        return {
            "reference": {"id": reference.item_id, "source": reference.source},
            "resolved": True,
            "item": item.to_dict(),
            "collection_items": children,
            "missing_child_ids": missing,
            "remote_lookup_available": False,
            "message": (
                "Collection expansion is limited to child items already present in the local cache."
                if item.content_type == "collection"
                else "Local metadata resolved."
            ),
        }

    def preview_item(self, item_id: str, *, partial_acknowledged: bool = False) -> WorkshopMutationPlan:
        """Describe every prospective copy without changing the filesystem."""
        by_id = {item.item_id: item for item in self.scan()}
        item = by_id.get(str(item_id))
        if item is None:
            raise KeyError("Workshop item is not present in the local cache.")
        missing_child_ids: list[str] = []
        selected = [item]
        if item.content_type == "collection":
            selected = [by_id[child] for child in item.child_ids if child in by_id]
            missing_child_ids = [child for child in item.child_ids if child not in by_id]
            if not selected:
                raise ValueError("No locally cached collection items can be added.")
        candidates: list[WorkshopCandidate] = []
        for selected_item in selected:
            if selected_item.source == "panel_missions":
                for name in selected_item.mission_names:
                    source = self._panel_mission_json(selected_item.path, name)
                    if source is not None:
                        candidates.append(self._candidate(selected_item.item_id, name, source, None))
                continue
            if selected_item.path is None:
                continue
            metadata = selected_item.path / "meta.json"
            for mission_json in _mission_jsons(selected_item.path):
                name = _safe_mission_name(mission_json.stem)
                if not name:
                    continue
                candidates.append(
                    self._candidate(selected_item.item_id, name, mission_json, metadata if metadata.is_file() else None)
                )
        if not candidates:
            raise ValueError("The selected item contains no locally available missions.")
        return WorkshopMutationPlan(
            item_id=item.item_id,
            candidates=candidates,
            missing_child_ids=missing_child_ids,
            partial_acknowledged=partial_acknowledged,
        )

    def _candidate(self, item_id: str, name: str, source: Path, metadata: Path | None) -> WorkshopCandidate:
        destination = self.missions_root / name / f"{name}.json"
        return WorkshopCandidate(
            item_id=item_id,
            mission_name=name,
            source=source,
            metadata=metadata,
            destination=destination,
            source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
            destination_hash=(hashlib.sha256(destination.read_bytes()).hexdigest() if destination.is_file() else None),
        )

    @staticmethod
    def _panel_mission_json(path: Path | None, name: str) -> Path | None:
        if path is None:
            return None
        if path.is_file():
            return path
        preferred = path / f"{name}.json"
        if preferred.is_file():
            return preferred
        return next((candidate for candidate in sorted(path.glob("*.json")) if candidate.name != "meta.json"), None)

    def _cached_item(self, item_dir: Path, *, deadline: float | None = None) -> WorkshopItem:
        metadata_paths = [item_dir / "meta.json", item_dir / "workshop.json"]
        objects = [_read_object(path) for path in metadata_paths if path.is_file()]
        missions = [_safe_mission_name(path.stem) for path in _mission_jsons(item_dir, deadline=deadline)]
        missions = [name for name in missions if name]
        children = _child_ids(objects)
        has_catalog = any(item_dir.glob("catalog_*.json"))
        content_type = (
            "collection" if children else ("mission" if missions else ("catalog" if has_catalog else "unknown"))
        )
        title = _first_text(objects, ("title", "Title", "name", "Name", "display_name"))
        item = WorkshopItem(
            item_id=item_dir.name,
            title=title or (missions[0] if missions else f"Workshop item {item_dir.name}"),
            author=_first_text(objects, ("author", "Author", "creator", "Creator", "owner")),
            content_type=content_type,
            source="steam_cache",
            installed=True,
            local=True,
            updated_at=_modified_iso(item_dir),
            metadata_available=any(bool(metadata) for metadata in objects),
            mission_names=list(dict.fromkeys(missions)),
            child_ids=children,
            path=item_dir,
        )
        return item

    @staticmethod
    def _panel_mission_exists(path: Path, mission_name: str) -> bool:
        if path.is_file():
            return path.suffix.lower() == ".json" and path.name.lower() != "meta.json"
        return (path / f"{mission_name}.json").is_file() or any(
            candidate.name.lower() != "meta.json" for candidate in path.glob("*.json")
        )

    def _memberships(self, mission_names: Iterable[str]) -> list[str]:
        names = set(mission_names)
        return sorted(
            playlist for playlist, members in self.playlist_memberships.items() if names.intersection(members)
        )

    def _with_memberships(self, items: list[WorkshopItem]) -> list[WorkshopItem]:
        for item in items:
            item.playlist_memberships = self._memberships(item.mission_names)
        return items
