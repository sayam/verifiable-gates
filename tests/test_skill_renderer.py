"""Rendering is a pure function of a catalogue, a preamble and a language.

The rule sheet exists so that nobody writes the rules down twice. That only holds
while the sheet is **generated** — which means the render has to be
byte-deterministic, so a project can hold its committed file against a fresh one
and see a difference rather than trust that there is none.

Three things are inputs here that were constants in the reference implementation,
and each has a test saying why it matters: the **catalogue**, so one renderer
serves any set of rules; the **preamble**, because the opening of a rule sheet is
prose a project writes about itself; and the **language**, because the catalogue
carries the published English and the original wording side by side, and a
renderer that could reach only one of them would make the other dead weight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from verifiable_gates import rules as catalogue
from verifiable_gates import skill

if TYPE_CHECKING:
    import pathlib

PREAMBLE = "# Rules\n\nSome opening prose.\n"


def a_rule(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 — field values are of mixed type
    base: dict[str, Any] = {
        "id": "a-rule",
        "layer": "baseline",
        "pillar": "security",
        "title": "A rule that holds",
        "title_th": "กฎที่ยังยืนอยู่",
        "born_from": "the trap that produced it",
        "born_from_th": "กับดักที่ให้กำเนิดมัน",
        "reference": {"kind": "test", "job": "test", "tests": ["tests/test_a.py"]},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- selection


def test_a_layer_can_be_asked_for() -> None:
    rules = [a_rule(), a_rule(id="business-rule", layer="business")]
    assert [r["id"] for r in catalogue.by_layer(rules, "business")] == ["business-rule"]


def test_no_layer_means_every_rule() -> None:
    rules = [a_rule(), a_rule(id="business-rule", layer="business")]
    assert len(catalogue.by_layer(rules)) == 2


def test_the_order_of_the_catalogue_is_kept() -> None:
    """A catalogue is written to be read; the neighbours of a rule are part of its meaning."""
    rules = [a_rule(id="zeta"), a_rule(id="alpha"), a_rule(id="mid")]
    assert [r["id"] for r in catalogue.by_layer(rules)] == ["zeta", "alpha", "mid"]


# ---------------------------------------------------------------- rendering


def test_a_rendered_rule_carries_all_three_parts() -> None:
    out = skill.render([a_rule()], PREAMBLE)
    assert "### `a-rule`" in out
    assert "**Rule:** A rule that holds" in out
    assert "**Born from:** the trap that produced it" in out
    assert "**Enforced in the reference:** `tests/test_a.py`" in out


def test_the_preamble_comes_from_the_caller() -> None:
    """Otherwise every project that uses this tool ships this project's story."""
    assert skill.render([], "# Mine\n").startswith("# Mine\n")


def test_the_other_language_can_be_rendered() -> None:
    """The original wording is published text, not an archive nobody can reach."""
    out = skill.render([a_rule()], PREAMBLE, language="th")
    assert "**กฎ:** กฎที่ยังยืนอยู่" in out
    assert "A rule that holds" not in out


def test_the_headings_follow_the_language_unless_the_caller_says_otherwise() -> None:
    assert "**Born from:**" in skill.render([a_rule()], PREAMBLE)
    assert "**เกิดจาก:**" in skill.render([a_rule()], PREAMBLE, language="th")


def test_the_field_headings_can_be_overridden() -> None:
    """A project rendering in a third language needs its own headings.

    The example uses non-ASCII headings, since those are the ones likely to break.
    """
    out = skill.render([a_rule()], PREAMBLE, labels=("Règle", "Origine", "Appliquée par"))
    assert "**Règle:** A rule that holds" in out
    assert "**Rule:**" not in out


def test_a_language_falls_back_rather_than_rendering_a_blank() -> None:
    """A missing translation must show the published text, not an empty field."""
    out = skill.render([a_rule(title_th="")], PREAMBLE, language="th")
    assert "**กฎ:** A rule that holds" in out


