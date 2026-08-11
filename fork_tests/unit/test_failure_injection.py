from __future__ import annotations

import pytest

from fork_tests.helpers.failures import FAILURE_BOUNDARIES, FailureBoundary, inject_failure


@pytest.mark.parametrize("boundary", FAILURE_BOUNDARIES)
def test_every_campaign_boundary_has_a_reusable_injector(boundary: FailureBoundary) -> None:
    injector = inject_failure(boundary, fail_on_call=2)

    injector()
    with pytest.raises(RuntimeError, match=boundary):
        injector()

    assert injector.calls == 2


def test_injector_can_raise_boundary_specific_exception() -> None:
    injector = inject_failure("atomic replace", error=OSError("replace unavailable"))

    with pytest.raises(OSError, match="replace unavailable"):
        injector()
