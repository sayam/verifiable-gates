"""Rendering is a pure function of a registry and a preamble.

The rule sheet exists so that nobody writes the rules down twice. That only holds
while the sheet is **generated** — which means the render has to be
byte-deterministic, so a project can hold its committed file against a fresh one
and see a difference rather than trust that there is none.

Two things are inputs here that were constants in the reference implementation,
and each has a test saying why it matters: the **registry**, so one renderer
serves any project, and the **preamble**, because the opening of a rule sheet is
prose a project writes about itself. Baking one project's paragraphs into the tool
would make every other project ship that project's story.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from verifiable_gates import skill

if TYPE_CHECKING:
    import pathlib

PREAMBLE = "# Rules\n\nSome opening prose.\n"


def a_gate(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — field values are of mixed type
    base: dict[str, Any] = {
        "id": "a-rule",
        "title": "A rule that holds",
        "kind": "test",
        "severity": "blocking",
        "enforced_by": {"job": "test", "tests": ["tests/test_a.py"]},
        "layer": "baseline",
        "pillar": "security",
        "portable": True,
        "born_from": "the trap that produced it",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- selection


def test_only_exportable_gates_are_rendered() -> None:
    """A rule this project keeps to itself is not a rule it hands anyone else."""
    gates = [a_gate(), a_gate(id="ours-only", portable=False)]
    assert [g["id"] for g in skill.portable_gates(gates)] == ["a-rule"]


def test_a_layer_can_be_asked_for() -> None:
    gates = [a_gate(), a_gate(id="business-rule", layer="business")]
    assert [g["id"] for g in skill.portable_gates(gates, "business")] == ["business-rule"]


def test_the_order_of_the_registry_is_kept() -> None:
    """A registry is written to be read; the neighbours of a rule are part of its meaning."""
    gates = [a_gate(id="zeta"), a_gate(id="alpha"), a_gate(id="mid")]
    assert [g["id"] for g in skill.portable_gates(gates)] == ["zeta", "alpha", "mid"]


# ---------------------------------------------------------------- rendering


def test_a_rendered_rule_carries_all_three_parts() -> None:
    out = skill.render([a_gate()], PREAMBLE)
    assert "### `a-rule`" in out
    assert "**Rule:** A rule that holds" in out
    assert "**Born from:** the trap that produced it" in out
    assert "**Enforced in the reference:** `tests/test_a.py`" in out


def test_the_preamble_comes_from_the_caller() -> None:
    """Otherwise every project that uses this tool ships this project's story."""
    assert skill.render([], "# Mine\n").startswith("# Mine\n")


def test_the_field_headings_can_be_in_another_language() -> None:
    """The reference implementation writes its sheets in a language that is not English.

    A renderer with English headings baked in would force one language on every
    project, which is the same mistake as baking in the preamble. The example uses
    non-ASCII headings, since those are the ones likely to break.
    """
    out = skill.render([a_gate()], PREAMBLE, labels=("Règle", "Origine", "Appliquée par"))
    assert "**Règle:** A rule that holds" in out
    assert "**Rule:**" not in out


def test_whitespace_in_born_from_is_collapsed() -> None:
    """`born_from` is written as a wrapped block; a sheet wants one paragraph."""
    out = skill.render([a_gate(born_from="a lesson\n   spread over\n   lines")], PREAMBLE)
    assert "**Born from:** a lesson spread over lines" in out


@pytest.mark.parametrize(
    ("gate", "expected"),
    [
        (
            a_gate(kind="test", enforced_by={"job": "t", "tests": ["a.py", "b.py"]}),
            "`a.py` · `b.py`",
        ),
        (
            a_gate(kind="step", enforced_by={"job": "scans", "step": "the step"}),
            'job `scans` step "the step"',
        ),
        (a_gate(kind="job", enforced_by={"job": "scans"}), "job `scans`"),
    ],
    ids=["test", "step", "job"],
)
def test_each_kind_points_at_what_enforces_it(gate: dict[str, Any], expected: str) -> None:
    """Point at the enforcer rather than restating its command — no second copy."""
    assert expected in skill.render([gate], PREAMBLE)


def test_the_same_inputs_render_the_same_bytes() -> None:
    """Without this, "regenerate and compare" proves nothing."""
    gates = [a_gate(), a_gate(id="second")]
    assert skill.render(gates, PREAMBLE) == skill.render(gates, PREAMBLE)


