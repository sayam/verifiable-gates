"""Report where a project stands against a bundle of gates.

**This file is shipped, so it is standalone on purpose**: stdlib only, no import
from the package around it. `install.py` copies it into a project's `tools/`
directory, where it runs under a bare `python3` before that project has installed
its first dependency. That constraint is why the manifest is JSON rather than
YAML, and why the few lines of manifest reading here are not shared with
`verifiable_gates.manifest` — the duplication is small and the property is not.

    python3 gates_doctor.py [root] [--manifest path] [--installed]

**Two modes that measure different things, and the difference is the point:**

- `--installed` asks whether the bundle *arrived and can run*: the config exists,
  every scan script compiles. That is a claim about the installation, not about
  the project's code.
- Without the flag it **runs the scans** and exits 1 if any found something.

Gates of kind `suite` are counted and reported as waiting on the project's own
tests. They are never folded into the pass count, because a rule this bundle
cannot decide must not look like one it decided. `NA` is reported separately from
`pass` for the same reason: a scan with nothing to look at has not agreed with you.

exit 0 = clean · 1 = findings, or an incomplete install · 2 = called wrongly
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


def run_scans(root: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    """Run every scan, reporting each gate rather than stopping at the first finding."""
    failed: list[str] = []
    for gid, script in scan_entries(manifest):
        result = subprocess.run(  # noqa: S603 — argv is built here, interpreter is sys.executable
            [sys.executable, str(bundle / script), str(root)],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode == 0:
            print(f"[{'NA' if result.stdout.startswith('NA:') else 'pass':>5}] {gid}")
        else:
            print(f"[found] {gid}")
            sys.stdout.write(result.stdout)
            failed.append(gid)

    print(f"\nwaiting on this project's own tests: {suite_count(manifest)} gates")
    if failed:
        print(f"** scans found problems in {len(failed)} gates: {', '.join(failed)}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Report where a project stands against its gates.")
    parser.add_argument(
        "root", nargs="?", help="the project to look at (default: above the bundle)"
    )
    parser.add_argument("--manifest", help="path to overlay.json (default: beside this file)")
    parser.add_argument(
        "--installed",
        action="store_true",
        help="check the bundle arrived intact, without judging the project",
    )
    args = parser.parse_args(argv)

    manifest_path = (
        pathlib.Path(args.manifest).resolve() if args.manifest else here / "overlay.json"
    )
    bundle = manifest_path.parent
    root = pathlib.Path(args.root).resolve() if args.root else bundle.parent
    manifest = load_manifest(manifest_path)

    if args.installed:
        return check_installed(root, manifest, bundle)
    return run_scans(root, manifest, bundle)


if __name__ == "__main__":
    sys.exit(main())
