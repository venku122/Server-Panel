"""Shared strict contract behavior and browser-compatible validation errors."""

from __future__ import annotations

from typing import Annotated, TypeAlias, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    JsonValue,
    StringConstraints,
    ValidationError,
)

JsonObject: TypeAlias = dict[str, JsonValue]
NonEmptyText: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ServerId: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ContractModel(BaseModel):
    """Reject undeclared route data and normalize surrounding whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ValidationDiagnostic(ContractModel):
    """A safe, field-scoped diagnostic suitable for audit or API output."""

    field: str
    message: str
    code: str


class ValidationFailure(ContractModel):
    success: bool = False
    error: str
    diagnostics: list[ValidationDiagnostic]


def validation_failure(error: ValidationError) -> dict[str, JsonValue]:
    """Preserve the legacy success/error shape while adding structured detail."""

    diagnostics = [
        ValidationDiagnostic(
            field=".".join(str(part) for part in detail["loc"]),
            message=str(detail["msg"]),
            code=str(detail["type"]),
        )
        for detail in error.errors(include_url=False, include_context=False, include_input=False)
    ]
    first = (
        diagnostics[0]
        if diagnostics
        else ValidationDiagnostic(field="request", message="Invalid value", code="invalid")
    )
    field_prefix = f"{first.field}: " if first.field else ""
    return cast(
        JsonObject,
        ValidationFailure(
            error=f"Invalid request: {field_prefix}{first.message}",
            diagnostics=diagnostics,
        ).model_dump(mode="json"),
    )
