"""Index the Workshop content already present on the panel host.

This module deliberately has no Steam Web API client. Public upstream provides a
local Workshop-cache sync, so local files are the authority and missing remote
metadata remains missing.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

_IGNORED_JSON_NAMES = {
    "meta.json",
    "workshop.json",
    "catalog_1.json",
    "catalog_workshop.json",
}
_ID_PATTERN = re.compile(r"^[0-9]{1,20}$")


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
        return {
            "id": self.item_id,
            "title": self.title,
            "author": self.author,
            "content_type": self.content_type,
            "source": self.source,
            "installed": self.installed,
            "local": self.local,
            "updated_at": self.updated_at,
            "metadata_available": self.metadata_available,
            "mission_names": list(self.mission_names),
            "child_ids": list(self.child_ids),
            "playlist_memberships": list(self.playlist_memberships),
            "can_add": bool(self.mission_names or self.child_ids),
        }


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


def _read_object(path: Path) -> dict[str, Any]:
    try:
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


def _mission_jsons(item_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    try:
        for path in item_dir.rglob("*.json"):
            name = path.name.lower()
            if not path.is_file() or name in _IGNORED_JSON_NAMES or name.startswith("catalog_"):
                continue
            candidates.append(path)
    except OSError:
        return []
    return sorted(candidates)


def _modified_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
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

    def scan(self) -> list[WorkshopItem]:
        """Return cached items and panel missions, de-duplicated by identity."""
        items: dict[str, WorkshopItem] = {}
        for root in self.workshop_roots:
            try:
                directories = sorted(path for path in root.iterdir() if path.is_dir())
            except OSError:
                continue
            for item_dir in directories:
                if not _ID_PATTERN.fullmatch(item_dir.name):
                    continue
                items[item_dir.name] = self._cached_item(item_dir)

        try:
            mission_paths = sorted(self.missions_root.iterdir())
        except OSError:
            mission_paths = []
        for path in mission_paths:
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
            item.playlist_memberships = self._memberships(item.mission_names)
            items[item_id] = item
        return sorted(items.values(), key=lambda item: (item.title.casefold(), item.item_id))

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

    def resolve(self, value: str) -> dict[str, Any]:
        """Resolve input against local files and expand locally known collections."""
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

    def copy_item_to_missions(self, item_id: str) -> list[str]:
        """Copy a cached item (or local collection) into panel missions."""
        by_id = {item.item_id: item for item in self.scan()}
        item = by_id.get(str(item_id))
        if item is None:
            raise KeyError("Workshop item is not present in the local cache.")
        selected = [item]
        if item.content_type == "collection":
            selected = [by_id[child] for child in item.child_ids if child in by_id]
            if not selected:
                raise ValueError("No locally cached collection items can be added.")
        copied: list[str] = []
        self.missions_root.mkdir(parents=True, exist_ok=True)
        for selected_item in selected:
            if selected_item.source == "panel_missions":
                copied.extend(selected_item.mission_names)
                continue
            if selected_item.path is None:
                continue
            metadata = selected_item.path / "meta.json"
            for mission_json in _mission_jsons(selected_item.path):
                name = _safe_mission_name(mission_json.stem)
                if not name:
                    continue
                destination = self.missions_root / name
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copy2(mission_json, destination / f"{name}.json")
                if metadata.is_file():
                    shutil.copy2(metadata, destination / "meta.json")
                copied.append(name)
        return list(dict.fromkeys(copied))

    def _cached_item(self, item_dir: Path) -> WorkshopItem:
        metadata_paths = [item_dir / "meta.json", item_dir / "workshop.json"]
        objects = [_read_object(path) for path in metadata_paths if path.is_file()]
        missions = [_safe_mission_name(path.stem) for path in _mission_jsons(item_dir)]
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
        item.playlist_memberships = self._memberships(item.mission_names)
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
