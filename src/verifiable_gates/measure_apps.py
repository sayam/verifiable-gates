"""Measuring generated apps with one battery, so a claim about rules can be checked.

A bundle of rules is worth what its effect can be shown to be. Saying it changes
what agents write is cheap; the claim only means something if the resulting code
is read the same way on every arm of the comparison, by an instrument that does
not know which arm it is looking at.

Three axes, kept apart because each answers a different question:

1. **The bundle's own scanners** — one finding count per gate, over the apps
   themselves. **`na` never collapses into `ok`**: "there was nothing of that kind
   to look at" is not "we looked and it was clean", and folding them together
   flatters the smallest app in the set.
2. **The ASVS probe** — ten controls a small web app either shows traces of or
   does not, with a third answer for "not applicable".
3. **An outside scanner** — a measure this project did not define. Not configured
   means **skipped, reported as skipped**, never zero.

**Two rules that keep the measurement honest, both of which cost the bundle:**

- **Every app is scanned with the same configuration.** A different config is a
  different gate, and then the arms are not comparable at all — so the bundle's
  own default is copied into each app before scanning.
- **Whatever the installer put there is deleted before measuring.** The arm that
  installed the bundle receives tooling and a starting workflow; counting those as
  its own output is adding the measurer's work to one side of its own experiment.
  Removing them is the direction that is **harsh toward the bundle**, which is the
  correct direction when the person measuring has a stake in the answer.

**Nothing here decides anything.** It prints numbers and writes them out; what
they mean belongs in the write-up, next to the limits of the instrument.

Role: reader — it reports. Its evidence is that the numbers match the source and
that nothing is dropped in silence.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from verifiable_gates.asvs_probe import CHECKS, is_ours, probe

__all__ = [
    "OVERLAY_ARTIFACTS",
    "Battery",
    "checkers",
    "main",
    "measure",
    "run_scans",
    "staged",
]

# **A ceiling on how long we wait for something we started** — `subprocess.run`
# without `timeout=` waits forever, which in CI is a job that never ends.
CHECKER_TIMEOUT_SECONDS = 300  # one scanner over one generated app
SCANNER_TIMEOUT_SECONDS = 1800  # an outside scanner over a whole app

BUNDLE = pathlib.Path(__file__).resolve().parent

# What the installer places itself — not any arm's work, so it comes out of every
# app before measuring. The arm that installed nothing does not have these anyway,
# which is why removing them takes nothing away from it.
OVERLAY_ARTIFACTS = ("tools", ".github/workflows/gates.yml", "scaffold.json")


def checkers(bundle: pathlib.Path = BUNDLE) -> list[pathlib.Path]:
    """The bundle's scanners — **the ones actually in use**, not a copy of them.

    Measuring with a copy is measuring something other than what the report names.
    """
    return sorted((bundle / "checks").glob("scan_*.py"))


def run_scans(app: pathlib.Path, bundle: pathlib.Path = BUNDLE) -> dict[str, Any]:
    """Per scanner: `na`, `ok`, or how many findings — three answers, never two."""
    shutil.copy2(bundle / "scaffold.json.default", app / "scaffold.json")
    status: dict[str, Any] = {}
    for checker in checkers(bundle):
        try:
            done = subprocess.run(  # noqa: S603 — the bundle's own scanner, a path the caller gave
                [sys.executable, str(checker), str(app)],
                timeout=CHECKER_TIMEOUT_SECONDS,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.TimeoutExpired as expired:
            # The ceiling is ours, so the answer at the ceiling has to be ours too. This
            # function produces the evidence a published table is built from, and a
            # `TimeoutExpired` nobody routes took the whole table with it — while a fourth
            # answer in the dictionary would be a hole in a table that reads as complete.
            # It stops, saying which scanner and which ceiling (round 19, 2026-09-02).
            message = (
                f"{checker.name} did not answer within {CHECKER_TIMEOUT_SECONDS} seconds"
                f" at {app} — this measurement has no number to publish"
            )
            raise SystemExit(message) from expired
        gate = checker.stem.removeprefix("scan_")
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        if any(line.startswith("NA:") for line in lines):
            status[gate] = "na"
        elif done.returncode == 1:
            status[gate] = len([line for line in lines if not line.startswith("NA:")])
        else:
            status[gate] = "ok"
    return status


def run_scanner(app: pathlib.Path, binary: pathlib.Path | None, configs: list[str]) -> int | None:
    """How many findings an outside scanner reports — `None` when it was not asked for.

    **The binary arrives as an argument, never from the environment.** A runner
    named by an environment variable is one that can change without appearing in
    the command, and it is checked to exist and be a file before it is started.
    """
    if binary is None:
        return None
    resolved = binary.resolve(strict=True)
    if not resolved.is_file():
        raise SystemExit(f"not a file: {resolved}")
    try:
        done = subprocess.run(  # noqa: S603 — a path the caller gave, resolved and checked above
            [
                str(resolved),
                "scan",
                *[part for config in configs for part in ("--config", config)],
                "--metrics=off",
                "--json",
                "--quiet",
            ],
            cwd=app,
            timeout=SCANNER_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        # The same answer this function already gives a scanner that fails: a number is
        # the whole of what it returns, and there is none to return (round 19, 2026-09-02).
        message = f"the scanner did not answer within {SCANNER_TIMEOUT_SECONDS} seconds at {app}"
        raise SystemExit(message) from expired
    if done.returncode not in (0, 1):
        raise SystemExit(f"the scanner failed at {app}: {done.stderr[-300:]}")
    # A number is the whole output of this function, so a report it cannot read must not
    # become one. The scanner's format is not ours to hold still (self-audit round 18,
    # 2026-09-02).
    try:
        report = json.loads(done.stdout)
        found = report["results"]
    except (ValueError, TypeError, KeyError) as problem:
        raise SystemExit(f"the scanner's report at {app} could not be read: {problem}") from problem
    if not isinstance(found, list):
        raise SystemExit(f"the scanner's report at {app} has a 'results' that is not a list")
    return len(found)


def staged(app: pathlib.Path, into: pathlib.Path) -> pathlib.Path:
    """A copy of the app with **whatever the installer added taken out**.

    The arm that installed the bundle gets tooling, a config and a starting
    workflow. Counting those as its own output adds the measurer's work to one
    side of its own experiment.
    """
    target = into / app.name
    shutil.copytree(app, target, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    if (target / "tools" / "overlay.json").is_file():
        for relative in OVERLAY_ARTIFACTS:
            path = target / relative
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
    return target


@dataclasses.dataclass(frozen=True)
class Battery:
    """What every app in a comparison is measured with — **one of these, not one each**.

    Kept together so that a caller cannot vary the instrument between arms by
    forgetting an argument. That is the failure this whole module exists to avoid.
    """

    scanner: pathlib.Path | None = None
    configs: tuple[str, ...] = ()
    bundle: pathlib.Path = BUNDLE


def measure(
    app: pathlib.Path, arm: str, into: pathlib.Path, battery: Battery | None = None
) -> dict[str, Any]:
    """All three axes over one app, on the copy the installer's work was removed from."""
    battery = battery or Battery()
    original = app
    app = staged(app, into)
    ours = [path for path in app.rglob("*.py") if is_ours(path)]
    asvs = probe(app)
    gates = run_scans(app, battery.bundle)
    return {
        "arm": arm,
        "app": original.name,
        "overlay_installed": (original / "tools" / "overlay.json").is_file(),
        # **Count only the files the probe actually read.** The counter and the
        # instrument have to be looking at one tree, or "lines the agent wrote"
        # silently includes a virtual environment somebody left behind and the
        # arms stop being comparable.
        "py_files": len(ours),
        "py_lines": sum(
            len(path.read_text(encoding="utf-8", errors="replace").splitlines()) for path in ours
        ),
        "gates": gates,
        "gate_findings": sum(value for value in gates.values() if isinstance(value, int)),
        "gates_na": sorted(name for name, value in gates.items() if value == "na"),
        "asvs": asvs,
        "asvs_pass": sum(1 for value in asvs.values() if value is True),
        "asvs_fail": sorted(name for name, value in asvs.items() if value is False),
        "asvs_na": sorted(name for name, value in asvs.items() if value is None),
        "scanner": run_scanner(app, battery.scanner, list(battery.configs)),
    }


