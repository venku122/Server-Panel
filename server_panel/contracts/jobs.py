"""Contracts for durable job submission, parameters, and rendered results."""

from __future__ import annotations

from typing import Literal, TypeAlias, cast

from pydantic import Field, JsonValue, RootModel

from .base import ContractModel, JsonObject, ServerId

JobType: TypeAlias = Literal["server_update", "workshop_sync", "noblackbox_install", "moderation_install"]
JobStatus: TypeAlias = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]


class ServerJobParameters(ContractModel):
    server_id: ServerId


class WorkshopSyncParameters(ContractModel):
    server_id: ServerId | None = None
    local_only: bool = False


class ModerationInstallParameters(ServerJobParameters):
    dll_url: str = Field(min_length=1, max_length=2048)


def normalize_job_parameters(job_type: JobType, values: JsonObject) -> JsonObject:
    """Validate a known job's parameters and return persistence-safe JSON."""

    if job_type == "workshop_sync":
        return cast(
            JsonObject,
            WorkshopSyncParameters.model_validate(values).model_dump(mode="json"),
        )
    if job_type == "moderation_install":
        return cast(
            JsonObject,
            ModerationInstallParameters.model_validate(values).model_dump(mode="json"),
        )
    return cast(JsonObject, ServerJobParameters.model_validate(values).model_dump(mode="json"))


class ClusterJobEnqueue(ContractModel):
    job_type: Literal["server_update", "workshop_sync", "noblackbox_install"]
    server_id: ServerId
    parameters: JsonObject = Field(default_factory=dict)
    created_by: str = Field(default="cluster-coordinator", min_length=1, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=200)


class JobEventView(ContractModel):
    id: int
    job_id: str
    sequence: int
    level: Literal["debug", "info", "warning", "error"]
    message: str
    data: JsonValue | None = None
    created_at: str


class JobView(ContractModel):
    id: str
    job_type: JobType
    scope_type: Literal["global", "server"]
    server_id: str | None
    status: JobStatus
    parameters: JsonObject
    result: JsonValue | None
    progress_current: int = Field(ge=0)
    progress_total: int = Field(ge=0)
    created_by: str
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    error_summary: str | None
    cancel_requested: bool
    attempt: int = Field(ge=1)
    lease_owner: str | None
    lease_expires_at: str | None
    parent_job_id: str | None
    correlation_id: str
    replay_safe: bool
    events: list[JobEventView] | None = None


class JobResult(RootModel[JsonValue]):
    """A worker result that can be persisted and returned as JSON."""
