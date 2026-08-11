from __future__ import annotations

import json
from pathlib import Path

import pytest

from server_panel.workshop import WorkshopLibrary, invalidate_workshop_cache, parse_workshop_reference


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def local_library(tmp_path: Path) -> tuple[WorkshopLibrary, Path, Path]:
    invalidate_workshop_cache()
    cache = tmp_path / "steamapps" / "workshop" / "content" / "2168680"
    missions = tmp_path / "missions"
    _write_json(cache / "111" / "meta.json", {"title": "Falcon Ridge", "author": "Aviator"})
    _write_json(cache / "111" / "FalconRidge.json", {"mission": True})
    _write_json(cache / "222" / "SilentValley.json", {"MissionObjects": []})
    _write_json(cache / "333" / "workshop.json", {"title": "Local Collection", "children": ["111", "222"]})
    _write_json(missions / "PanelOnly" / "PanelOnly.json", {"mission": True})
    library = WorkshopLibrary([cache], missions, {"Current rotation": ["FalconRidge"]})
    return library, cache, missions


def test_parses_numeric_and_full_workshop_urls() -> None:
    numeric = parse_workshop_reference("111")
    url = parse_workshop_reference("https://steamcommunity.com/sharedfiles/filedetails/?id=333")

    assert (numeric.item_id, numeric.source) == ("111", "numeric_id")
    assert (url.item_id, url.source) == ("333", "steam_url")
    with pytest.raises(ValueError, match="numeric Workshop ID"):
        parse_workshop_reference("https://example.com/sharedfiles/filedetails/?id=111")


def test_indexes_metadata_absence_search_and_playlist_membership(
    local_library: tuple[WorkshopLibrary, Path, Path],
) -> None:
    library, _cache, _missions = local_library
    items = {item.item_id: item for item in library.scan()}

    assert items["111"].title == "Falcon Ridge"
    assert items["111"].playlist_memberships == ["Current rotation"]
    assert items["222"].metadata_available is False
    assert items["333"].content_type == "collection"
    assert items["mission:PanelOnly"].source == "panel_missions"
    assert [item.item_id for item in library.search("falcon")] == ["111"]


def test_rejects_arbitrary_json_and_bounds_each_item_scan(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _write_json(cache / "111" / "not-a-mission.json", {"settings": {"enabled": True}})
    for index in range(140):
        _write_json(cache / "111" / f"mission-{index:03}.json", {"mission": True})

    item = WorkshopLibrary([cache], tmp_path / "missions").scan(force=True)[0]

    assert "not-a-mission" not in item.mission_names
    assert len(item.mission_names) <= 128


def test_cached_scan_avoids_rescanning_filesystem(local_library, monkeypatch: pytest.MonkeyPatch) -> None:
    library, _cache, _missions = local_library
    first = library.scan(force=True)
    monkeypatch.setattr(library, "_cached_item", lambda *_args, **_kwargs: pytest.fail("unexpected rescan"))

    second = library.scan()

    assert [item.item_id for item in second] == [item.item_id for item in first]
    assert library.last_refresh_at


def test_preview_is_non_mutating_and_conflicts_are_explicit(local_library) -> None:
    library, _cache, missions = local_library
    destination = missions / "FalconRidge" / "FalconRidge.json"
    _write_json(destination, {"mission": "existing"})
    before = destination.read_bytes()

    plan = library.preview_item("111")

    assert plan.to_dict()["conflicts"][0]["state"] == "different"
    with pytest.raises(ValueError, match="choose replace"):
        plan.replacements("error")
    assert destination.read_bytes() == before


def test_identical_copy_is_idempotent_and_replace_retains_backup(local_library) -> None:
    library, cache, missions = local_library
    destination = missions / "FalconRidge" / "FalconRidge.json"
    destination.parent.mkdir(parents=True)
    destination.write_bytes((cache / "111" / "FalconRidge.json").read_bytes())

    identical = library.preview_item("111")
    replacements, installed = identical.replacements("error")

    assert replacements == {}
    assert installed == ["FalconRidge"]
    destination.write_text('{"mission": "old"}', encoding="utf-8")
    replacement = library.preview_item("111")
    replacements, _ = replacement.replacements("replace")
    backup = destination.with_name(".FalconRidge.json.workshop-backup-111")
    assert replacements[backup] == b'{"mission": "old"}'


def test_incomplete_collection_requires_explicit_acknowledgement(local_library) -> None:
    library, cache, _missions = local_library
    _write_json(cache / "333" / "workshop.json", {"title": "Collection", "children": ["111", "999"]})
    library.refresh()

    blocked = library.preview_item("333")
    with pytest.raises(ValueError, match="Acknowledge"):
        blocked.replacements("error")
    allowed = library.preview_item("333", partial_acknowledged=True)

    assert allowed.missing_child_ids == ["999"]
    assert allowed.replacements("error")[1] == ["FalconRidge"]
