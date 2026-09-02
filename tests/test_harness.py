"""The harness answers in something a loop can act on, and never passes silently.

Its value is the shape of the answer: `(gate id, cause, hint)` is what lets an
agent fix the cause rather than the symptom. So the tests are about the answer —
that a failure names the gate, quotes enough of the output to locate it, and
carries the trap the rule came from.

**Skips are the part that has to be loud.** The harness runs gates of kind `test`
and cannot decide `job` or `step`, whose commands live in the workflow. Reporting
those as anything other than "skipped, because" would turn "nobody checked this"
into "this passed", which is the failure this whole project is organised against.
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

import pytest

from verifiable_gates import harness

PASSING = "def test_ok():\n    assert True\n"
FAILING = "def test_no():\n    assert 1 == 2, 'a distinctive message'\n"


def a_gate(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — field values are of mixed type
    base: dict[str, Any] = {
        "id": "a-rule",
        "title": "A rule",
        "kind": "test",
        "severity": "blocking",
        "enforced_by": {"job": "test", "tests": ["tests/test_thing.py"]},
        "layer": "internal",
        "pillar": "devx",
        "born_from": "the trap that produced it",
    }
    base.update(overrides)
    return base


def a_tree(root: pathlib.Path, body: str) -> pathlib.Path:
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "test_thing.py").write_text(body, encoding="utf-8")
    return root


# ---------------------------------------------------------------- one gate


def test_a_gate_that_hangs_is_a_red_answer_not_a_traceback(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`TimeoutExpired` used to escape; the loop can act on a cause, not on a traceback."""
    monkeypatch.setattr(harness, "GATE_TIMEOUT_SECONDS", 1)
    sleeping = "import time\n\ndef test_slow():\n    time.sleep(30)\n"

    result = harness.run_test_gate(a_gate(), a_tree(tmp_path, sleeping))

    assert result["status"] == "fail"
    assert "timed out after 1s" in result["cause"]


def test_a_passing_gate_reports_pass_and_a_duration(tmp_path: pathlib.Path) -> None:
    result = harness.run_test_gate(a_gate(), a_tree(tmp_path, PASSING))
    assert result["status"] == "pass"
    assert result["seconds"] >= 0


def test_a_failing_gate_quotes_enough_to_find_it(tmp_path: pathlib.Path) -> None:
    """A failure with no cause sends the loop back to read the whole log."""
    result = harness.run_test_gate(a_gate(), a_tree(tmp_path, FAILING))
    assert result["status"] == "fail"
    assert "a distinctive message" in result["cause"]


def test_the_cause_is_a_tail_not_the_whole_log(tmp_path: pathlib.Path) -> None:
    """A report that carries everything is a report nobody reads."""
    many = "".join(f"def test_no{n}():\n    assert False\n" for n in range(30))
    result = harness.run_test_gate(a_gate(), a_tree(tmp_path, many))
    assert len(result["cause"].splitlines()) <= harness.CAUSE_LINES


# ---------------------------------------------------------------- the walk


def test_a_gate_the_harness_cannot_decide_is_skipped_out_loud(tmp_path: pathlib.Path) -> None:
    gate = a_gate(kind="job", enforced_by={"job": "image"})
    results = harness.run_all([gate], tmp_path, set())
    assert results[0]["status"] == "skip"
    assert "enforced by CI job `image`" in results[0]["cause"]


def test_a_skip_names_what_it_would_have_needed(tmp_path: pathlib.Path) -> None:
    gate = a_gate(kind="job", enforced_by={"job": "image"}, requires=["docker"])
    assert "needs docker" in harness.run_all([gate], tmp_path, set())[0]["cause"]


def test_a_failure_carries_the_trap_the_rule_came_from(tmp_path: pathlib.Path) -> None:
    """Knowing what broke satisfies the letter; knowing what it protected fixes the cause."""
    results = harness.run_all([a_gate()], a_tree(tmp_path, FAILING), set())
    assert results[0]["hint"] == "the trap that produced it"


