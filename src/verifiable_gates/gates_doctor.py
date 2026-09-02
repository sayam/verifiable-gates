"""Report where a project stands against a bundle of gates.

**This file is shipped, so it is standalone on purpose**: stdlib only, no import
from the package around it. `install.py` copies it into a project's `tools/`
directory, where it runs under a bare `python3` before that project has installed
its first dependency. That constraint is why the manifest is JSON rather than
YAML, and why the few lines of manifest reading here are not shared with
`verifiable_gates.manifest` — the duplication is small and the property is not.

    python3 gates_doctor.py [root | --root DIR] [--manifest path]
                            [--installed | --rules] [--sarif FILE]

The project can be named either way. Every other tool in this bundle takes
`--root`, and an operator who reaches for the same spelling here should be
answered, not shown a usage error. Naming it twice is a misuse (exit 2): two
roots that differ would leave the report silently about one of them.

**Three modes that measure different things, and the difference is the point:**

- `--installed` asks whether the bundle *arrived and can run*: the config exists,
  every scan script compiles. That is a claim about the installation, not about
  the project's code. An install that stopped partway says so, rather than
  reporting the files that did land as files somebody edited. A file this doctor
  **cannot read** is a third sentence, apart from *gone* and *changed*: it is red,
  because a scan nobody can read does not run, and it is not an accusation.
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

Every file here is read first and the exception answered, never asked about and
then read: `is_file()` followed by `read_bytes()` is two questions with a gap between
them, and a file that passed the first and failed the second — `chmod 000`, or removed
in the gap — was a `PermissionError` traceback beside exit 1, the code that means *the
installation is incomplete*, from a reader that had decided nothing (self-audit round
20, 2026-09-03). It is exit 1 still, with the sentence above: the question this mode
answers is whether the bundle can run, and a scan that cannot be read cannot.

**`--sarif FILE` writes the same run as SARIF 2.1.0 beside the report**, for the
readers that speak it — GitHub code scanning (`upload-sarif`), reviewdog, an IDE —
so a project's gates land where its other findings already land, without those
readers learning anything about this bundle. The text report stays on stdout and
stays the default; SARIF is a format, not a second opinion. The scanners are not
touched: each is shipped standalone and speaks one line per finding, and the doctor
already reads all nine, so the doctor translates. What the translation refuses to
lose is the third answer. A finding is a `result`; `NA` and *the scan did not answer*
are **not** — they are `toolExecutionNotifications` on the invocation (level `note`
and `error`), and any error marks the invocation `executionSuccessful: false`. A
reader that only counts results sees a clean run where a scan could not look, which
is the sentence the manifest forbids; a reader that reads invocations sees the
truth. A location is attached only when the path the scanner named exists under
the root — a location nobody can open is worse than none. The SARIF file that cannot
be written is exit 2 with a sentence, after the report has been printed: the
verdict stood, the artefact asked for did not arrive.

exit 0 = clean · 1 = findings, or an incomplete install · 2 = called wrongly

Role: reader — it reports where a project stands. Its evidence is that each
scanner's own tests decide the verdicts it relays, and that NA is never a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import py_compile
import re
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
    try:
        written = json.loads(record.read_text(encoding="utf-8"))
        files = written["files"]
    except FileNotFoundError:
        return [
            (
                "no tools/installed.json — this bundle was installed before the installer "
                "recorded what it wrote, so intact cannot be checked; re-run the installer"
            )
        ]
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
        said = _held_to_the_record(root / name, name, recorded)
        if said is not None:
            found.append(said)
    return found


def _held_to_the_record(path: pathlib.Path, name: str, recorded: str) -> str | None:
    """One recorded file against the tree: gone, unreadable, changed, or nothing to say.

    Read first, and answer the exception. This was `is_file()` and then `read_bytes()` on
    the next line — two questions with a gap between them — and a file that passed the
    first and failed the second, `chmod 000` or removed in the gap, was a `PermissionError`
    traceback beside exit 1, the code that means *the installation is incomplete*, from a
    reader that had decided nothing (self-audit round 20, 2026-09-03). Unreadable is its
    own sentence: it is not round 4's "its contents have changed", which means somebody
    edited the bundle, and a file nobody can read has not been shown to be either.
    """
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return f"{name} was installed and is gone"
    except OSError as problem:
        return (
            f"{name} cannot be read ({problem.strerror or problem}), so whether it is still "
            "what was installed cannot be checked"
        )
    if actual != recorded:
        return f"{name} is not what was installed — its contents have changed"
    return None


def check_installed(root: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path) -> int:
    """Is everything here, runnable, and still what arrived? Says nothing about the
    project's own code."""
    problems: list[str] = check_installed_record(root)
    if not (root / "scaffold.json").is_file():
        problems.append("no scaffold.json — the install did not finish")

    scans = scan_entries(manifest)
    for gid, script in scans:
        # The same one road as `_held_to_the_record`, for the scans the record may not
        # name: a bundle with no record reached `py_compile` and died there instead.
        try:
            py_compile.compile(str(bundle / script), doraise=True)
        except FileNotFoundError:
            problems.append(f"{gid}: {script} is missing")
        except OSError as denied:
            problems.append(
                f"{gid}: {script} cannot be read ({denied.strerror or denied}) — a scan "
                "nobody can read does not run"
            )
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


