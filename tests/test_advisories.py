"""A register of accepted advisories, held to reality in both directions.

The rule under test is not "no findings" — a check that is red from its first day
gets silenced within a fortnight, and the real findings go with it. The rule is
that **every finding has been decided about**, which makes the register the thing
that has to be right.

The second direction is the one that rots: tools never mention an id they did not
need to ignore, so an entry outlives its subject in complete silence and sits
there excusing nothing, until the day it silently excuses something real.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from verifiable_gates import advisories

ROOT = pathlib.Path(__file__).resolve().parent.parent

REGISTER = """\
# Advisories we have looked at and accepted, with why.

GHSA-aaaa-bbbb-cccc  # pinned by a tool we do not control; upstream has not moved
PYSEC-2026-1          # no fix exists yet; the affected path is not reachable

"""


def only(found: list[str]) -> str:
    assert len(found) == 1, f"expected exactly one problem, got {found}"
    return found[0]


# ------------------------------------------------------------- the register


def test_the_register_carries_each_reason(tmp_path: pathlib.Path) -> None:
    """An id with no reason is an id nobody can review later."""
    path = tmp_path / "accepted.txt"
    path.write_text(REGISTER, encoding="utf-8")

    entries = advisories.accepted(path)

    assert set(entries) == {"GHSA-aaaa-bbbb-cccc", "PYSEC-2026-1"}
    assert "upstream has not moved" in entries["GHSA-aaaa-bbbb-cccc"]


def test_comments_and_blank_lines_are_not_entries(tmp_path: pathlib.Path) -> None:
    """The file has to be able to explain itself without that becoming data."""
    path = tmp_path / "accepted.txt"
    path.write_text("# only a preamble\n\n   \n", encoding="utf-8")

    assert advisories.accepted(path) == {}


# --------------------------------------------------------- both directions


def test_a_finding_nobody_entered_is_red() -> None:
    found = advisories.problems({"CVE-2026-1": "openssl (HIGH, fix: 3.0.1)"}, {})

    assert "CVE-2026-1" in only(found)


def test_a_finding_that_was_entered_is_quiet() -> None:
    found = advisories.problems({"CVE-2026-1": "openssl"}, {"CVE-2026-1": "no fix yet"})

    assert found == []


def test_an_entry_with_nothing_left_to_excuse_is_red() -> None:
    """**The direction the tools are silent about.**

    An ignore flag never mentions an id it did not need, so a stale entry makes no
    noise at all — it simply waits to excuse something nobody decided about.
    """
    found = advisories.problems({}, {"CVE-2026-1": "no fix yet"})

    assert "CVE-2026-1" in only(found)
    assert "take the line out" in only(found)


def test_both_directions_are_reported_together() -> None:
    """One run has to say everything, or the second problem waits for the next push."""
    found = advisories.problems({"NEW-1": "detail"}, {"OLD-1": "why"})

    assert len(found) == 2


def test_a_clean_register_says_nothing() -> None:
    assert advisories.problems({}, {}) == []


# ------------------------------------------------------- reading the reports


def test_a_python_audit_report_is_read_with_its_fix_versions() -> None:
    report = {
        "dependencies": [
            {
                "name": "mcp",
                "version": "1.2.0",
                "vulns": [{"id": "PYSEC-2026-1", "fix_versions": ["1.2.1", "1.3.0"]}],
            }
        ]
    }

    found = advisories.from_pip_audit(report)

    assert found == {"PYSEC-2026-1": "mcp==1.2.0 (fix: 1.2.1, 1.3.0)"}


def test_no_fix_yet_reads_differently_from_a_fix_we_cannot_take() -> None:
    """Waiting on somebody else, and being blocked on this side, are different facts."""
    report = {
        "dependencies": [
            {"name": "x", "version": "1", "vulns": [{"id": "P-1", "fix_versions": []}]}
        ]
    }

    assert "none yet" in advisories.from_pip_audit(report)["P-1"]


def test_a_report_with_no_findings_reads_as_empty() -> None:
    assert advisories.from_pip_audit({"dependencies": []}) == {}
    assert advisories.from_npm_audit({"vulnerabilities": {}}) == {}
    assert advisories.from_trivy({"Results": []}) == {}


def test_a_package_audit_is_counted_by_advisory_not_by_package() -> None:
    """**Six headlines, one cause.**

    The report groups by affected package: an entry's `via` holds the advisory
    itself as an object, and plain strings for packages that merely inherited it.
    Counting headlines makes the register grow with how packages happen to depend
    on each other rather than with what anybody decided.
    """
    advisory = {
        "name": "brace-expansion",
        "range": "<1.1.12",
        "severity": "low",
        "url": "https://github.com/advisories/GHSA-1234-5678-90ab",
    }
    report = {
        "vulnerabilities": {
            "brace-expansion": {"via": [advisory]},
            "minimatch": {"via": ["brace-expansion"]},
            "glob": {"via": ["minimatch"]},
        }
    }

    found = advisories.from_npm_audit(report)

    assert list(found) == ["GHSA-1234-5678-90ab"]
    assert "low" in found["GHSA-1234-5678-90ab"]


def test_the_advisory_id_is_the_one_a_person_can_look_up() -> None:
    """A registry's internal number cannot be looked up, and a register full of them
    cannot be reviewed by the person who has to decide whether an entry still holds."""
    report = {
        "vulnerabilities": {
            "x": {
                "via": [
                    {
                        "name": "x",
                        "range": "<1",
                        "severity": "high",
                        "source": 1234567,
                        "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
                    }
                ]
            }
        }
    }

    assert list(advisories.from_npm_audit(report)) == ["GHSA-aaaa-bbbb-cccc"]


def test_an_advisory_whose_url_changed_shape_still_gets_an_id() -> None:
    """Losing the id entirely would drop the finding — worse than an ugly one."""
    report = {"vulnerabilities": {"x": {"via": [{"name": "x", "url": "https://example.test/x"}]}}}

    assert list(advisories.from_npm_audit(report)) == ["https://example.test/x"]


def test_an_image_report_is_read_with_severity_and_fix() -> None:
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2026-9999",
                        "PkgName": "libssl3",
                        "Severity": "HIGH",
                        "FixedVersion": "3.0.15-1",
                    }
                ]
            }
        ]
    }

    found = advisories.from_trivy(report)

    assert found == {"CVE-2026-9999": "libssl3 (HIGH, fix: 3.0.15-1)"}


def test_an_image_report_is_not_filtered_a_second_time() -> None:
    """Severity and fixed-ness are decided where the scanner is invoked, once.

    A filter in two places is a filter that will one day disagree with itself, and
    the half that is wrong will be the half nobody is looking at.
    """
    report = {
        "Results": [
            {"Vulnerabilities": [{"VulnerabilityID": "CVE-1", "Severity": "LOW"}]},
            {"Vulnerabilities": [{"VulnerabilityID": "CVE-2", "Severity": "CRITICAL"}]},
        ]
    }

    assert set(advisories.from_trivy(report)) == {"CVE-1", "CVE-2"}


# --------------------------------------------------------------- the wording


def test_the_wording_is_an_input() -> None:
    found = advisories.problems({"X": "d"}, {}, messages={"unjudged": "{id} needs a decision"})

    assert only(found) == "X needs a decision"


def test_one_replaced_message_leaves_the_other_alone() -> None:
    found = advisories.problems({}, {"OLD": "why"}, messages={"unjudged": "unused"})

    assert "take the line out" in only(found)


def test_a_register_file_that_is_not_there_is_loud(tmp_path: pathlib.Path) -> None:
    """No register and an empty register are opposite facts about a project."""
    with pytest.raises(FileNotFoundError):
        advisories.accepted(tmp_path / "absent.txt")


# ---------------------------------------------------------------- the command line

PIP_REPORT: dict[str, Any] = {
    "dependencies": [
        {"name": "x", "version": "1.0", "vulns": [{"id": "GHSA-1", "fix_versions": ["1.1"]}]},
        {"name": "y", "version": "2.0", "vulns": []},
    ]
}


def a_run(tmp_path: pathlib.Path, register: str, report: dict[str, Any] = PIP_REPORT) -> int:
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / "accepted.txt").write_text(register, encoding="utf-8")
    return advisories.main(
        [
            "--kind",
            "pip-audit",
            "--report",
            str(tmp_path / "report.json"),
            "--register",
            str(tmp_path / "accepted.txt"),
        ]
    )


def test_an_unjudged_finding_is_red(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert a_run(tmp_path, "# nothing accepted\n") == 1
    assert "GHSA-1" in capsys.readouterr().err


def test_a_judged_finding_is_green_and_counted(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert a_run(tmp_path, "GHSA-1  # accepted: no fix we can take yet\n") == 0
    assert "1 finding(s), every one judged; 1 accepted" in capsys.readouterr().out


def test_a_stale_entry_is_red_even_with_nothing_found(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The quiet direction: an entry excusing nothing is one that will excuse something."""
    assert a_run(tmp_path, "GHSA-9  # long gone\n", {"dependencies": []}) == 1
    assert "GHSA-9" in capsys.readouterr().err


