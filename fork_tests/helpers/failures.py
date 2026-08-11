from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FailureBoundary = Literal[
    "sqlite insert/commit",
    "filesystem write",
    "atomic replace",
    "rollback write",
    "audit append",
    "job lease renewal",
    "job finish",
    "remote signed request",
    "workshop copy",
    "config version save",
]

FAILURE_BOUNDARIES: tuple[FailureBoundary, ...] = (
    "sqlite insert/commit",
    "filesystem write",
    "atomic replace",
    "rollback write",
    "audit append",
    "job lease renewal",
    "job finish",
    "remote signed request",
    "workshop copy",
    "config version save",
)


@dataclass
class FailureInjector:
    """Fail a named boundary on its selected invocation while recording calls."""

    boundary: FailureBoundary
    fail_on_call: int = 1
    error: Exception | None = None
    calls: int = 0

    def __call__(self, *_args: object, **_kwargs: object) -> None:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise self.error or RuntimeError(f"injected {self.boundary} failure")


def inject_failure(
    boundary: FailureBoundary,
    *,
    fail_on_call: int = 1,
    error: Exception | None = None,
) -> FailureInjector:
    """Build a deterministic, counted injector for a campaign mutation boundary."""
    return FailureInjector(boundary=boundary, fail_on_call=fail_on_call, error=error)
