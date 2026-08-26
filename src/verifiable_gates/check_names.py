"""The names a repository's checks will actually appear under.

Branch protection is a list of **check names**, and a check name is not a job id.
A job with a `name:` uses that instead; a job with a matrix produces one check per
row, each named by substituting the row's values into the template. Two failures
follow from getting this wrong, and they look opposite:

- **A required name no job can produce** leaves every pull request waiting for a
  check that will never arrive. Nothing is red; the pull request simply never
  becomes mergeable.
- **A job nobody requires** runs, goes red, and merges anyway.

Both are invisible from inside the repository unless something computes the names
the platform is going to use. The reference implementation had one report saying
`dialect` failed ten times and, in the same breath, that `dialects` had never gone
red — the first is the check name, the second is the job id, and no reader had
ever put them together.

Three questions this answers, and they are genuinely different:

- **which checks a pull request will show** — only the workflows triggered by one
- **every check the repository can produce at all** — including scheduled and
  release-only ones, which is the set a "not required, and here is why" register
  has to be checked against
- **how many there are** — the number documents tend to advertise

**Named for what it computes, not for what it reads.** `checks` is taken by the
directory of standalone scanners this bundle ships, and a module shadowing a
package is a bug that surfaces as an `AttributeError` far from its cause.

Role: reader — it reports. Nothing here decides pass or fail, and nothing here
reaches the network: the answer is computed from the workflow files on disk,
which is what makes it checkable at all.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from verifiable_gates import workflows as gha

if TYPE_CHECKING:
    from verifiable_gates.workflows import Workflow

__all__ = ["MATRIX_REF", "all_checks", "check_names", "pull_request_checks", "total_checks"]

MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([a-zA-Z0-9_.]+)\s*\}\}")


def _resolve(name: str, combo: object) -> str:
    """Substitute `${{ matrix.x.y }}` in a job's name with one row's values."""

    def value(found: re.Match[str]) -> str:
        reference = found.group(1)
        node = combo
        for part in reference.split(".")[1:] if "." in reference else []:
            node = node[part] if isinstance(node, dict) else node
        if isinstance(node, dict):
            node = node.get(reference.split(".")[-1], node)
        return str(node)

    return MATRIX_REF.sub(value, name)


def _names_of(key: str, job: dict[str, Any]) -> set[str]:
    """Every check name one job declaration produces.

    A matrix row whose values do not appear in the name still produces a distinct
    check — the platform appends the row itself. Collapsing those into one name
    would under-count exactly the jobs that run most often.
    """
    base = job.get("name") or key
    strategy = job.get("strategy") or {}
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not matrix:
        return {base}
    return {
        _resolve(base, combo) if _resolve(base, combo) != base else f"{base} ({combo})"
        for combos in matrix.values()
        for combo in combos
    }


def check_names(workflow: Workflow) -> set[str]:
    """Every check name one workflow produces."""
    return {name for key, job in gha.jobs(workflow).items() for name in _names_of(key, job)}


def pull_request_checks(workflows: dict[str, Workflow]) -> set[str]:
    """The names that will appear on a pull request.

    This is the set branch protection has to cover. A workflow that never runs on
    a pull request must **not** be in it: requiring such a name is the failure
    where nothing is red and the pull request never merges.
    """
    return {
        name
        for workflow in workflows.values()
        if gha.runs_on(workflow, "pull_request")
        for name in check_names(workflow)
    }


def all_checks(workflows: dict[str, Workflow]) -> set[str]:
    """Every check name the repository can produce, on any trigger at all.

    Wider than `pull_request_checks` on purpose. A register saying "this check is
    not required, and here is why" has to be held against *this* set — held
    against the pull-request set instead, its entries can never appear in it, so
    the register is never consulted and quietly becomes a text file.
    """
    return {name for workflow in workflows.values() for name in check_names(workflow)}


def total_checks(workflows: dict[str, Workflow]) -> int:
    """How many checks the repository can produce — the number documents quote.

    Counted rather than measured by the size of `all_checks`, because two jobs in
    different workflows may share a name: as a count of what runs they are two,
    as a set of names they are one.
    """
    total = 0
    for workflow in workflows.values():
        for job in gha.jobs(workflow).values():
            strategy = job.get("strategy") or {}
            matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
            total += len(next(iter(matrix.values()))) if matrix else 1
    return total
