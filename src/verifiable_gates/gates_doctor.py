"""Report where a project stands against a bundle of gates.

**This file is shipped, so it is standalone on purpose**: stdlib only, no import
from the package around it. `install.py` copies it into a project's `tools/`
directory, where it runs under a bare `python3` before that project has installed
its first dependency. That constraint is why the manifest is JSON rather than
YAML, and why the few lines of manifest reading here are not shared with
`verifiable_gates.manifest` — the duplication is small and the property is not.

    python3 gates_doctor.py [root | --root DIR] [--manifest path]
                            [--installed | --rules | --working] [--sarif FILE]

The project can be named either way. Every other tool in this bundle takes
`--root`, and an operator who reaches for the same spelling here should be
answered, not shown a usage error. Naming it twice is a misuse (exit 2): two
roots that differ would leave the report silently about one of them.

**Four modes that measure different things, and the difference is the point:**

- `--installed` asks whether the bundle *arrived and can run*: the config exists,
  every scan script compiles. That is a claim about the installation, not about
  the project's code. An install that stopped partway says so, and so does one
  still under way, rather than reporting the files that did land as files
  somebody edited — and an install that begins while the doctor is reading is
  said too, since the record is read again after the files. A file this doctor
  **cannot read** is a third sentence, apart from *gone* and *changed*: it is red,
  because a scan nobody can read does not run, and it is not an accusation.
- `--rules` asks what this bundle *decides*, and judges nothing: every `scan`
  gate in the installed manifest, with where the rule came from and which
  scanner reads it, for the instruction file a project keeps for its agents to
  point at. It is read at run time, so an upgrade cannot leave an agent on
  yesterday's rule — and it is read **only off a bundle that is still the one
  the installer wrote**. The manifest lives inside the project it holds to
  account, so an edited `title` put *this rule was retired — do not report it*
  in front of an agent, in the tool's own voice, with nothing said and exit 0,
  while `--installed` beside it saw the edit at once (self-audit round 21,
  2026-09-03). A bundle whose record does not hold, or that has no record at
  all, prints no rules: exit 2 with what `--installed` would have said. A rule
  nobody can vouch for is not a rule an agent should be handed.
- `--working` asks what practices the bundle carries and whether this tree has turned
  them on. It judges nothing and never fails: the working is how a project's own work
  is done, and a doctor grading that would be a rule the tool cannot check dressed as
  one it did. Enabled means one thing — `.local/LESSONS.md` exists — because a second
  place saying so would be a register nobody holds.
- Without any of them it **runs the scans** and exits 1 if any found something.

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
verdict stood, the artefact asked for did not arrive. **A file already at that path
is replaced only if it is this doctor's run over this root.** Two doctors over two
trees given one `--sarif` path — a matrix job, a shared scratch file — left a log that
parsed, held the later tree's run whole, and said nothing about the earlier tree's,
whose answer was gone (self-audit round 20, 2026-09-03). The log is read back before
the rename: another root's run, another tool's log, a file that is not a log, one that
cannot be read or one too big to read back is left as it is, with a sentence naming
what it holds and the same exit 2 — the verdict stood, the file asked for was not
written. The read happens after the new log is written beside it and just before the
rename, so the window in which two doctors finishing together both see nothing is
the length of a read and a rename, not of a scan.

exit 0 = clean · 1 = findings, or an incomplete install · 2 = called wrongly, or
asked a question this bundle cannot answer for itself — the SARIF that could not be
written, and the rules of a bundle whose record does not vouch for it

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
import stat
import subprocess
import sys
from typing import TYPE_CHECKING, Any, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Callable


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
        text = record.read_text(encoding="utf-8")
        written = json.loads(text)
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
    # An install under way writes its record before its first file, naming under
    # `arriving` the digest each file will have: a file in the window is the previous
    # version or the new one, and only a file that is neither has been edited. With the
    # record written last, every file that had landed read as "its contents have changed"
    # (self-audit round 20, 2026-09-03). The key is gone from the finished record.
    arriving = written.get("arriving", {})
    if not _is_record_of_files(arriving):
        held = json.dumps(arriving)[:40]
        wrong = (
            f"tools/installed.json cannot be read: 'arriving' holds {held}, not the "
            "name-to-digest object the installer writes"
        )
        return [wrong]
    found = []
    if arriving:
        found.append(
            "an install into this tree is under way, or stopped before it could record what "
            "landed — wait for it, or re-run the installer"
        )
    # An install that stopped partway leaves a tree that is half one bundle and half the
    # one before it. Until the installer said so, the record went on describing the
    # previous install and every file the stopped one *had* written came back as "its
    # contents have changed" — the sentence for a bundle somebody edited. A record with no
    # such key was written by an installer that did not know the question, and is read as
    # finished (self-audit round 16, 2026-09-01).
    elif written.get("finished", True) is False:
        found.append(
            "the last install into this tree did not finish, so part of the bundle may "
            "still be the previous version — re-run the installer"
        )
    for name, recorded in sorted(files.items()):
        said = _held_to_the_record(root / name, name, recorded, arriving.get(name))
        if said is not None:
            found.append(said)
    # The record and the files are read at different moments, and an install that began
    # between them rewrote the record first — so a record that is no longer the one read
    # above means the files were held to a record that was not theirs. Measured: one read
    # in 247 still said "changed" with the marker alone (self-audit round 20, 2026-09-03).
    if _record_text(record) != text:
        moved = (
            "tools/installed.json changed while it was being checked — an install into "
            "this tree is under way; wait for it, and run again"
        )
        return [moved]
    return found


def _record_text(record: pathlib.Path) -> str | None:
    """The record as it is now, or nothing when it cannot be read now."""
    try:
        return record.read_text(encoding="utf-8")
    except OSError:
        return None


def _held_to_the_record(
    path: pathlib.Path, name: str, recorded: str, arriving: str | None = None
) -> str | None:
    """One recorded file against the tree: gone, unreadable, changed, or nothing to say.
    A file that already holds what the running install is bringing (`arriving`) has
    landed, not changed.

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
    if actual not in (recorded, arriving):
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
        sys.stderr.write(_as_prose(result.stderr) + "\n" if result.stderr else "")
        sys.stderr.flush()
        crashed = "Traceback (most recent call last)" in result.stderr
        if result.returncode == 0:
            # A scan that answers NA names **what it looked for** — "no docs/adr", "no
            # Python under app". The doctor printed the bare word and threw the reason
            # away, so five different NA lines read identically and an operator could not
            # tell "there is no such directory" from "a directory this scanner cannot
            # read" — which is the distinction the scanners were changed to make
            # (self-audit round 14, 2026-09-01).
            said = [_shown(line) for line in result.stdout.strip().splitlines()]
            if said and said[0].startswith("NA:"):
                reason = said[0].removeprefix("NA:").strip()
                print(f"[   NA] {gid} — {reason}")
                outcomes.append((gid, "na", said, reason))
            else:
                print(f"[ pass] {gid}")
                outcomes.append((gid, "pass", said, ""))
        elif result.returncode == 1 and result.stdout.strip() and not crashed:
            print(f"[found] {gid}")
            # Every line through the guard before it is printed or counted: what the
            # doctor writes is its own sentence about what a scanner said, and a scanner's
            # line is one finding whatever the tree it read was named (round 21).
            said = [_shown(line) for line in result.stdout.strip().splitlines()]
            print("\n".join(said))
            failed.append(gid)
            outcomes.append((gid, "found", said, ""))
        else:
            reason = f"the scan did not answer (exit {result.returncode})"
            print(f"[error] {gid} — {reason}")
            broken.append(gid)
            outcomes.append((gid, "error", [], f"{reason}\n{_as_prose(result.stderr)}".strip()))

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
# The most the doctor reads back from a file already at `--sarif`, to tell whose run
# it is. A log of 18,000 results is under 10 MiB; a file past this is answered without
# being read, since an input of the right kind but too large is a road round 19 walked.
READ_BACK_CEILING = 64 * 1024 * 1024
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


