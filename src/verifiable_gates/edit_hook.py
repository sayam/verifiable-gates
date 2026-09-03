"""The gates a project installed, fed back to the agent that just edited a file.

**This file runs as a hook, so it is standalone on purpose**: stdlib only, no import
from the package around it. Claude Code runs it as
`python3 "${CLAUDE_PLUGIN_ROOT}/src/verifiable_gates/edit_hook.py"` after every `Edit`
or `Write` (`hooks/hooks.json`), under whatever `python3` the user has, in a project
that may have installed nothing of this package but the bundle under `tools/`.

It is the third front door, after `action.yml` and `.pre-commit-hooks.yaml`, and it
carries no bundle either: it runs `tools/gates_doctor.py` **as the project has it**, so
the plugin updating changes nothing about what the project is held to
(`DECISIONS.md` `ci-runs-the-bundle-the-project-installed`). What it adds is *when*:
CI and a commit hook answer after the work; this answers after the edit, while the
agent that made it is still holding the file.

**Off by default, on by one switch.** `VERIFIABLE_GATES_AT_EDIT=1` in the environment —
a project sets it in its `.claude/settings.json` under `env`, where the team can see it —
turns it on; unset or `0` is off and silent. Any other value is a misuse said out loud
(exit 2), because a switch that reads `yes` as *off* would leave somebody believing
their edits were checked when nothing looked (the shape of self-audit round 18:
a configuration that is not a configuration is never a silent default).

**It reports; it does not refuse.** The hook fires after the edit has landed
(`PostToolUse`), runs the doctor over the tree as it now is, and when the doctor
found something — or could not answer, which is red too — exits 2 with the report on
stderr, which Claude Code hands back to the agent as feedback. A `PreToolUse` hook
would have to judge a file that does not exist yet, from its own copy of what `Edit`
is about to do: a check on one state and an act on another, the shape round 20 spent
eight findings closing (`DECISIONS.md` `the-edit-hook-reports-and-does-not-refuse`).

Three ways of answering nothing, kept apart: the switch is off (silent, nothing
claimed); the edited file lies outside the project (silent — it cannot have moved the
project's verdict); the doctor answered clean (silent, and that silence *is* a claim,
made by the doctor).

**Two voices, never confused.** What the doctor said is relayed as the doctor's, under a
line naming it and its exit code, and the report is capped at `REASON_CEILING` bytes with
a sentence saying how much was cut and how to read the rest — a reason of megabytes is
round 19's shape in the agent's own context. What this hook has to say for itself — no
bundle under the root, a doctor nobody can open, one that did not answer in time or could
not be started, stdin that is not a hook event, an argument on the command line — is a
sentence of its own, with no exit code borrowed from a reader that never ran.

exit 0 = nothing to say · 2 = the report, or a sentence about why there is none

Role: reader — it relays what the project's own doctor said about the tree after an
edit. The doctor's exit code is the verdict; this file decides nothing of its own.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

SWITCH = "VERIFIABLE_GATES_AT_EDIT"
DOCTOR = pathlib.Path("tools") / "gates_doctor.py"
# The doctor's report, as fed back to the agent. A finding is a line; a run over a
# project with real problems is a few dozen; anything past this is cut with a sentence.
REASON_CEILING = 16 * 1024
# Above the doctor's own per-scan timeout summed over nine scans would be honest; a hook
# holding the agent for minutes is not. The doctor times each scan out on its own.
DOCTOR_TIMEOUT = 120.0
INSTALLER = "python -m verifiable_gates.install"


def switched(environ: Mapping[str, str]) -> bool | str:
    """True on, False off, or the sentence for a value that is neither."""
    value = environ.get(SWITCH, "0")
    if value in {"", "0"}:
        return False
    if value == "1":
        return True
    return f"{SWITCH}={value!r} is neither 1 nor 0 — nothing was checked"


def read_event(stream: IO[str]) -> dict[str, Any] | str:
    """The hook event Claude Code writes on stdin, or the sentence for something else."""
    try:
        raw = json.loads(stream.read())
    except (OSError, ValueError) as problem:
        return f"stdin is not a hook event: {problem} — nothing was checked"
    if not isinstance(raw, dict):
        return "stdin is not a hook event: not a JSON object — nothing was checked"
    return raw


def project_root(event: Mapping[str, Any], environ: Mapping[str, str]) -> pathlib.Path | str:
    """Where the project is: Claude Code's variable first, the event's `cwd` second."""
    named = environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd")
    if not isinstance(named, str) or not named:
        return (
            "neither CLAUDE_PROJECT_DIR nor the event's cwd names the project — nothing was checked"
        )
    return pathlib.Path(named).resolve()


def edited_inside(event: Mapping[str, Any], root: pathlib.Path) -> bool:
    """Whether the edit could have moved this project's verdict.

    A path the event does not carry is taken as inside — the tree may have changed and
    the doctor is the one to say. A path it does carry that resolves outside the root
    cannot have, and is left alone.
    """
    tool_input = event.get("tool_input")
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(path, str) or not path:
        return True
    where = pathlib.Path(path)
    if not where.is_absolute():
        where = root / where
    return where.resolve().is_relative_to(root)


def _cut(text: str, ceiling: int) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= ceiling:
        return text
    kept = raw[:ceiling].decode("utf-8", errors="ignore")
    return (
        f"{kept}\n… {len(raw) - ceiling} more bytes not shown — run"
        f" python3 {DOCTOR.as_posix()} --root . to read the whole report\n"
    )


def consult(root: pathlib.Path, timeout: float = DOCTOR_TIMEOUT) -> tuple[int, str] | str:
    """The doctor's exit code and what it said — or a sentence of this hook's own.

    The two are different kinds of answer and the caller keeps them apart: a tuple is
    the doctor speaking, and only that is relayed as *the doctor says*; a string is this
    hook explaining why there is no verdict to relay — no doctor to run, one nobody can
    open, one that did not answer in time, one that could not be started. Attributing
    those to the doctor would quote a reader that never ran (found by the coverage floor
    on the road that opens an unreadable doctor, 2026-09-03).
    """
    doctor = root / DOCTOR
    # The interpreter is the one that opens the doctor, and a file it cannot open is its
    # own two-line message and exit 2 — honest, but not the sentence that says what to
    # do. So the file is opened here first and the exception answered; a doctor removed
    # between this and the run below is still exit 2 with the interpreter's own words.
    try:
        with doctor.open("rb"):
            pass
    except FileNotFoundError:
        return (
            f"no bundle installed under {root} — this hook runs the doctor a project"
            f" installed ({INSTALLER}); it carries no copy of its own. Set {SWITCH}=0 to"
            " turn the hook off for a project that has not installed one."
        )
    except OSError as problem:
        return f"{DOCTOR.as_posix()} could not be run: {problem} — nothing was decided"
    try:
        done = subprocess.run(  # noqa: S603 — argv is built here; the interpreter is our own
            [sys.executable, str(doctor), "--root", str(root)],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"{DOCTOR.as_posix()} did not answer within {timeout:g}s — nothing was decided"
    except OSError as problem:
        return f"{DOCTOR.as_posix()} could not be run: {problem} — nothing was decided"
    said = done.stdout + ("\n" if done.stdout and done.stderr else "") + done.stderr
    return done.returncode, said


def _say(stderr: IO[str], sentence: str) -> int:
    stderr.write(f"verifiable-gates: {sentence}\n")
    return 2


def _prepare(stdin: IO[str], environ: Mapping[str, str]) -> tuple[pathlib.Path, str] | str | None:
    """The root and the edited path when there is a doctor to consult.

    None when there is nothing to run and nothing to say — the switch is off, or the
    edit lies outside the project. A sentence when there is something to say instead.
    """
    on = switched(environ)
    if on is False:
        return None
    if isinstance(on, str):
        return on
    event = read_event(stdin)
    if isinstance(event, str):
        return event
    root = project_root(event, environ)
    if isinstance(root, str):
        return root
    if not edited_inside(event, root):
        return None
    tool_input = event.get("tool_input")
    edited = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    return root, (edited if isinstance(edited, str) and edited else "the tree")


def main(
    argv: list[str] | None = None,
    *,
    stdin: IO[str] = sys.stdin,
    stderr: IO[str] = sys.stderr,
    environ: Mapping[str, str] = os.environ,
) -> int:
    """The hook, as Claude Code runs it: the event on stdin, nothing on the command line."""
    if argv:
        return _say(stderr, "this is a hook — it reads the event on stdin and takes no arguments")
    prepared = _prepare(stdin, environ)
    if prepared is None:
        return 0
    if isinstance(prepared, str):
        return _say(stderr, prepared)
    root, edited = prepared
    answer = consult(root, DOCTOR_TIMEOUT)
    if isinstance(answer, str):
        return _say(stderr, answer)
    code, said = answer
    if code == 0:
        return 0
    stderr.write(
        f"verifiable-gates: after the edit to {edited}, {DOCTOR.as_posix()} (exit {code}) says:\n"
    )
    stderr.write(_cut(said, REASON_CEILING))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
