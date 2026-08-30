"""Report where a project stands against a bundle of gates.

**This file is shipped, so it is standalone on purpose**: stdlib only, no import
from the package around it. `install.py` copies it into a project's `tools/`
directory, where it runs under a bare `python3` before that project has installed
its first dependency. That constraint is why the manifest is JSON rather than
YAML, and why the few lines of manifest reading here are not shared with
`verifiable_gates.manifest` — the duplication is small and the property is not.

    python3 gates_doctor.py [root | --root DIR] [--manifest path] [--installed]

The project can be named either way. Every other tool in this bundle takes
`--root`, and an operator who reaches for the same spelling here should be
answered, not shown a usage error. Naming it twice is a misuse (exit 2): two
roots that differ would leave the report silently about one of them.

**Two modes that measure different things, and the difference is the point:**

- `--installed` asks whether the bundle *arrived and can run*: the config exists,
  every scan script compiles. That is a claim about the installation, not about
  the project's code.
- Without the flag it **runs the scans** and exits 1 if any found something.

Gates of kind `suite` are counted and reported as waiting on the project's own
tests. They are never folded into the pass count, because a rule this bundle
cannot decide must not look like one it decided. `NA` is reported separately from
`pass` for the same reason: a scan with nothing to look at has not agreed with you.

A scan that exits without a verdict — a traceback on a broken `scaffold.json`,
exit 2 — is `[error]`, not `[found]`: its stderr is passed through and it is
counted apart from the findings, because a tool that crashed has judged nothing
(an outside audit on 2026-08-30 fed a malformed config and the doctor answered
`[found]` seven times with the tracebacks swallowed). It is still red. The same
answer for a scan that hangs past its timeout (the doctor tracebacked with
`TimeoutExpired`, outside audit 2026-08-31) and for one that printed part of a
verdict and then crashed — a traceback on stderr beside exit 1 means the scan
did not finish judging, however much it said first.

exit 0 = clean · 1 = findings, or an incomplete install · 2 = called wrongly

Role: reader — it reports where a project stands. Its evidence is that each
scanner's own tests decide the verdicts it relays, and that NA is never a pass.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import py_compile
import subprocess
import sys
from typing import Any


def load_manifest(path: pathlib.Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "gates" not in raw:
        message = f"{path}: not a manifest — no 'gates'"
        raise ValueError(message)
    return raw


def scan_entries(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    return sorted(
        (gid, entry["script"])
        for gid, entry in manifest["gates"].items()
        if entry.get("kind") == "scan"
    )


def suite_count(manifest: dict[str, Any]) -> int:
    return sum(1 for entry in manifest["gates"].values() if entry.get("kind") == "suite")


def check_installed(root: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    """Is everything here and runnable? Says nothing about the project's own code."""
    problems: list[str] = []
    if not (root / "scaffold.json").is_file():
        problems.append("no scaffold.json — the install did not finish")

    scans = scan_entries(manifest)
    for gid, script in scans:
        path = bundle / script
        if not path.is_file():
            problems.append(f"{gid}: {script} is missing")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            problems.append(f"{gid}: {script} does not compile: {error}")

    if problems:
        print("** the installation is incomplete:")
        for problem in problems:
            print(f"   {problem}")
        return 1

    total, suites = len(manifest["gates"]), suite_count(manifest)
    print(f"installed: {total} gates ({len(scans)} scan · {suites} suite) — every scan runs")
    return 0


# One scan gets five minutes — a scan is a file read, not a build; one that is
# still running has hung, and a hang is an answer the report has to carry.
SCAN_TIMEOUT = 300


def run_scans(root: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    """Run every scan, reporting each gate rather than stopping at the first finding."""
    failed: list[str] = []
    broken: list[str] = []
    for gid, script in scan_entries(manifest):
        try:
            result = subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
                [sys.executable, str(bundle / script), str(root)],
                capture_output=True,
                text=True,
                check=False,
                timeout=SCAN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"[error] {gid} — the scan did not answer (timed out after {SCAN_TIMEOUT}s)")
            broken.append(gid)
            continue
        sys.stderr.write(result.stderr)
        crashed = "Traceback (most recent call last)" in result.stderr
        if result.returncode == 0:
            print(f"[{'NA' if result.stdout.startswith('NA:') else 'pass':>5}] {gid}")
        elif result.returncode == 1 and result.stdout.strip() and not crashed:
            print(f"[found] {gid}")
            sys.stdout.write(result.stdout)
            failed.append(gid)
        else:
            print(f"[error] {gid} — the scan did not answer (exit {result.returncode})")
            broken.append(gid)

    print(f"\nwaiting on this project's own tests: {suite_count(manifest)} gates")
    if failed:
        print(f"** scans found problems in {len(failed)} gates: {', '.join(failed)}")
    if broken:
        print(f"** {len(broken)} scans did not answer, which is no verdict: {', '.join(broken)}")
    return 1 if failed or broken else 0


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Report where a project stands against its gates.")
    parser.add_argument(
        "root", nargs="?", help="the project to look at (default: above the bundle)"
    )
    parser.add_argument(
        "--root", dest="root_option", metavar="DIR", help="the same, spelt like the other tools"
    )
    parser.add_argument("--manifest", help="path to overlay.json (default: beside this file)")
    parser.add_argument(
        "--installed",
        action="store_true",
        help="check the bundle arrived intact, without judging the project",
    )
    args = parser.parse_args(argv)
    if args.root is not None and args.root_option is not None:
        parser.error("give the project once: either as the positional root or as --root, not both")
    root_arg = args.root_option if args.root is None else args.root

    manifest_path = (
        pathlib.Path(args.manifest).resolve() if args.manifest else here / "overlay.json"
    )
    bundle = manifest_path.parent
    root = pathlib.Path(root_arg).resolve() if root_arg else bundle.parent
    manifest = load_manifest(manifest_path)

    if args.installed:
        return check_installed(root, manifest, bundle)
    return run_scans(root, manifest, bundle)


if __name__ == "__main__":
    sys.exit(main())