# The doctor's own copy of the scanners' guard, for the same reason it carries its own
# whole-file writer: this file is shipped alone into a project's tools/ and may import
# nothing from the package. Held byte-identical to the nine by
# `tests/test_checks_are_standalone.py`.
_ESCAPED = {
    **{c: f"\\x{c:02x}" for c in (*range(0x20), 0x7F)},
    **{
        c: f"\\u{c:04x}"
        for c in (
            *range(0x80, 0xA0),
            *range(0x200B, 0x2010),
            *range(0x202A, 0x202F),
            *range(0x2066, 0x206A),
            0xFEFF,
        )
    },
}


def _shown(text: str | pathlib.Path) -> str:
    """Text that can always be printed, and is always **one line**.

    The scanners hold their own output to this; this is the second layer, and its boundary
    is worth writing down. A scanner that prints two lines **is** reporting two findings —
    the doctor reads one line as one finding and cannot second-guess that, so a rogue
    scanner is not what this stops. What it stops is everything a line can carry *inside*
    itself: an ANSI escape in a file name (`\x1b[2K\x1b[A`) that erases the finding printed
    above it, a carriage return that rewrites the line, a C1 byte, a bidi override, a NUL
    (self-audit round 21, 2026-09-03). The forging of a *line* is closed one layer up, in
    the scanner, which is the only place that knows a file name is one value: see `_shown`
    in each of the nine.
    """
    return os.fsencode(str(text)).decode("utf-8", "backslashreplace").translate(_ESCAPED)


