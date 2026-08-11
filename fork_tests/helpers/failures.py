from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FailureInjector:
    """Fail a named boundary on its selected invocation while recording calls."""

    boundary: str
    fail_on_call: int = 1
    calls: int = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError(f"injected {self.boundary} failure")


def inject_failure(boundary: str, *, fail_on_call: int = 1) -> FailureInjector:
    return FailureInjector(boundary=boundary, fail_on_call=fail_on_call)