def test_a_pass_carries_no_hint(tmp_path: pathlib.Path) -> None:
    results = harness.run_all([a_gate()], a_tree(tmp_path, PASSING), set())
    assert "hint" not in results[0]


def test_only_selects_without_hiding_the_rest_from_the_registry(tmp_path: pathlib.Path) -> None:
    gates = [a_gate(), a_gate(id="other")]
    results = harness.run_all(gates, a_tree(tmp_path, PASSING), {"other"})
    assert [r["gate"] for r in results] == ["other"]


# ---------------------------------------------------------------- one round


REGISTRY = """version: 1
gates:
  - id: a-rule
    title: A rule
    kind: test
    severity: blocking
    enforced_by: {job: test, tests: [tests/test_thing.py]}
    layer: internal
    pillar: devx
    born_from: the trap that produced it
"""


def a_project(root: pathlib.Path, body: str) -> pathlib.Path:
    a_tree(root, body)
    (root / "gates.yaml").write_text(REGISTRY, encoding="utf-8")
    return root


def run(root: pathlib.Path, *extra: str) -> int:
    return harness.main(["--registry", str(root / "gates.yaml"), "--root", str(root), *extra])


def test_a_clean_round_returns_zero_and_counts_itself(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = a_project(tmp_path, PASSING)
    assert run(root) == 0
    assert "round 1: 1 pass · 0 fail · 0 skip" in capsys.readouterr().out


def test_rounds_accumulate_so_a_repeat_offender_is_visible(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Which gate keeps failing should be a fact, not an impression."""
    root = a_project(tmp_path, FAILING)
    assert run(root) == 1
    assert run(root) == 1
    capsys.readouterr()

    records = [
        json.loads(line)
        for line in (root / harness.ROUND_LOG).read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert records[1]["failed"] == ["a-rule"]
    # The number is the line's position and is never written into the line — a number
    # only ever read off the file cannot disagree with it (self-audit round 20).
    assert all("round" not in record for record in records)
    assert records[0]["token"] != records[1]["token"]


def test_a_failing_round_prints_the_gate_the_cause_and_the_hint(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(a_project(tmp_path, FAILING)) == 1
    output = capsys.readouterr().out
    assert "[FAIL] a-rule" in output
    assert "a distinctive message" in output
    assert "hint: the trap that produced it" in output


def test_the_full_report_can_be_written_for_a_machine(tmp_path: pathlib.Path) -> None:
    root = a_project(tmp_path, PASSING)
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    stale = report.stat().st_ino
    assert run(root, "--output", str(report)) == 0
    # Replaced whole, never rewritten in place: a loop reading the report while the
    # harness writes it saw an empty file (self-audit round 20, 2026-09-03).
    assert report.stat().st_ino != stale, "the report was rewritten in place"
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["round"] == 1
    assert written["results"][0]["gate"] == "a-rule"


def test_asking_for_a_gate_that_does_not_exist_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2, never 0 — a typo in a gate id must not read as "everything passed"."""
    root = a_project(tmp_path, PASSING)
    assert run(root, "--only", "no-such-gate") == 2
    assert "no such gate" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("registry", "why"),
    [
        ("version: 1\n", "no gates list"),
        ("version: 1\ngates:\n  - a stray string\n", "a row that is not a mapping"),
        ("version: 2\ngates: []\n", "a schema version this reader does not speak"),
    ],
    ids=lambda value: value if " " in str(value) else "registry",
)
def test_an_index_the_harness_cannot_read_is_a_misuse_not_a_pass(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], registry: str, why: str
) -> None:
    """Exit 2 with the reader's words — never 0, never a traceback."""
    root = a_project(tmp_path, PASSING)
    (root / "gates.yaml").write_text(registry, encoding="utf-8")
    assert run(root) == 2, why
    assert "cannot read the registry" in capsys.readouterr().err


