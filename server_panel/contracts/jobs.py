"""Contracts for durable job submission, parameters, and rendered results."""

from __future__ import annotations

from typing import Literal, TypeAlias, cast

from pydantic import ConfigDict, Field, JsonValue, RootModel

from server_panel.limits import JOB_ID_MAX_LENGTH, JOB_PARAMETER_TEXT_MAX_LENGTH

from .base import ContractModel, JsonObject, ServerId

JobType: TypeAlias = Literal["server_update", "workshop_sync", "noblackbox_install", "moderation_install"]
JobStatus: TypeAlias = Literal[
    "queued",
    "running",
    "cancel_requested",
    "succeeded",
    "failed",
    "cancelled",
    "interrupted",
]
KNOWN_JOB_TYPES = frozenset({"server_update", "workshop_sync", "noblackbox_install", "moderation_install"})


class ServerJobParameters(ContractModel):
    server_id: ServerId


class WorkshopSyncParameters(ContractModel):
    server_id: ServerId | None = None
    local_only: bool = False
    all_servers: bool = False


class ModerationInstallParameters(ServerJobParameters):
    dll_url: str = Field(min_length=1, max_length=JOB_PARAMETER_TEXT_MAX_LENGTH)


JOB_PARAMETER_MODELS = {
    "server_update": ServerJobParameters,
    "workshop_sync": WorkshopSyncParameters,
    "noblackbox_install": ServerJobParameters,
    "moderation_install": ModerationInstallParameters,
}


def normalize_job_parameters(job_type: str, values: JsonObject) -> JsonObject:
    """Validate a known job's parameters and reject unknown runtime dispatch."""
    model = JOB_PARAMETER_MODELS.get(job_type)
    if model is None:
        raise ValueError(f"Unsupported job type: {job_type}")
    return cast(JsonObject, model.model_validate(values).model_dump(mode="json"))


class ClusterJobEnqueue(ContractModel):
    # Additive fields from newer peers are ignored; supported job types remain explicit.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    job_type: JobType
    server_id: ServerId
    parameters: JsonObject = Field(default_factory=dict)
    created_by: str = Field(default="cluster-coordinator", min_length=1, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=200)
    contract_version: int = Field(default=1, ge=1)


class JobEventView(ContractModel):
    id: int
    job_id: str = Field(min_length=1, max_length=JOB_ID_MAX_LENGTH)
    sequence: int
    level: Literal["debug", "info", "warning", "error"]
    message: str
    data: JsonValue | None = None
    created_at: str


class JobView(ContractModel):
    """Normal browser model; worker lease ownership is diagnostics-only."""

    id: str = Field(min_length=1, max_length=JOB_ID_MAX_LENGTH)
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
    parent_job_id: str | None
    correlation_id: str
    replay_safe: bool
    last_completed_step: str | None = None
    events: list[JobEventView] | None = None
    invalid_record: bool = False
    validation_warning: str | None = None


class JobResult(RootModel[JsonValue]):
    """A worker result that can be persisted and returned as JSON."""
