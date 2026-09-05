"""Every `proved_by.ref` in the registry, resolved against the platform — read-only.

`registry.py` holds a ref to its *shape* (`pr/N`, `run/N`, `commit/<hex>`, an
`owner/repo#` prefix when the red was seen elsewhere), and the suite is held to
no-network-at-test-time, so a ref that names nothing — `pr/999999999` — passed
every test (filed three times by outside audits; RC-12). This module is the other
half: it asks GitHub whether each distinct ref still points at something, and for a
`run/N` whether its log can still be read — GitHub keeps run logs for a retention
window and answers **410 Gone** after it, while the run's record stays. It runs from
`posture.yml`, weekly and on every push to `main`, where the platform is already
being asked; never from the test job.

Three answers, as every decider here:

- exit 0 — every distinct ref resolves and every run's log is readable;
- exit 1 — a ref answers 404, has a shape this module cannot ask about, or is a run
  whose log is gone: each is printed with the gates that cite it and what to do
  (rewrite the ref to the `pr/N` that carries the same proof, or re-decide the row);
- exit 2 — the platform could not be asked (no `gh`, no token, a timeout): "could
  not look" is not a pass.

Role: decider — it answers with an exit code, and a posture step blocks on it.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys

import yaml

from verifiable_gates import gh

__all__ = ["Ref", "collect", "main", "parse", "resolve", "status_of"]

DEFAULT_REPO = "sayam/verifiable-gates"


class Ref:
    """One distinct ref, split into what the API needs."""

    __slots__ = ("kind", "number", "repo", "text")

    def __init__(self, text: str, default_repo: str) -> None:
        self.text = text
        target, _, rest = text.rpartition("#")
        self.repo = target or default_repo
        self.kind, _, self.number = rest.partition("/")

    @property
    def path(self) -> str | None:
        """The API path that says whether the thing exists, or None for a shape we cannot ask."""
        if self.kind == "pr":
            return f"repos/{self.repo}/pulls/{self.number}"
        if self.kind == "run":
            return f"repos/{self.repo}/actions/runs/{self.number}"
        if self.kind == "commit":
            return f"repos/{self.repo}/commits/{self.number}"
        return None


def parse(text: str, default_repo: str = DEFAULT_REPO) -> Ref:
    return Ref(text, default_repo)


def collect(registry: pathlib.Path) -> dict[str, list[str]]:
    """Every distinct ref in the registry, with the ids of the gates that cite it."""
    loaded = yaml.safe_load(registry.read_text(encoding="utf-8"))
    cited: dict[str, list[str]] = collections.defaultdict(list)
    for gate in loaded["gates"]:
        for row in gate.get("proved_by") or []:
            cited[str(row["ref"])].append(str(gate["id"]))
    return dict(cited)


def status_of(problem: BaseException) -> str:
    """The HTTP status inside `gh`'s message, when there is one."""
    text = str(problem)
    for code in ("404", "410", "403", "401"):
        if f"HTTP {code}" in text or f'"status":"{code}"' in text or f"({code})" in text:
            return code
    return "error"


def _exists(ref: Ref, path: str) -> tuple[object, str | None]:
    """The platform's answer for the ref, or the sentence for a 404."""
    try:
        return gh.api(path), None
    except PermissionError as refused:
        if status_of(refused) == "404":
            return None, f"{ref.text}: the platform answers 404 — nothing at {path}"
        raise


def _log_readable(ref: Ref, path: str) -> str | None:
    """None when the run's log can still be fetched; otherwise the sentence saying why not."""
    try:
        gh.run(["api", f"{path}/logs", "--silent"])
    except PermissionError as refused:
        status = status_of(refused)
        if status == "410":
            return (
                f"{ref.text}: the run exists but its log is gone (410 — past the retention"
                " window); rewrite the ref to the pr/N that carries the same proof, or"
                " re-decide the row"
            )
        if status == "404":
            return f"{ref.text}: the run exists but the platform has no log for it (404)"
        raise
    return None


def resolve(ref: Ref) -> str | None:
    """None when the ref points at something readable; otherwise one sentence saying why not."""
    path = ref.path
    if path is None:
        return f"{ref.text}: a shape this module cannot ask the platform about"
    answer, missing = _exists(ref, path)
    if missing is not None or ref.kind != "run":
        return missing
    # A run that never started has no log to keep: `startup_failure` is the whole
    # record, and asking for its log answers 404 forever (measured 2026-09-05 on
    # run/33937392727, the release run refused by the Actions policy). The run's
    # existence and its conclusion are the proof there.
    if isinstance(answer, dict) and answer.get("conclusion") == "startup_failure":
        return None
    return _log_readable(ref, path)


def _report(findings: dict[str, str], cited: dict[str, list[str]]) -> None:
    for ref, why in findings.items():
        print(f"FAIL {why} — cited by: {', '.join(cited[ref])}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Resolve every ref, print the findings, return the code."""
    parser = argparse.ArgumentParser(
        description="Every proved_by.ref in gates.yaml, resolved against GitHub (read-only)."
    )
    parser.add_argument("--root", default=".", help="the checkout (default: here)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo a bare ref belongs to")
    args = parser.parse_args(argv)
    registry = pathlib.Path(args.root) / "gates.yaml"
    try:
        cited = collect(registry)
    except (OSError, KeyError, TypeError, yaml.YAMLError) as unreadable:
        print(f"cannot read {registry}: {unreadable}", file=sys.stderr)
        return 2
    findings: dict[str, str] = {}
    try:
        for text in sorted(cited):
            why = resolve(parse(text, args.repo))
            if why is not None:
                findings[text] = why
    except (PermissionError, RuntimeError) as problem:
        print(f"could not ask the platform: {problem}", file=sys.stderr)
        return 2
    if findings:
        _report(findings, cited)
        return 1
    rows = sum(len(gates) for gates in cited.values())
    runs = sum(1 for text in cited if parse(text, args.repo).kind == "run")
    print(
        f"every proved_by ref resolves: {len(cited)} distinct refs across {rows} rows,"
        f" {runs} of them runs whose logs are still readable"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
