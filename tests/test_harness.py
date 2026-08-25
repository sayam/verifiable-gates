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

import json
from typing import TYPE_CHECKING, Any

from verifiable_gates import harness

if TYPE_CHECKING:
    import pathlib

    import pytest

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
    assert [r["round"] for r in records] == [1, 2]
    assert records[1]["failed"] == ["a-rule"]


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
    assert run(root, "--output", str(report)) == 0
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