# ---------------------------------------------------------------- the command line


def a_project(root: pathlib.Path, registry_text: str) -> tuple[pathlib.Path, pathlib.Path]:
    (root / "gates.yaml").write_text(registry_text, encoding="utf-8")
    (root / "preamble.md").write_text(PREAMBLE, encoding="utf-8")
    return root / "gates.yaml", root / "preamble.md"


REGISTRY = """version: 1
gates:
  - id: a-rule
    title: A rule that holds
    kind: test
    severity: blocking
    enforced_by: {job: test, tests: [tests/test_a.py]}
    layer: baseline
    pillar: security
    portable: true
    born_from: the trap that produced it
"""


def test_writing_and_then_checking_agree(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, preamble = a_project(tmp_path, REGISTRY)
    out = tmp_path / "SKILL.md"
    args = ["--registry", str(registry), "--preamble", str(preamble), "--out", str(out)]

    assert skill.main(args) == 0
    assert "rewrote" in capsys.readouterr().out
    assert skill.main([*args, "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_a_second_write_reports_nothing_changed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, preamble = a_project(tmp_path, REGISTRY)
    out = tmp_path / "SKILL.md"
    args = ["--registry", str(registry), "--preamble", str(preamble), "--out", str(out)]
    assert skill.main(args) == 0
    capsys.readouterr()
    assert skill.main(args) == 0
    assert "unchanged" in capsys.readouterr().out


def test_check_fails_when_the_committed_file_drifted(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point of committing a generated file is that drift becomes visible."""
    registry, preamble = a_project(tmp_path, REGISTRY)
    out = tmp_path / "SKILL.md"
    out.write_text("edited by hand\n", encoding="utf-8")

    args = ["--registry", str(registry), "--preamble", str(preamble), "--out", str(out), "--check"]
    assert skill.main(args) == 1
    assert "differs from a fresh render" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "edited by hand\n", "--check must not write"


def test_check_fails_when_the_file_is_absent(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, preamble = a_project(tmp_path, REGISTRY)
    args = [
        "--registry",
        str(registry),
        "--preamble",
        str(preamble),
        "--out",
        str(tmp_path / "gone.md"),
        "--check",
    ]
    assert skill.main(args) == 1
    assert "differs" in capsys.readouterr().err


def test_a_broken_registry_stops_the_render(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rendering from a registry nobody validated would publish its mistakes."""
    registry, preamble = a_project(tmp_path, "version: 1\ngates:\n  - id: Bad_Id\n")
    out = tmp_path / "SKILL.md"
    args = ["--registry", str(registry), "--preamble", str(preamble), "--out", str(out)]

    assert skill.main(args) == 2
    assert "registry:" in capsys.readouterr().err
    assert not out.exists(), "nothing should be written from a registry that did not pass"


def test_labels_must_come_in_threes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two headings would silently drop a field from every rule."""
    registry, preamble = a_project(tmp_path, REGISTRY)
    args = [
        "--registry",
        str(registry),
        "--preamble",
        str(preamble),
        "--out",
        str(tmp_path / "SKILL.md"),
        "--labels",
        "one|two",
    ]
    assert skill.main(args) == 2
    assert "3 headings" in capsys.readouterr().err


def test_labels_reach_the_render_from_the_command_line(tmp_path: pathlib.Path) -> None:
    registry, preamble = a_project(tmp_path, REGISTRY)
    out = tmp_path / "SKILL.md"
    args = [
        "--registry",
        str(registry),
        "--preamble",
        str(preamble),
        "--out",
        str(out),
        "--labels",
        "Règle|Origine|Appliquée par",
    ]
    assert skill.main(args) == 0
    assert "**Règle:**" in out.read_text(encoding="utf-8")


def test_a_layer_can_be_chosen_from_the_command_line(tmp_path: pathlib.Path) -> None:
    registry, preamble = a_project(tmp_path, REGISTRY)
    out = tmp_path / "SKILL.md"
    args = [
        "--registry",
        str(registry),
        "--preamble",
        str(preamble),
        "--out",
        str(out),
        "--layer",
        "business",
    ]
    assert skill.main(args) == 0
    assert "a-rule" not in out.read_text(encoding="utf-8"), "a baseline rule leaked into business"
