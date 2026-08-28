"""The crosswalk is derived from evidence, never written — and says plainly what nothing backs."""

from __future__ import annotations

import pytest

from verifiable_gates import gates_crosswalk as cw

MARKER = "<!-- table starts here -->"
WORDS = cw.Words(
    header="# Crosswalk\n",
    summary="passed {rows} · backed {backed} · by argument {unbacked}\n",
    backed_title="## gate → requirements\n",
    table_head="| gate | requirements |",
    unbacked_title="## by argument only\n",
    unbacked_note="No gate runs for these.\n",
)
GATES = [
    {
        "id": "tests-own-files",
        "kind": "test",
        "enforced_by": {"job": "test", "tests": ["tests/test_a.py"]},
    },
    {"id": "stack-runs", "kind": "job", "enforced_by": {"job": "stack", "tests": None}},
    {"id": "image-built", "kind": "step", "enforced_by": {"job": "image"}},
]
SHEET = (
    "| V0.0.1 | 1 | in the preamble | pass | `tests/test_a.py` |\n"
    + MARKER
    + "\n| id | L | text | status | evidence |\n"
    "|---|---|---|---|---|\n"
    "| V1.1.1 | 1 | a | pass | `tests/test_a.py::test_it` |\n"
    "| V1.1.2 | 1 | b | pass | `ci:stack` and `ci:image` |\n"
    "| V1.1.10 | 1 | c | pass | argued in `ADR 0001` |\n"
    "| V1.1.3 | 1 | d | fail | — |\n"
    "| V1.1.4 | 1 | e | pass |\n"  # malformed — four cells
    "| V1.1.5 | 1 | f | pass | `tests/test_nobody_owns.py` |\n"
)


def test_passed_rows_reads_only_below_the_marker_and_only_passing_rows() -> None:
    rows = cw.passed_rows(SHEET, marker=MARKER, passed="pass")

    assert set(rows) == {"V1.1.1", "V1.1.2", "V1.1.10", "V1.1.5"}
    assert "V0.0.1" not in rows, "a row above the marker is the person's, not the assessment's"
    assert "V1.1.3" not in rows, "a failing row is not a passing row"


def test_a_worksheet_without_the_marker_is_loud() -> None:
    with pytest.raises(ValueError, match="marker"):
        cw.passed_rows("no marker here", marker=MARKER, passed="pass")


def test_a_worksheet_where_nothing_passes_is_loud_not_empty() -> None:
    """An empty crosswalk would read as "nothing is backed" — a broken reader must not say that."""
    with pytest.raises(ValueError, match="no passing row"):
        cw.passed_rows(MARKER + "\n| V1.1.1 | 1 | a | fail | — |\n", marker=MARKER, passed="pass")


def test_gate_lookups_partition_files_and_count_only_job_and_step_gates_by_job() -> None:
    by_file, by_job = cw.gate_lookups(GATES)

    assert by_file == {"tests/test_a.py": "tests-own-files"}
    assert by_job == {"stack": ["stack-runs"], "image": ["image-built"]}
    assert "test" not in by_job, "mapping ci:test to every test gate would be noise"


def test_the_crosswalk_maps_by_file_and_by_job_and_lists_the_rest() -> None:
    rows = cw.passed_rows(SHEET, marker=MARKER, passed="pass")
    by_file, by_job = cw.gate_lookups(GATES)

    rendered = cw.crosswalk(rows, by_file, by_job, words=WORDS)

    assert rendered == (
        "# Crosswalk\n\n"
        "passed 4 · backed 2 · by argument 2\n\n"
        "## gate → requirements\n\n"
        "| gate | requirements |\n"
        "|---|---|\n"
        "| `image-built` | V1.1.2 |\n"
        "| `stack-runs` | V1.1.2 |\n"
        "| `tests-own-files` | V1.1.1 |\n"
        "\n"
        "## by argument only\n\n"
        "No gate runs for these.\n\n"
        "V1.1.5 · V1.1.10\n"
    )


def test_a_cited_file_no_gate_owns_backs_nothing() -> None:
    """Citing a test file is not evidence unless the registry says whose it is."""
    rows = {"V1.1.5": "`tests/test_nobody_owns.py`"}

    rendered = cw.crosswalk(rows, {}, {}, words=WORDS)

    assert "backed 0 · by argument 1" in rendered
    assert rendered.rstrip().endswith("V1.1.5")


def test_requirements_in_a_gate_row_sort_as_numbers() -> None:
    rows = {"V1.1.10": "`ci:stack`", "V1.1.2": "`ci:stack`", "V1.1.9": "`ci:stack`"}

    rendered = cw.crosswalk(rows, {}, {"stack": ["stack-runs"]}, words=WORDS)

    assert "| `stack-runs` | V1.1.2 · V1.1.9 · V1.1.10 |" in rendered
