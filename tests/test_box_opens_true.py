"""Opening the box gives a real index, not an instruction to go and make one.

Most rules in this bundle end with "register it in your gates.yaml". If the box
does not contain that file, already true about itself, the instruction is prose —
governance audit round 23 of the reference implementation is where that gap was
first measured.

The second half matters as much: the check must not report N/A, or an absent
index would look like a satisfied one.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from bundle import do_install

if TYPE_CHECKING:
    import pathlib

    import pytest


def test_a_fresh_install_starts_with_a_registry_that_is_already_true(
    tmp_path: pathlib.Path, bundle_copy: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Opening the box gives a real index, not an instruction to go and make one.

    Most rules in this bundle end with "register it in your gates.yaml". If the
    box does not contain that file, already true about itself, the instruction is
    prose. So the shipped registry has to pass the shipped registry scanner on a
    project that has done nothing yet — **and not be skipped as N/A**, which would
    let an absent file look like a satisfied one.
    """
    project = tmp_path / "project"
    assert do_install(project, bundle_copy) == 0
    capsys.readouterr()
    assert (project / "gates.yaml").is_file(), "installed, but with no gate index"

    scanner = project / "tools" / "checks" / "scan_gates_registry.py"
    done = subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
        [sys.executable, str(scanner), str(project)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert done.returncode == 0, f"the starting registry fails its own check:\n{done.stdout}"
    assert "NA" not in done.stdout, (
        f"the starting registry was skipped, not checked:\n{done.stdout}"
    )
