"""Contracts for the local-only Workshop library and current rotation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import ContractModel, NonEmptyText


class WorkshopSearch(ContractModel):
    q: str = Field(default="", max_length=200)
    filter: Literal["all", "installed", "local", "playlist"] = "all"


class WorkshopResolveRequest(ContractModel):
    reference: NonEmptyText = Field(max_length=512)


class WorkshopRotationUpdate(ContractModel):
    item_id: NonEmptyText = Field(max_length=200)
    placement: Literal["first_available", "slot1", "slot2"] = "first_available"
    conflict_policy: Literal["error", "replace", "skip", "rename"] = "error"
    acknowledge_partial_collection: bool = False


class WorkshopItemView(ContractModel):
    id: str
    title: str
    author: str | None
    content_type: str
    source: str
    installed: bool
    local: bool
    updated_at: str | None
    metadata_available: bool
    mission_names: list[str]
    child_ids: list[str]
    playlist_memberships: list[str]
    can_add: bool