def test_whitespace_in_born_from_is_collapsed() -> None:
    """`born_from` is written as a wrapped block; a sheet wants one paragraph."""
    out = skill.render([a_rule(born_from="a lesson\n   spread over\n   lines")], PREAMBLE)
    assert "**Born from:** a lesson spread over lines" in out


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (
            a_rule(reference={"kind": "test", "job": "t", "tests": ["a.py", "b.py"]}),
            "`a.py` · `b.py`",
        ),
        (
            a_rule(reference={"kind": "step", "job": "scans", "step": "the step"}),
            'job `scans` step "the step"',
        ),
        (a_rule(reference={"kind": "job", "job": "scans"}), "job `scans`"),
    ],
    ids=["test", "step", "job"],
)
def test_each_kind_points_at_what_enforces_it(rule: dict[str, Any], expected: str) -> None:
    """Point at the enforcer rather than restating its command — no second copy."""
    assert expected in skill.render([rule], PREAMBLE)


def test_the_same_inputs_render_the_same_bytes() -> None:
    """Without this, "regenerate and compare" proves nothing."""
    rules = [a_rule(), a_rule(id="second")]
    assert skill.render(rules, PREAMBLE) == skill.render(rules, PREAMBLE)


# ---------------------------------------------------------------- the command line

CATALOGUE = """version: 1
rules:
  - id: a-rule
    layer: baseline
    pillar: security
    title: A rule that holds
    title_th: กฎที่ยังยืนอยู่
    born_from: the trap that produced it
    born_from_th: กับดักที่ให้กำเนิดมัน
    reference: {kind: test, job: test, tests: [tests/test_a.py]}
"""


def a_project(root: pathlib.Path, catalogue_text: str) -> tuple[pathlib.Path, pathlib.Path]:
    (root / "rules.yaml").write_text(catalogue_text, encoding="utf-8")
    (root / "preamble.md").write_text(PREAMBLE, encoding="utf-8")
    return root / "rules.yaml", root / "preamble.md"


