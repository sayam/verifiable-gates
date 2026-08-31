"""This repository's own floors, held against reality by the ratchet module it ships.

`ratchets` was proved on fakes and pointed at nobody here: the coverage floor and the
docstring floor were "moved up only" by a comment in ci.yml and a row in DECISIONS.md,
and a comment is not a mechanism (the re-audit of 2026-08-30, rounds 14 and 23, counted
"thresholds move one way" among the declared rules with no machine behind them).

Two floors, two shapes:

- **interrogate** — measured live by running the tool, as the `lint` job does. The slack
  is not the module's default of one point: DECISIONS.md `interrogate-at-84` says the
  floor moves when coverage reaches 90, so the slack is 90 − 84, and this test and that
  row go red on the same day.
- **coverage** — `fail_under` is 100, the top of its scale, and the tool itself refuses
  a run beneath it. There is no slack to measure above 100; what is held is that the
  number is still 100 (a lowered floor is a decision someone signs, not a convenience).
- **xenon** — three ranks on one line of ci.yml, read by nothing until an outside audit
  on 2026-08-30 lowered one and the suite stayed green. The line has to say what the
  row `xenon-floor-at-reality` decided, and each rank has to sit where reality sits:
  measured with `radon`, the same tool xenon reads, a worst block, worst module or
  average that ranks *better* than its ceiling is a ceiling left behind — move it up
  in the line and the row, in the same change.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import tomllib

import pytest

from verifiable_gates import measure, ratchets

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTERROGATE_MOVES_AT = 90.0  # DECISIONS.md: interrogate-at-84


def declared_floors() -> dict[str, float]:
    """The two numbers in pyproject.toml that promise to move one way."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {
        "interrogate": float(config["tool"]["interrogate"]["fail-under"]),
        "coverage": float(config["tool"]["coverage"]["report"]["fail_under"]),
    }


def our_ratchets(floors: dict[str, float]) -> dict[str, ratchets.Ratchet]:
    return {
        "interrogate": ratchets.Ratchet(
            "interrogate", slack=INTERROGATE_MOVES_AT - floors["interrogate"]
        ),
        "coverage": ratchets.Ratchet("coverage", owned_by_a_tool=True, slack=0.0),
    }


def test_the_docstring_floor_sits_against_reality() -> None:
    """Below the floor `interrogate` itself is red in `lint`; above it by the slack, this is
    the only thing that says the floor was left behind."""
    floors = declared_floors()
    measured = {
        "interrogate": measure.docstring_coverage(ROOT, "src"),
        "coverage": floors["coverage"],
    }

    assert ratchets.problems(our_ratchets(floors), floors, measured) == []


def test_the_coverage_floor_is_the_top_of_its_scale() -> None:
    assert declared_floors()["coverage"] == 100.0, "lowering it is a decision, not a convenience"


def test_the_slack_is_the_decisions_rows_expiry_not_the_default() -> None:
    """DECISIONS.md `interrogate-at-84` expires when coverage reaches 90; this test goes red
    the same day, so the row and the ratchet cannot disagree about when the floor moves."""
    text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| interrogate-at-"))

    assert f"reaches {INTERROGATE_MOVES_AT:.0f}" in row, row
    assert our_ratchets(declared_floors())["interrogate"].slack == pytest.approx(6.0)


def test_reality_past_the_expiry_is_red_and_names_the_floor() -> None:
    floors = declared_floors()
    measured = {"interrogate": INTERROGATE_MOVES_AT + 0.5, "coverage": 100.0}

    found = ratchets.problems(our_ratchets(floors), floors, measured)

    assert len(found) == 1
    assert found[0].startswith("interrogate: floor 84.0 but actually 90.5 — 6.50 above it"), found


def test_the_declared_floor_is_the_one_the_decisions_row_names() -> None:
    """Lowering the floor is the one move a ratchet cannot see from the numbers alone —
    a lower floor has *more* slack, not less. The row `interrogate-at-<N>` names the
    number that was decided; the file has to carry that number until the row is rewritten."""
    text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| interrogate-at-"))
    decided = float(row.split("|")[1].strip().rsplit("-", 1)[1])

    assert declared_floors()["interrogate"] == decided, (declared_floors(), decided)


# ------------------------------------------------------------------------ xenon

XENON_LINE = re.compile(
    r"xenon --max-absolute (?P<absolute>[A-F]) --max-modules (?P<modules>[A-F])"
    r" --max-average (?P<average>[A-F]) src"
)
XENON_ROW = re.compile(
    r"(?P<absolute>[A-F]) \(block\) / (?P<modules>[A-F]) \(module\)"
    r" / (?P<average>[A-F]) \(average\)"
)


def declared_ceilings() -> dict[str, str]:
    """The three ranks on ci.yml's xenon line."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    match = XENON_LINE.search(text)
    assert match, "ci.yml no longer runs xenon with three explicit ranks"
    return match.groupdict()


def decided_ceilings() -> dict[str, str]:
    """The three ranks the row `xenon-floor-at-reality` decided."""
    text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| xenon-floor-at-"))
    match = XENON_ROW.search(row)
    assert match, row
    return match.groupdict()


def rank(complexity: float) -> str:
    """radon's rank for a complexity — the scale xenon judges by."""
    edges = ((5, "A"), (10, "B"), (20, "C"), (30, "D"), (40, "E"))
    return next((letter for edge, letter in edges if complexity <= edge), "F")


def measured_ceilings() -> dict[str, str]:
    """Where reality sits: the worst block, the worst module, the average — via radon."""
    done = subprocess.run(
        ["radon", "cc", "-j", "src"],  # noqa: S607 — found on PATH like xenon itself
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    per_module = {
        path: [block["complexity"] for block in blocks]
        for path, blocks in json.loads(done.stdout).items()
        if blocks
    }
    every = [c for blocks in per_module.values() for c in blocks]
    return {
        "absolute": rank(max(every)),
        "modules": rank(max(sum(blocks) / len(blocks) for blocks in per_module.values())),
        "average": rank(sum(every) / len(every)),
    }


def test_the_xenon_line_says_what_the_decisions_row_decided() -> None:
    """Lowering a ceiling is one edit to ci.yml that no tool sees; the row has to move with it."""
    assert declared_ceilings() == decided_ceilings()


@pytest.mark.parametrize("which", ["absolute", "modules", "average"])
def test_each_xenon_ceiling_sits_where_reality_sits(which: str) -> None:
    """A ceiling reality has dropped below is a ceiling left behind — move it up, and the row."""
    declared = declared_ceilings()[which]
    measured = measured_ceilings()[which]
    assert measured <= declared, f"{which}: ceiling {declared} but reality is {measured}"
    assert measured == declared, (
        f"{which}: ceiling {declared} but reality now ranks {measured} — move the ceiling up "
        "in ci.yml and in DECISIONS.md `xenon-floor-at-reality`, in the same change"
    )


def test_the_interrogate_row_says_the_numbers_this_test_and_pyproject_use() -> None:
    """DECISIONS `interrogate-at-84` names the floor (84%) and the move point (90) in prose;
    only its id was held, so the words could say any number (self-audit, 2026-08-31)."""
    row = next(
        line
        for line in (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| interrogate-at-84 |")
    )
    said_floor = re.search(r"floor is (\d+)%", row)
    said_move = re.search(r"reaches (\d+)", row)
    assert said_floor, row
    assert said_move, row
    assert float(said_floor.group(1)) == declared_floors()["interrogate"], row
    assert float(said_move.group(1)) == INTERROGATE_MOVES_AT, row