# One scan's outcome, kept for the SARIF writer: the gate, one of pass / na / found /
# error, the lines the scan printed, and the sentence the doctor said about it.
Outcome = tuple[str, str, list[str], str]


def run_scans(
    root: pathlib.Path,
    manifest: dict[str, Any],
    bundle: pathlib.Path,
    sarif: pathlib.Path | None = None,
) -> int:
    """Run every scan, reporting each gate rather than stopping at the first finding."""
    failed: list[str] = []
    broken: list[str] = []
    outcomes: list[Outcome] = []
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
            reason = f"the scan did not answer (timed out after {SCAN_TIMEOUT}s)"
            print(f"[error] {gid} — {reason}")
            broken.append(gid)
            outcomes.append((gid, "error", [], reason))
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
                reason = said[0].removeprefix("NA:").strip()
                print(f"[   NA] {gid} — {reason}")
                outcomes.append((gid, "na", said, reason))
            else:
                print(f"[ pass] {gid}")
                outcomes.append((gid, "pass", said, ""))
        elif result.returncode == 1 and result.stdout.strip() and not crashed:
            print(f"[found] {gid}")
            sys.stdout.write(result.stdout)
            failed.append(gid)
            outcomes.append((gid, "found", result.stdout.strip().splitlines(), ""))
        else:
            reason = f"the scan did not answer (exit {result.returncode})"
            print(f"[error] {gid} — {reason}")
            broken.append(gid)
            outcomes.append((gid, "error", [], f"{reason}\n{result.stderr}".strip()))

    print(f"\nwaiting on this project's own tests: {suite_count(manifest)} gates")
    if failed:
        print(f"** scans found problems in {len(failed)} gates: {', '.join(failed)}")
    if broken:
        print(f"** {len(broken)} scans did not answer, which is no verdict: {', '.join(broken)}")
    verdict = 1 if failed or broken else 0
    if sarif is not None and not write_sarif(sarif, root, manifest, outcomes):
        return 2
    return verdict


# ---------------------------------------------------------------- SARIF

SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)
INFORMATION_URI = "https://github.com/sayam/verifiable-gates"
# `<path>:<line> …`, `<path>: …` or `<path> …` at the head of a finding line. Whether
# it is a location is decided by the tree, not by the shape: see `_sarif_result`.
LOCATION = re.compile(r"^(?P<path>[^\s:]+)(?::(?P<line>\d+))?:?(?:\s+|$)")


