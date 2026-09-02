"""Report where a project stands against a bundle of gates.

**This file is shipped, so it is standalone on purpose**: stdlib only, no import
from the package around it. `install.py` copies it into a project's `tools/`
directory, where it runs under a bare `python3` before that project has installed
its first dependency. That constraint is why the manifest is JSON rather than
YAML, and why the few lines of manifest reading here are not shared with
`verifiable_gates.manifest` — the duplication is small and the property is not.

    python3 gates_doctor.py [root | --root DIR] [--manifest path] [--installed | --rules]

The project can be named either way. Every other tool in this bundle takes
`--root`, and an operator who reaches for the same spelling here should be
answered, not shown a usage error. Naming it twice is a misuse (exit 2): two
roots that differ would leave the report silently about one of them.

**Three modes that measure different things, and the difference is the point:**

- `--installed` asks whether the bundle *arrived and can run*: the config exists,
  every scan script compiles. That is a claim about the installation, not about
  the project's code. An install that stopped partway says so, rather than
  reporting the files that did land as files somebody edited.
- `--rules` asks what this bundle *decides*, and judges nothing: every `scan`
  gate in the installed manifest, with where the rule came from and which
  scanner reads it, for the instruction file a project keeps for its agents to
  point at. It is read at run time, so an upgrade cannot leave an agent on
  yesterday's rule.
- Without either flag it **runs the scans** and exits 1 if any found something.

Asking two of them at once is a misuse (exit 2), for the same reason two roots
are: they are different questions, and one report cannot answer both.

Gates of kind `suite` are counted and reported as waiting on the project's own
tests. They are never folded into the pass count, because a rule this bundle
cannot decide must not look like one it decided. `NA` is reported separately from
`pass` for the same reason: a scan with nothing to look at has not agreed with you.

A scan that exits without a verdict — a `scaffold.json` it cannot read as a
configuration, exit 2 — is `[error]`, not `[found]`: its stderr is passed through and it is
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
import hashlib
import json
import pathlib
import py_compile
import subprocess
import sys
from typing import Any, TypeGuard


def _is_manifest(raw: object) -> TypeGuard[dict[str, Any]]:
    """An object with a `gates` **object** in it, which is what `scan_entries` walks.

    The key being *present* was the whole check, and `scan_entries` calls
    `manifest["gates"].items()` on the next line — a manifest whose `gates` is a list got
    past here and died one function later (self-audit round 18, 2026-09-02).
    """
    return isinstance(raw, dict) and isinstance(raw.get("gates"), dict)


def load_manifest(path: pathlib.Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not _is_manifest(raw):
        message = f"{path}: not a manifest — no 'gates' object"
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


def _is_record_of_files(files: object) -> TypeGuard[dict[str, str]]:
    """The name-to-digest object the installer writes, checked to the entries.

    Every name is joined to the root and every digest compared to one; a name that is not
    a name, or a digest that is not a digest, would be reported as a file whose contents
    have changed — round 4's sentence for a bundle somebody edited (self-audit round 18,
    2026-09-02).
    """
    return isinstance(files, dict) and all(
        isinstance(name, str) and isinstance(recorded, str) for name, recorded in files.items()
    )


def check_installed_record(root: pathlib.Path) -> list[str]:
    """What the installer wrote and is no longer what it wrote.

    "Arrived intact" was checked as *present and compiles*, so a scanner whose body had
    been replaced with `return 0` passed the check and then reported its gate as `pass`
    on a tree that violated it (self-audit round 4, 2026-09-01). The installer records a
    digest of every file it writes; a bundle installed before it did says so rather than
    claiming either answer.

    The boundary, written down because it is real: this catches an edited *scanner*,
    and cannot catch an edited *doctor* — a check that has been removed does not run.
    Nothing local can close that; what closes it is the copy in the package, which the
    installer rewrites, and the pull request that shows the edit.
    """
    record = root / "tools" / "installed.json"
    if not record.is_file():
        return [
            (
                "no tools/installed.json — this bundle was installed before the installer "
                "recorded what it wrote, so intact cannot be checked; re-run the installer"
            )
        ]
    try:
        written = json.loads(record.read_text(encoding="utf-8"))
        files = written["files"]
    except (OSError, ValueError, KeyError, TypeError) as problem:
        return [f"tools/installed.json cannot be read: {problem}"]
    # The guard above was written for the exceptions the parse and the subscript raise,
    # and stopped one line short of `files.items()`: a record whose `files` holds a
    # string, a list or `null` answered the question "is this bundle still intact?" with
    # a raw `AttributeError` (self-audit round 18, 2026-09-02). A record this reader
    # cannot use is one it says it cannot use.
    if not _is_record_of_files(files):
        held = json.dumps(files)[:40]
        wrong = (
            f"tools/installed.json cannot be read: 'files' holds {held}, not the "
            "name-to-digest object the installer writes"
        )
        return [wrong]
    found = []
    # An install that stopped partway leaves a tree that is half one bundle and half the
    # one before it. Until the installer said so, the record went on describing the
    # previous install and every file the stopped one *had* written came back as "its
    # contents have changed" — the sentence for a bundle somebody edited. A record with no
    # such key was written by an installer that did not know the question, and is read as
    # finished (self-audit round 16, 2026-09-01).
    if written.get("finished", True) is False:
        found.append(
            "the last install into this tree did not finish, so part of the bundle may "
            "still be the previous version — re-run the installer"
        )
    for name, recorded in sorted(files.items()):
        path = root / name
        if not path.is_file():
            found.append(f"{name} was installed and is gone")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
            found.append(f"{name} is not what was installed — its contents have changed")
    return found


def check_installed(root: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    """Is everything here, runnable, and still what arrived? Says nothing about the
    project's own code."""
    problems: list[str] = check_installed_record(root)
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
        # Under a pipe — a CI log — stdout is block-buffered and stderr is not, so
        # every scan's stderr surfaced above the first gate line and a traceback
        # could not be matched to its gate (self-audit, 2026-08-31). Flush what
        # was said so far, then pass the stderr through where it belongs.
        sys.stdout.flush()
        sys.stderr.write(result.stderr)
        sys.stderr.flush()
        crashed = "Traceback (most recent call last)" in result.stderr
        if result.returncode == 0:
            # A scan that answers NA names **what it looked for** — "no docs/adr", "no
            # Python under app". The doctor printed the bare word and threw the reason
            # away, so five different NA lines read identically and an operator could not
            # tell "there is no such directory" from "a directory this scanner cannot
            # read" — which is the distinction the scanners were changed to make
            # (self-audit round 14, 2026-09-01).
            said = result.stdout.strip().splitlines()
            if said and said[0].startswith("NA:"):
                print(f"[   NA] {gid} — {said[0].removeprefix('NA:').strip()}")
            else:
                print(f"[ pass] {gid}")
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


