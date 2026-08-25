"""Two of the scanners apply to this repository, so this repository runs them.

Audit round 23 of the reference implementation measured the gap between the rules
a project exports and the rules it keeps, and the answer was 2.7%. The cheapest
defence is to point every scanner that *can* apply here at here, from the day it
lands, rather than waiting for the doctor to orchestrate it in a later stage.

Only two apply today. The rest need a service layer, templates, a Dockerfile, or
an ADR directory — none of which this repository has. That is honest N/A, not a
pass, and the scanners say so themselves; `tests/test_checks_behaviour.py` is
where that distinction is proven.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from verifiable_gates.checks import scan_install_pinning, scan_workflow_pinning

ROOT = pathlib.Path(__file__).resolve().parent.parent

APPLICABLE = [
    pytest.param(scan_workflow_pinning, id="actions-sha-pinned"),
    pytest.param(scan_install_pinning, id="ci-tools-hash-pinned"),
]


@pytest.mark.parametrize("module", APPLICABLE)
def test_this_repository_passes_the_rules_it_ships(
    module: Any,  # noqa: ANN401 — the parameter is a module object
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = module.main(ROOT)
    output = capsys.readouterr().out
    assert result == 0, f"this repository breaks a rule it exports:\n{output}"
    assert not output.startswith("NA:"), (
        "this scanner found nothing to check here, so it is not dogfooding anything — "
        "either the repository lost the thing it checks, or this test is in the wrong list"
    )