def test_a_failure_without_a_recorded_trap_prints_no_hint(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty hint line would look like a rule that came from nowhere on purpose."""
    root = a_project(tmp_path, FAILING)
    registry = (root / "gates.yaml").read_text(encoding="utf-8")
    (root / "gates.yaml").write_text(
        registry.replace("    born_from: the trap that produced it\n", ""), encoding="utf-8"
    )

    assert run(root) == 1
    output = capsys.readouterr().out
    assert "[FAIL] a-rule" in output
    assert "hint:" not in output


def test_the_round_log_is_ignored_by_this_repository() -> None:
    """`ROUND_LOG` is per-machine notes — the module says it belongs in `.gitignore`.

    It did not, until an outside audit on 2026-08-29 watched the file appear in a
    tree the harness ran in. A comment that names a rule nothing checks is the
    kind of promise this project exists to replace.
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    ignored = (root / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert harness.ROUND_LOG in ignored


@pytest.mark.parametrize(
    "registry", ["a: [\n", "a: 1\n---\n- b\n"], ids=["unclosed-flow", "two-documents"]
)
def test_yaml_the_reader_rejects_is_a_misuse_not_a_traceback(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], registry: str
) -> None:
    """A registry PyYAML cannot parse died with a ScannerError and exit 1 (self-audit,
    2026-08-31); the harness says it cannot read it, exit 2."""
    root = a_project(tmp_path, PASSING)
    (root / "gates.yaml").write_text(registry, encoding="utf-8")
    assert run(root) == 2
    assert "cannot read the registry" in capsys.readouterr().err


def test_a_registry_that_is_not_there_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = a_project(tmp_path, PASSING)
    (root / "gates.yaml").unlink()
    assert run(root) == 2
    assert "cannot read the registry" in capsys.readouterr().err


SKIPPED = (
    "import pytest\n\npytestmark = pytest.mark.skip(reason='switched off')\n\n\n"
    "def test_ok():\n    assert True\n"
)


def test_a_gate_whose_tests_were_all_skipped_did_not_run(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """pytest exits 0 when every test it collected was skipped, so one line at the top of
    a claimed file turned a gate off and the harness called it `pass` — with the whole
    suite and the 100% coverage floor green beside it, because the lines those tests
    cover are reached by others (self-audit round 4, 2026-09-01)."""
    root = a_project(tmp_path, SKIPPED)

    assert run(root) == 1
    printed = capsys.readouterr().out
    assert "no test ran" in printed
    assert "0 pass · 1 fail" in printed


def test_a_file_with_no_test_in_it_is_still_a_fail(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The neighbouring shape, which already worked: pytest exits 5 for a file it
    collected nothing from, and that has always been a fail."""
    root = a_project(tmp_path, "# nothing here\n")

    assert run(root) == 1
    assert "1 fail" in capsys.readouterr().out


def test_notes_that_cannot_be_written_do_not_change_the_verdict(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A checkout mounted read-only ended the run with a raw `PermissionError` and exit 1
    *after every gate had passed* — a red that reads as a broken gate and sends the next
    person hunting for one (self-audit round 5, 2026-09-01)."""
    root = a_project(tmp_path, PASSING)
    (root / harness.ROUND_LOG).mkdir()

    assert run(root) == 0
    printed = capsys.readouterr()
    assert "could not write the round notes" in printed.err
    assert "round 0: 1 pass · 0 fail" in printed.out, "a round that was not noted is round 0"


def test_a_report_that_cannot_be_written_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unlike the notes, `--output` was asked for by name: not producing it is a call that
    could not be answered, which is exit 2 — not exit 1, which would say the gates failed."""
    root = a_project(tmp_path, PASSING)
    somewhere = tmp_path / "not-a-directory" / "report.json"

    assert run(root, "--output", str(somewhere)) == 2
    assert "cannot write the report" in capsys.readouterr().err


def test_notes_that_cannot_be_decoded_are_left_alone_and_do_not_change_the_verdict(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Round 5 gave the notes a guard for a file that cannot be *written*; a file that
    cannot be *decoded* went straight past it and ended a passing round with a raw
    `UnicodeDecodeError` and exit 1 (self-audit round 12, 2026-09-01). The notes are
    left exactly as they were — overwriting a file this reader could not read would
    destroy whatever it held — and the round is numbered 0, "not noted"."""
    root = a_project(tmp_path, PASSING)
    log = root / harness.ROUND_LOG
    log.write_bytes(b"notes somebody saved as cp1252: caf\xe9\n")

    assert run(root) == 0
    printed = capsys.readouterr()
    assert "could not read the round notes: not UTF-8" in printed.err
    assert "round 0: 1 pass · 0 fail" in printed.out
    assert log.read_bytes() == b"notes somebody saved as cp1252: caf\xe9\n"


# ------------------------------------------- two rounds noted at once
#
# The note was read-count-write: read the whole file, count the lines, write the whole
# file back. Two harnesses on one checkout both counted the same lines, both printed the
# same round number, and the second write threw the first one's note away — and a writer
# killed between the truncate and the write left the file at 0 bytes, in a file that is
# in `.gitignore` and so cannot be recovered (self-audit round 20, 2026-09-03). The note
# is now appended in one write and the number is read back off the file by the token
# the note carries: two rounds at once are two numbers, and neither is lost.

SEEDED = 300


def _seeded_notes(root: pathlib.Path, rounds: int) -> pathlib.Path:
    log = root / harness.ROUND_LOG
    log.write_text(
        "".join(
            json.dumps({"token": f"{n:016x}", "counts": {}, "failed": []}) + "\n"
            for n in range(rounds)
        ),
        encoding="utf-8",
    )
    return log


def test_two_rounds_noted_at_once_are_two_numbers_and_neither_is_lost(
    tmp_path: pathlib.Path,
) -> None:
    """Two real processes, one checkout, as two agents or two terminals would do it."""
    root = a_project(tmp_path, PASSING)
    log = _seeded_notes(root, SEEDED)
    command = [
        sys.executable,
        "-m",
        "verifiable_gates.harness",
        "--registry",
        str(root / "gates.yaml"),
        "--root",
        str(root),
    ]
    runs = [
        subprocess.Popen(command, stdout=subprocess.PIPE, text=True)  # noqa: S603 — argv built here
        for _ in range(2)
    ]
    said = [run.communicate()[0].strip().splitlines()[-1] for run in runs]

    assert [run.returncode for run in runs] == [0, 0]
    numbers = sorted(int(line.removeprefix("round ").split(":")[0]) for line in said)
    assert numbers == [SEEDED + 1, SEEDED + 2], said
    assert len(log.read_text(encoding="utf-8").splitlines()) == SEEDED + 2


def test_a_note_that_lands_in_the_gap_is_kept_and_counted(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The interleaving, made deterministic: another harness's note lands after this one
    has looked at the file and before it writes. Counted ahead, this round would be
    numbered as if that note were not there; rewritten whole, that note would be gone."""
    root = a_project(tmp_path, PASSING)
    log = _seeded_notes(root, SEEDED)
    foreign = json.dumps({"token": "another-harness", "counts": {}, "failed": []})

    def another_harness_writes_first(log_path: pathlib.Path) -> bool:
        with log_path.open("a", encoding="utf-8") as notes:
            notes.write(foreign + "\n")
        return True

    monkeypatch.setattr(harness, "_notes_can_be_read", another_harness_writes_first)

    assert run(root) == 0
    assert f"round {SEEDED + 2}: 1 pass" in capsys.readouterr().out
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == SEEDED + 2
    assert lines[SEEDED] == foreign, "the note that landed in the gap was thrown away"


def test_the_round_number_is_the_notes_own_line_not_the_count_after_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Read back after the append, the file may already hold a later note; the number is
    where *this* note is, and a note that cannot be found is round 0 with a sentence."""
    log = _seeded_notes(tmp_path, 3)
    mine = json.loads(log.read_text(encoding="utf-8").splitlines()[1])
    note = json.dumps(mine)

    position_of = harness._position_of  # noqa: SLF001 — the read-back is the subject

    assert position_of(log, note) == 2
    assert position_of(log, "not in the notes") == 0
    assert "could not find this round in the notes" in capsys.readouterr().err
    log.unlink()
    assert position_of(log, note) == 0
    assert "could not read the round notes back" in capsys.readouterr().err


def test_a_note_is_written_without_reading_the_notes_first(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Append-only means the write depends on nothing read: notes that can be written
    and not read back still get this round's note, and the round is 0 with a sentence,
    because a number nobody could read off the file is not a number."""
    root = a_project(tmp_path, PASSING)
    log = _seeded_notes(root, 3)
    log.chmod(0o222)
    try:
        code = run(root)
    finally:
        log.chmod(0o644)

    assert code == 0
    printed = capsys.readouterr()
    assert "round 0: 1 pass" in printed.out
    assert "could not read the round notes back" in printed.err
    assert len(log.read_text(encoding="utf-8").splitlines()) == 4, "the note was not appended"


# ------------------------------------------- what the harness says, in what bytes
#
# The harness prints two things it did not write — the `hint`, which is the registry's
# prose, and its own summary's `·` — and writes two files nobody asked it to encode. All
# four went out in the **machine's** locale, while every reader in this package insists
# on UTF-8. On a machine whose stdout is not UTF-8 a round in which every gate was
# skipped and nothing failed printed nothing at all, ended in `UnicodeEncodeError` and
# exited **1** (self-audit round 15, 2026-09-01).

PROSE = "the trap that produced it — an em dash, as the registry's prose is full of"
WITH_PROSE = REGISTRY.replace("born_from: the trap that produced it", f"born_from: {PROSE}")


def an_ascii_terminal(monkeypatch: pytest.MonkeyPatch) -> io.BytesIO:
    """Replace stdout with one that can encode ASCII and nothing else, and return its bytes."""
    raw = io.BytesIO()
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(raw, encoding="ascii", write_through=True))
    return raw


def test_a_green_round_is_still_green_on_a_terminal_that_is_not_utf8(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `·` in the harness's own summary line must not be able to fail the run."""
    root = a_project(tmp_path, PASSING)
    said = an_ascii_terminal(monkeypatch)

    assert run(root) == 0, "a round with nothing wrong was failed by the act of reporting it"
    assert b"1 pass \\xb7 0 fail" in said.getvalue(), said.getvalue()


def test_a_hint_the_terminal_cannot_show_is_shown_escaped(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hint is the registry's prose, and prose is not ASCII — but it is still a hint."""
    root = a_tree(tmp_path, FAILING)
    (root / "gates.yaml").write_text(WITH_PROSE, encoding="utf-8")
    said = an_ascii_terminal(monkeypatch)

    assert run(root) == 1
    written = said.getvalue()
    assert b"hint: the trap that produced it" in written
    assert b"\\u2014" in written or b"\\x" in written, written


def test_the_report_is_utf8_whatever_the_machine_reads_by_default(tmp_path: pathlib.Path) -> None:
    """The report is written for another machine, and read back with `encoding="utf-8"`.

    Run for real in a subprocess, because the encoding `write_text` picks with no
    `encoding=` is the interpreter's at startup and cannot be changed from inside the
    test. `PYTHONUTF8=0` with the C locale is one machine where they differ; a Windows
    default (cp1252) is another, and there the file is written and silently misread
    rather than refused.
    """
    root = a_tree(tmp_path, FAILING)
    (root / "gates.yaml").write_text(WITH_PROSE, encoding="utf-8")
    report = tmp_path / "report.json"

    done = subprocess.run(  # noqa: S603 — sys.executable and paths this test just wrote
        [
            sys.executable,
            "-m",
            "verifiable_gates.harness",
            "--registry",
            str(root / "gates.yaml"),
            "--root",
            str(root),
            "--output",
            str(report),
        ],
        env={**os.environ, "PYTHONUTF8": "0", "LC_ALL": "C"},
        capture_output=True,
        check=False,
        timeout=300,
    )

    assert done.returncode == 1, f"the gate failed, so the run is 1: {done.stderr.decode()[-400:]}"
    written = json.loads(report.read_text(encoding="utf-8"))
    assert "—" in written["results"][0]["hint"], "the registry's prose did not survive the trip"