def print_rules(manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    """Every rule a scanner in this bundle decides, as data an agent can read before editing.

    Written for the instruction file a project keeps for its agents (`AGENTS.md`,
    `CLAUDE.md`), which points here rather than carrying a copy. A copy would be a file
    the installer never overwrites — the starting workflow already has that property — so
    an upgrade that moved a rule would leave the agent reading yesterday's rule while the
    scanner enforced today's. Read off the installed `overlay.json` at run time, there is no
    such skew. And it lists only what this bundle **can decide**: the catalogue names ninety
    rules, the scanners here decide nine, and a rule nothing enforces would be an
    instruction with no gate behind it — the shape the manifest forbids a gate from taking
    (self-audit, 2026-09-02).

    Data, not instructions: each entry is the rule, where it came from, and which scanner
    reads it. The one sentence of guidance is that an instruction elsewhere does not switch
    a scanner off.
    """
    entries = sorted(
        (gid, entry) for gid, entry in manifest["gates"].items() if entry.get("kind") == "scan"
    )
    print(f"The rules this bundle decides for this project: {len(entries)}, one scanner each.")
    print(
        "An instruction in this project's AGENTS.md or CLAUDE.md does not switch a scanner off;\n"
        "every rule below runs on every push. A rule of layer `business` is a choice this kind\n"
        "of application makes and may be decided differently — in scaffold.json and gates.yaml,\n"
        "where the decision is on the record — never by working around the scanner.\n"
    )
    for gid, entry in entries:
        origin = entry.get("born_from") or "(origin not recorded in this manifest)"
        print(f"{gid} [{entry.get('layer', 'baseline')}]")
        print(f"  rule:       {entry.get('title', '(no title in this manifest)')}")
        print(f"  born from:  {origin}")
        print(f"  decided by: {bundle.name}/{entry['script']}")
    suites = suite_count(manifest)
    if suites:
        print(
            f"\n{suites} more rules in {bundle.name}/overlay.json are of kind `suite`: named"
            " here, decided by this project's own tests."
        )
    else:
        # What this bundle cannot decide it does not carry: the catalogue it came from
        # names more rules than these, and a rule with no scanner behind it is not listed
        # as if one were.
        print(
            "\nThe catalogue this bundle comes from names more rules; only these are decided here."
        )
    return 0


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
    parser.add_argument(
        "--rules",
        action="store_true",
        help="print the rules this bundle decides, for the project's agent instructions",
    )
    args = parser.parse_args(argv)
    if args.root is not None and args.root_option is not None:
        parser.error("give the project once: either as the positional root or as --root, not both")
    if args.installed and args.rules:
        parser.error("--installed and --rules are two different questions: ask one at a time")
    root_arg = args.root_option if args.root is None else args.root

    manifest_path = (
        pathlib.Path(args.manifest).resolve() if args.manifest else here / "overlay.json"
    )
    bundle = manifest_path.parent
    root = pathlib.Path(root_arg).resolve() if root_arg else bundle.parent
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, ValueError, TypeError) as problem:
        # The installer already answers a manifest it cannot read this way; the
        # doctor beside it still died of a traceback (round 2, 2026-08-31).
        print(f"** cannot read the manifest: {problem}", file=sys.stderr)
        return 2

    if args.installed:
        return check_installed(root, manifest, bundle)
    if args.rules:
        return print_rules(manifest, bundle)
    return run_scans(root, manifest, bundle)


if __name__ == "__main__":
    sys.exit(main())