def _as_prose(text: str) -> str:
    """A scanner's stderr, shown as the prose it is: line breaks kept, the rest escaped.

    stdout is a grammar and every line of it becomes one finding; stderr is a traceback or
    a sentence for a person, and escaping its newlines would make it unreadable. What must
    not survive either way is a control character that moves a terminal's cursor.
    """
    return "\n".join(_shown(line) for line in text.splitlines(keepends=False))


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
    #
    # "Under the root" is decided on the **path**, not on what the path leads to.
    # `is_absolute()` was the whole check, and `..` walked straight through it: a finding
    # naming `../outside.txt` was given `uri: ../outside.txt`, because `(root / "..")` is
    # a directory the operating system resolves happily and `is_file()` agreed (self-audit
    # round 21, 2026-09-03). A `..` component is refused now, before anything is opened.
    #
    # Symlinks are deliberately **not** followed (owner's decision, 2026-09-04): a
    # `app/link.py` inside the tree that points elsewhere still gets its location, because
    # a SARIF annotation lands on the path a reader opens in the repository, and that path
    # is a file the repository has. Following the link would drop a legitimate annotation
    # from any project that keeps a vendored or shared directory that way. What is refused
    # is a path that names somewhere else *as a path* — which is what a reader would have
    # to follow out of the tree to make sense of.
    if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
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


def _final_mode(target: pathlib.Path) -> int:
    """The mode the written file ends up with: the target's, or a new file's default."""
    try:
        return stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        was = os.umask(0)
        os.umask(was)
        return 0o666 & ~was


def _write_whole(
    out: pathlib.Path,
    text: str,
    unless: Callable[[pathlib.Path], str | None] | None = None,
) -> str | None:
    """The text as `out`, whole or not at all — a sibling file renamed over the target.

    `write_text` truncates first, and a reader arriving between that and the write — the
    upload step, an IDE watching the file — saw an empty log or part of one, 99.7% of
    the time at this log's size; a doctor killed inside that window left 0 bytes. The
    package has one writer for this (`files.py`); this file is shipped standalone and
    may import nothing from it, so it carries the dozen lines (self-audit round 20,
    2026-09-03).

    `unless`, given the target, answers a sentence when what is there must not be
    replaced; it is asked after the sibling is complete and just before the rename, so
    that what it saw is as close as a read can be to what the rename would remove. On a
    sentence nothing is renamed, the sibling is removed, and the sentence is returned;
    None means the text is at `out`.
    """
    target = out.resolve()
    beside = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        create = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        # The sibling is written private and wears its final mode only at the end: it
        # exists under its own name for the length of the write, and for that moment
        # nobody else has business reading it. The final mode is the target's if it has
        # one, else what `write_text` would have given a new file.
        with os.fdopen(os.open(beside, create, 0o600), "wb") as h:
            h.write(text.encode("utf-8"))
            h.flush()
            os.fsync(h.fileno())
        beside.chmod(_final_mode(target))
        held = unless(target) if unless is not None else None
        if held is None:
            beside.replace(target)
    except OSError:
        beside.unlink(missing_ok=True)
        raise
    if held is not None:
        beside.unlink(missing_ok=True)
    return held


