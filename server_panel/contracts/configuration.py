"""Contracts for the public-main configuration editors."""

from __future__ import annotations

from pydantic import Field, JsonValue, RootModel, model_validator

from .base import ContractModel, ServerId
from server_panel.limits import FPS_MAX, FPS_MIN, MAX_PLAYERS_MAX, MAX_PLAYERS_MIN, PORT_MAX, PORT_MIN


class DedicatedConfig(RootModel[dict[str, JsonValue]]):
    """A JSON object, without imposing template or provider-specific fields."""


class DedicatedConfigUpdate(ContractModel):
    server_id: ServerId | None = None
    config: DedicatedConfig
    created_by: str | None = Field(default=None, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=200)

    def config_view(self) -> dict[str, JsonValue]:
        return dict(self.config.root)


class StartupSettings(ContractModel):
    fps: int | None = Field(default=None, ge=FPS_MIN, le=FPS_MAX)
    max_players: int | None = Field(default=None, ge=MAX_PLAYERS_MIN, le=MAX_PLAYERS_MAX)
    remote_commands_port: int | None = Field(default=None, ge=PORT_MIN, le=PORT_MAX)
    old_port: int | None = Field(default=None, ge=PORT_MIN, le=PORT_MAX)

    @model_validator(mode="after")
    def require_a_setting(self) -> StartupSettings:
        if all(value is None for value in (self.fps, self.max_players, self.remote_commands_port)):
            raise ValueError("at least one startup setting is required")
        return self


class StartupSettingsUpdate(ContractModel):
    server_id: ServerId | None = None
    settings: StartupSettings
    created_by: str | None = Field(default=None, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=200)