def test_this_repositorys_register_is_readable_and_reasoned() -> None:
    """Every entry in our own register carries a reason — an id alone is not a judgement."""
    register = advisories.accepted(ROOT / "pins" / "dev" / "advisories-accepted.txt")

    assert all(register.values()), f"an entry with no reason: {register}"


@pytest.mark.parametrize(
    ("report", "register", "why"),
    [
        ("not json", "", "a report the scanner left half-written"),
        ("[]", "", "a report of the wrong shape"),
        (None, "", "a report that is not there"),
        ('{"dependencies": []}', None, "a register that is not there"),
    ],
    ids=["unparsable", "wrong-shape", "missing-report", "missing-register"],
)
def test_a_report_or_register_this_reader_cannot_read_is_a_misuse(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    report: str | None,
    register: str | None,
    why: str,
) -> None:
    """`pip-audit` writes half a file when it dies, and the register is edited by hand.
    Both were a traceback and exit 1 — the code that means findings (round 2, 2026-08-31)."""
    report_path, register_path = tmp_path / "report.json", tmp_path / "accepted.txt"
    if report is not None:
        report_path.write_text(report, encoding="utf-8")
    if register is not None:
        register_path.write_text(register, encoding="utf-8")

    argv = ["--kind", "pip-audit", "--report", str(report_path), "--register", str(register_path)]
    assert advisories.main(argv) == 2, why
    assert "cannot read the report or the register" in capsys.readouterr().err