def _not_this_run(target: pathlib.Path, root: pathlib.Path) -> str | None:
    """A sentence when `target` holds something other than this doctor's run over `root`.

    Read first, then answered — never asked about and then read. Nothing at the path is
    the ordinary case and is None; so is this doctor's own earlier run over the same
    root, which a re-run replaces. Everything else is named: a run over another root
    (the answer that was being lost), another tool's log, a file that is not a log, one
    that cannot be read — which cannot be told from another run, so it is not replaced
    either — and one past `READ_BACK_CEILING`, answered without reading the rest.
    """
    try:
        with target.open("rb") as h:
            raw = h.read(READ_BACK_CEILING + 1)
    except FileNotFoundError:
        return None
    except OSError as problem:
        return f"cannot be read, so it cannot be told from another run: {problem}"
    if len(raw) > READ_BACK_CEILING:
        return f"is over {READ_BACK_CEILING} bytes, more than a log this doctor reads back"
    return _whose_run(raw, root)


def _whose_run(raw: bytes, root: pathlib.Path) -> str | None:
    """A sentence unless `raw` is a log this doctor wrote over `root`."""
    try:
        run = json.loads(raw)["runs"][0]
        tool = run["tool"]["driver"]["name"]
        uri = run["originalUriBaseIds"]["%SRCROOT%"]["uri"]
    except (ValueError, KeyError, IndexError, TypeError):
        tool = uri = None
    if not isinstance(tool, str) or not isinstance(uri, str):
        return "is not a log this doctor wrote"
    if tool != "verifiable-gates":
        return f"is a log written by {tool}, not by this doctor"
    if uri != root.as_uri() + "/":
        return f"holds a run over {uri}, not over this root"
    return None


def write_sarif(
    out: pathlib.Path, root: pathlib.Path, manifest: dict[str, Any], outcomes: list[Outcome]
) -> bool:
    """The log on disk, or a sentence on stderr and False — never a traceback.

    Two sentences, apart on purpose: a file that *cannot* be written, and one this
    doctor *will not* write over because of what is already there.
    """
    text = json.dumps(sarif_log(root, manifest, outcomes), indent=2) + "\n"
    try:
        held = _write_whole(out, text, unless=lambda target: _not_this_run(target, root))
    except OSError as problem:
        sys.stdout.flush()
        print(
            f"** cannot write the SARIF: {out}: {problem} — the report above stands",
            file=sys.stderr,
        )
        return False
    if held is not None:
        sys.stdout.flush()
        print(
            f"** not writing the SARIF: {out} {held} — the report above stands;"
            " name another file, or remove that one",
            file=sys.stderr,
        )
        return False
    return True