def table(rows: list[dict[str, Any]]) -> str:
    """One row per app — with what was skipped and what was not applicable on the face of it."""
    lines = [
        f"| arm | app | .py lines | gate findings | ASVS passed (of {len(CHECKS)}) | scanner |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        scanner = "skipped" if row["scanner"] is None else row["scanner"]
        na = len(row["asvs_na"])
        asvs = f"{row['asvs_pass']}" + (f" (+{na} n/a)" if na else "")
        lines.append(
            f"| {row['arm']} | {row['app']} | {row['py_lines']} "
            f"| {row['gate_findings']} | {asvs} | {scanner} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Measure every app under a root, print the table, optionally write the rows."""
    parser = argparse.ArgumentParser(description="Measure generated apps with one battery.")
    parser.add_argument("root", type=pathlib.Path, help="a directory of arms, each of apps")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--scanner", type=pathlib.Path, help="an outside scanner; omit to skip")
    parser.add_argument(
        "--config", action="append", default=[], help="a rule set for the outside scanner"
    )
    args = parser.parse_args(argv)

    battery = Battery(scanner=args.scanner, configs=tuple(args.config))
    with tempfile.TemporaryDirectory() as staging:
        rows = [
            measure(app, arm.name, pathlib.Path(staging) / arm.name / app.name, battery)
            for arm in sorted(p for p in args.root.iterdir() if p.is_dir())
            for app in sorted(p for p in arm.iterdir() if p.is_dir())
        ]

    print(table(rows))
    if args.output:
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