def test_writing_and_then_checking_agree(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "SKILL.md"
    args = ["--catalogue", str(catalogue), "--preamble", str(preamble), "--out", str(out)]

    assert skill.main(args) == 0
    assert "rewrote" in capsys.readouterr().out
    assert skill.main([*args, "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_a_second_write_reports_nothing_changed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "SKILL.md"
    args = ["--catalogue", str(catalogue), "--preamble", str(preamble), "--out", str(out)]
    assert skill.main(args) == 0
    capsys.readouterr()
    assert skill.main(args) == 0
    assert "unchanged" in capsys.readouterr().out


def test_check_fails_when_the_committed_file_drifted(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point of committing a generated file is that drift becomes visible."""
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "SKILL.md"
    out.write_text("edited by hand\n", encoding="utf-8")

    args = [
        "--catalogue",
        str(catalogue),
        "--preamble",
        str(preamble),
        "--out",
        str(out),
        "--check",
    ]
    assert skill.main(args) == 1
    assert "differs from a fresh render" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "edited by hand\n", "--check must not write"


def test_check_fails_when_the_file_is_absent(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    args = [
        "--catalogue",
        str(catalogue),
        "--preamble",
        str(preamble),
        "--out",
        str(tmp_path / "gone.md"),
        "--check",
    ]
    assert skill.main(args) == 1
    assert "differs" in capsys.readouterr().err


def test_a_broken_catalogue_stops_the_render(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rendering from a catalogue nobody validated would publish its mistakes."""
    catalogue, preamble = a_project(tmp_path, "version: 1\nrules:\n  - id: Bad_Id\n")
    out = tmp_path / "SKILL.md"
    args = ["--catalogue", str(catalogue), "--preamble", str(preamble), "--out", str(out)]

    assert skill.main(args) == 2
    assert "catalogue:" in capsys.readouterr().err
    assert not out.exists(), "nothing should be written from a catalogue that did not pass"


def test_labels_must_come_in_threes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two headings would silently drop a field from every rule."""
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    args = [
        "--catalogue",
        str(catalogue),
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
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "SKILL.md"
    args = [
        "--catalogue",
        str(catalogue),
        "--preamble",
        str(preamble),
        "--out",
        str(out),
        "--labels",
        "Règle|Origine|Appliquée par",
    ]
    assert skill.main(args) == 0
    assert "**Règle:**" in out.read_text(encoding="utf-8")


def test_a_language_can_be_chosen_from_the_command_line(tmp_path: pathlib.Path) -> None:
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "SKILL.md"
    args = [
        "--catalogue",
        str(catalogue),
        "--preamble",
        str(preamble),
        "--out",
        str(out),
        "--language",
        "th",
    ]
    assert skill.main(args) == 0
    assert "กฎที่ยังยืนอยู่" in out.read_text(encoding="utf-8")


def test_a_layer_can_be_chosen_from_the_command_line(tmp_path: pathlib.Path) -> None:
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "SKILL.md"
    args = [
        "--catalogue",
        str(catalogue),
        "--preamble",
        str(preamble),
        "--out",
        str(out),
        "--layer",
        "business",
    ]
    assert skill.main(args) == 0
    assert "a-rule" not in out.read_text(encoding="utf-8"), "a baseline rule leaked into business"


def test_a_preamble_that_is_not_there_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sheet is generated from a catalogue and a preamble; a preamble that is not
    there was a traceback and exit 1 (round 2, 2026-08-31)."""
    catalogue, _ = a_project(tmp_path, CATALOGUE)
    argv = [
        "--catalogue",
        str(catalogue),
        "--preamble",
        str(tmp_path / "not-there.md"),
        "--out",
        str(tmp_path / "SKILL.md"),
    ]

    assert skill.main(argv) == 2
    assert "cannot read the preamble" in capsys.readouterr().err


def test_a_catalogue_that_is_not_utf_8_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The preamble was given the third answer in round 2; the catalogue beside it was
    still read bare (self-audit round 3, 2026-09-01)."""
    bad, preamble = a_project(tmp_path, CATALOGUE)
    bad.write_bytes("rules: caf\xe9\n".encode("latin-1"))

    with pytest.raises(SystemExit) as refused:
        skill.main(
            [
                "--catalogue",
                str(bad),
                "--preamble",
                str(preamble),
                "--out",
                str(tmp_path / "SKILL.md"),
            ]
        )

    assert refused.value.code == 2
    assert "cannot read the catalogue" in capsys.readouterr().err


def test_a_sheet_that_cannot_be_written_is_a_misuse(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sheet that could not be written is a call that could not be answered, not a sheet
    that is out of date — it was a traceback and exit 1, the code this tool uses for "the
    file on disk differs" (self-audit round 5, 2026-09-01)."""
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    out = tmp_path / "a-directory"
    out.mkdir()

    with pytest.raises(SystemExit) as refused:
        skill.main(["--catalogue", str(catalogue), "--preamble", str(preamble), "--out", str(out)])

    assert refused.value.code == 2
    assert "cannot write the sheet" in capsys.readouterr().err


def test_a_preamble_this_renderer_cannot_decode_stops_the_render(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The preamble is prose a person wrote, so another encoding is the ordinary case, not
    the exotic one — and it ended the render with a raw `UnicodeDecodeError` and exit 1
    rather than the 2 this reader answers for a preamble it cannot open (self-audit round
    12, 2026-09-01)."""
    catalogue, preamble = a_project(tmp_path, CATALOGUE)
    preamble.write_bytes(b"A preamble with a caf\xe9 in it\n")
    out = tmp_path / "SKILL.md"
    args = ["--catalogue", str(catalogue), "--preamble", str(preamble), "--out", str(out)]

    assert skill.main(args) == 2
    printed = capsys.readouterr().err
    assert "cannot read the preamble" in printed
    assert "not UTF-8" in printed
    assert not out.exists(), "nothing should be written from a preamble that could not be read"