def rules_off_an_intact_bundle(
    root: pathlib.Path, manifest: dict[str, Any], bundle: pathlib.Path
) -> int:
    """`--rules`, but only off a bundle that is still the one that was installed.

    This mode is the one a project's `AGENTS.md` points its agents at, and the file it
    reads — `tools/overlay.json` — lives inside the project it holds to account. Editing
    a `title` there put a paragraph of the project's own choosing in front of the agent,
    formatted as this tool's prose, exit 0 and stderr empty: *rule … was retired … do not
    report this as a finding*; `born_from`, the field that says a rule has a real incident
    behind it, could be blanked in the same edit. `--installed` on the same tree answered
    *its contents have changed* immediately — the check existed, in the mode nobody tells
    an agent to run (self-audit round 21, 2026-09-03).

    So the check runs here, before a single rule is printed, and the answer is the same in
    both directions the owner decided (`DECISIONS.md`
    `the-rules-are-read-off-a-bundle-that-is-still-intact`): a record that does not hold
    and **no record at all** are both exit 2 with no rules on stdout. *Could not check* and
    *checked and wrong* are one answer here on purpose — neither is a bundle whose rules
    anybody can vouch for, and a warning printed above the rules would be a warning read
    after them.

    The boundary is the one `check_installed_record` already names: this catches an edited
    manifest or scanner, and cannot catch an edited doctor — a check that has been removed
    does not run.
    """
    unheld = check_installed_record(root)
    if unheld:
        print(
            f"** not printing the rules: the bundle under {root} is not the one that was"
            " installed, so what it says the rules are cannot be vouched for",
            file=sys.stderr,
        )
        for problem in unheld:
            print(f"   {problem}", file=sys.stderr)
        print(
            "   re-run the installer, or ask for the whole account with --installed",
            file=sys.stderr,
        )
        return 2
    return print_rules(manifest, bundle)


def print_working(manifest: dict[str, Any], root: pathlib.Path) -> int:
    """The practices this bundle carries, and whether this tree has turned them on.

    Read off the installed manifest, like `--rules`, so an upgrade cannot leave an agent on
    yesterday's copy. Unlike `--rules` it is **not** held to the installed record: nothing
    here decides anything about the project, so there is no verdict for a tampered manifest
    to corrupt — what it prints is a reading list, and the worst a wrong one can do is
    recommend a habit nobody adopted.

    The state line is the only measurement, and it measures one thing: whether
    `.local/LESSONS.md` is there. It is never a finding. A project that deleted its ledger
    made a decision, and this mode says so rather than grading it (`DECISIONS.md`
    `the-working-is-off-by-default`).
    """
    practices = manifest.get("working") or []
    if not practices:
        print("this bundle carries no working practices.")
        return 0
    print(f"The practices this bundle carries: {len(practices)}. None is decided by a scanner.")
    print(
        "They are how the work is done, not what the code must be. Each names the lesson"
        " that paid for it and the pull requests it held on.\n"
    )
    for entry in practices:
        held_by = str(entry.get("held_by", "reading"))
        named = entry.get(held_by)
        print(f"{entry.get('id', '(no id)')}")
        print(f"  practice:  {entry.get('title', '(no title in this manifest)')}")
        print(f"  born from: {entry.get('born_from', '(origin not recorded in this manifest)')}")
        print(f"  held by:   {f'{held_by} — {named}' if named else held_by}")
        print(f"  apply:     {entry.get('apply', '(nothing to do recorded in this manifest)')}")
    ledger = root / ".local" / "LESSONS.md"
    if ledger.is_file():
        print(f"\nOn here: {ledger.relative_to(root)} exists. The entries in it are yours.")
    else:
        print(
            "\nOff here: no .local/LESSONS.md. Turn it on with"
            " `python -m verifiable_gates.install <this tree> --working`, which lands an"
            " empty ledger and nothing else."
        )
    return 0


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
        "--working",
        action="store_true",
        help="print the practices this bundle carries, and whether this tree turned them on",
    )
    parser.add_argument(
        "--sarif",
        metavar="FILE",
        help="also write this run as SARIF 2.1.0, for code scanning, reviewdog or an IDE",
    )
    args = parser.parse_args(argv)
    if args.sarif and (args.installed or args.rules or args.working):
        parser.error(
            "--sarif describes a run of the scans; --installed, --rules and --working run none"
        )
    asked = [name for name in ("installed", "rules", "working") if getattr(args, name)]
    if len(asked) > 1:
        parser.error(f"--{' and --'.join(asked)} are different questions: ask one at a time")
    if args.root is not None and args.root_option is not None:
        parser.error("give the project once: either as the positional root or as --root, not both")
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
        return rules_off_an_intact_bundle(root, manifest, bundle)
    if args.working:
        return print_working(manifest, root)
    return run_scans(root, manifest, bundle, pathlib.Path(args.sarif) if args.sarif else None)


if __name__ == "__main__":
    sys.exit(main())