def _installed_version(root: pathlib.Path) -> str | None:
    """The bundle version the installer recorded, or nothing — never a guess."""
    try:
        written = json.loads((root / "tools" / "installed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = written.get("version") if isinstance(written, dict) else None
    return version if isinstance(version, str) else None


def _sarif_result(root: pathlib.Path, gid: str, line: str) -> dict[str, Any]:
    """One finding line as a SARIF result, located only where the tree agrees."""
    text = line.removeprefix(f"{gid}:").strip()
    result: dict[str, Any] = {"ruleId": gid, "level": "error", "message": {"text": text}}
    head = LOCATION.match(text)
    if head is None:
        return result
    path = pathlib.Path(head.group("path"))
    # A finding that names a path the reader cannot open under the root — a key from
    # `scaffold.json`, a sentence, a path outside — gets a message and no location:
    # an annotation on the wrong file is a reader sent to the wrong place.
    if path.is_absolute() or not (root / path).is_file():
        return result
    region = {"startLine": int(head.group("line"))} if head.group("line") else {}
    location: dict[str, Any] = {
        "artifactLocation": {"uri": path.as_posix(), "uriBaseId": "%SRCROOT%"}
    }
    if region:
        location["region"] = region
    result["locations"] = [{"physicalLocation": location}]
    return result


def sarif_log(
    root: pathlib.Path, manifest: dict[str, Any], outcomes: list[Outcome]
) -> dict[str, Any]:
    """The whole run as one SARIF 2.1.0 log. Pure: the same outcomes give the same log."""
    gates = manifest["gates"]
    rules = []
    for gid, _script in scan_entries(manifest):
        gate = gates[gid]
        rule: dict[str, Any] = {
            "id": gid,
            "shortDescription": {"text": str(gate.get("title", gid))},
        }
        if isinstance(gate.get("born_from"), str):
            rule["fullDescription"] = {"text": gate["born_from"]}
            rule["help"] = {"text": gate["born_from"]}
        if isinstance(gate.get("layer"), str):
            rule["properties"] = {"layer": gate["layer"]}
        rules.append(rule)
    results: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    for gid, kind, said, sentence in outcomes:
        if kind == "found":
            results += [_sarif_result(root, gid, line) for line in said if line.strip()]
        elif kind in {"na", "error"}:
            # The third answer, kept as what it is: neither a result nor silence.
            level = "note" if kind == "na" else "error"
            notes.append(
                {"level": level, "message": {"text": sentence}, "associatedRule": {"id": gid}}
            )
    driver: dict[str, Any] = {
        "name": "verifiable-gates",
        "informationUri": INFORMATION_URI,
        "rules": rules,
    }
    version = _installed_version(root)
    if version is not None:
        driver["version"] = version
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": driver},
                "originalUriBaseIds": {"%SRCROOT%": {"uri": root.as_uri() + "/"}},
                "invocations": [
                    {
                        "executionSuccessful": not any(k == "error" for _g, k, _s, _t in outcomes),
                        "toolExecutionNotifications": notes,
                    }
                ],
                "results": results,
            }
        ],
    }


def _write_whole(out: pathlib.Path, text: str) -> None:
    """The text as `out`, whole or not at all — a sibling file renamed over the target.

    `write_text` truncates first, and a reader arriving between that and the write — the
    upload step, an IDE watching the file — saw an empty log or part of one, 99.7% of
    the time at this log's size; a doctor killed inside that window left 0 bytes. The
    package has one writer for this (`files.py`); this file is shipped standalone and
    may import nothing from it, so it carries the dozen lines (self-audit round 20,
    2026-09-03).
    """
    target = out.resolve()
    beside = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        create = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        # 0o644 before the umask, not 0o666: the sibling exists under its own name for
        # the length of the write, and a mode the umask does not narrow would be a file
        # anyone could write for that moment.
        with os.fdopen(os.open(beside, create, 0o644), "wb") as h:
            h.write(text.encode("utf-8"))
            h.flush()
            os.fsync(h.fileno())
        beside.replace(target)
    except OSError:
        beside.unlink(missing_ok=True)
        raise


def write_sarif(
    out: pathlib.Path, root: pathlib.Path, manifest: dict[str, Any], outcomes: list[Outcome]
) -> bool:
    """The log on disk, or a sentence on stderr and False — never a traceback."""
    try:
        _write_whole(out, json.dumps(sarif_log(root, manifest, outcomes), indent=2) + "\n")
    except OSError as problem:
        sys.stdout.flush()
        print(
            f"** cannot write the SARIF: {out}: {problem} — the report above stands",
            file=sys.stderr,
        )
        return False
    return True


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
    parser.add_argument(
        "--sarif",
        metavar="FILE",
        help="also write this run as SARIF 2.1.0, for code scanning, reviewdog or an IDE",
    )
    args = parser.parse_args(argv)
    if args.sarif and (args.installed or args.rules):
        parser.error("--sarif describes a run of the scans; --installed and --rules run none")
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
    return run_scans(root, manifest, bundle, pathlib.Path(args.sarif) if args.sarif else None)


if __name__ == "__main__":
    sys.exit(main())
