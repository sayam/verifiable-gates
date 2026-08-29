"""The gate that stops a newcomer's issue being closed out from under them.

The decision is pure: given what a pull request closes, what those issues are
labelled, and the pull request body, it says whether the handoff was silent.
Everything that touches the network is separated from it, which is what makes
the decision testable at all.

Both directions matter here in an unusual way. A false red blocks a maintainer
doing perfectly legitimate work and teaches them the gate is noise; a false
green lets exactly the incident this exists to prevent happen again, and the
person who loses is the one who is not in the room.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
from typing import Any

import pytest

from verifiable_gates import check_issue_handoff as handoff
from verifiable_gates import gh

CLOSING = [{"number": 171, "title": "add a thing"}]
LABELLED = {171: {"good first issue", "docs"}}


# ---------------------------------------------------------------- the decision


def test_closing_a_labelled_issue_is_caught() -> None:
    found = handoff.problems(CLOSING, LABELLED, body="")

    assert len(found) == 1
    assert "#171" in found[0]
    assert "good first issue" in found[0]


def test_closing_an_unlabelled_issue_is_fine() -> None:
    """The gate is about the invitation, not about closing issues."""
    assert handoff.problems(CLOSING, {171: {"bug"}}, body="") == []


def test_a_pull_request_that_closes_nothing_is_fine() -> None:
    assert handoff.problems([], {}, body="") == []


def test_an_issue_with_no_labels_at_all_is_fine() -> None:
    """A number missing from the map means "not labelled", not "unknown"."""
    assert handoff.problems(CLOSING, {}, body="") == []


def test_every_labelled_issue_is_named_not_just_the_first() -> None:
    """A report that stops at the first leaves the second to be found by its author."""
    closing = [{"number": 1, "title": "one"}, {"number": 2, "title": "two"}]
    found = handoff.problems(closing, {1: {handoff.LABEL}, 2: {handoff.LABEL}}, body="")

    assert len(found) == 2
    assert {"#1" in found[0], "#2" in found[1]} == {True}


# ---------------------------------------------------------------- the override


def test_a_declared_takeback_releases_the_gate() -> None:
    """Taking it back is allowed. Taking it back *silently* is not."""
    body = "Fixes #171\n\ngood-first-issue-taken-back: nobody picked it up in three weeks\n"

    assert handoff.problems(CLOSING, LABELLED, body=body) == []


@pytest.mark.parametrize(
    ("body", "why"),
    [
        ("good-first-issue-taken-back:", "the marker with no reason at all"),
        ("good-first-issue-taken-back:   ", "whitespace is not a reason"),
        ("  good-first-issue-taken-back: mine now", "indented — not a declaration line"),
        ("see good-first-issue-taken-back: mine", "buried mid-sentence"),
    ],
)
def test_a_bare_or_buried_marker_does_not_release_it(body: str, why: str) -> None:
    """An override nobody has to justify is one that gets pasted in reflexively."""
    assert handoff.problems(CLOSING, LABELLED, body=body), why


def test_the_marker_is_found_anywhere_in_a_real_body() -> None:
    """People write it under their prose, not on line one."""
    body = "## What\n\nSomething.\n\ngood-first-issue-taken-back: stale for a month\n\n## Why\n"

    assert handoff.problems(CLOSING, LABELLED, body=body) == []


def test_a_missing_body_is_treated_as_no_declaration() -> None:
    """GitHub hands back null for an empty body — that must not crash, and must not excuse.

    A body that is absent contains no declaration, so the gate still catches the
    handoff. Reading it as "nothing to object to" would turn the commonest pull
    request shape there is — no body at all — into a silent way through.
    """
    assert handoff.problems(CLOSING, LABELLED, body=None) == handoff.problems(  # type: ignore[arg-type]
        CLOSING, LABELLED, body=""
    )
    assert handoff.problems(CLOSING, LABELLED, body=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------- the report


def test_the_report_names_both_ways_out() -> None:
    """Telling somebody they are wrong without telling them what to do is noise."""
    text = handoff.report(handoff.problems(CLOSING, LABELLED, body=""))

    assert "#171" in text
    assert "Remove" in text, "does not offer the ordinary way out"
    assert "good-first-issue-taken-back:" in text, "does not offer the deliberate way out"


# ---------------------------------------------------------------- the command line


def test_without_a_pull_request_number_it_stays_quiet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """This gate only means anything on a pull request — elsewhere it must not fail."""
    monkeypatch.delenv("PR_NUMBER", raising=False)
    monkeypatch.delenv("PR_BODY", raising=False)

    assert handoff.main([]) == 0
    assert "only means anything" in capsys.readouterr().out


def test_a_pull_request_closing_nothing_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(handoff, "closing_issues", lambda _pr: [])

    assert handoff.main(["--pr", "9"]) == 0
    assert "closes no issue" in capsys.readouterr().out


def test_a_silent_handoff_returns_a_blocking_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exit code is the whole point — a report nobody acts on blocks nothing."""
    monkeypatch.setattr(handoff, "closing_issues", lambda _pr: CLOSING)
    monkeypatch.setattr(handoff, "labels_of", lambda _n: LABELLED[171])

    assert handoff.main(["--pr", "9", "--body", ""]) == 1
    assert "still carries" in capsys.readouterr().err


def test_a_clean_handoff_returns_zero_and_says_what_it_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(handoff, "closing_issues", lambda _pr: CLOSING)
    monkeypatch.setattr(handoff, "labels_of", lambda _n: {"bug"})

    assert handoff.main(["--pr", "9", "--body", ""]) == 0
    assert "#171" in capsys.readouterr().out


def test_the_environment_supplies_the_defaults(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CI passes these as env, not flags — a default that never reads them is dead."""
    monkeypatch.setenv("PR_NUMBER", "9")
    monkeypatch.setenv("PR_BODY", "good-first-issue-taken-back: taking it back, stale")
    monkeypatch.setattr(handoff, "closing_issues", lambda _pr: CLOSING)
    monkeypatch.setattr(handoff, "labels_of", lambda _n: LABELLED[171])

    assert handoff.main([]) == 0
    capsys.readouterr()


def test_the_shipped_file_is_the_one_being_tested() -> None:
    """A guard on the guard: tests against a stale copy prove nothing about what ships."""
    source = pathlib.Path(handoff.__file__).read_text(encoding="utf-8")
    assert 'LABEL = "good first issue"' in source


# ------------------------------------------------------- talking to the platform


def fake_gh(monkeypatch: pytest.MonkeyPatch, payloads: dict[str, str]) -> list[list[str]]:
    """Stand in for `gh`, recording the argv it was handed.

    The argv matters as much as the answer: this gate's whole claim is that it
    reads what the platform *will do on merge*, and that claim is carried by the
    exact `--json` field it asks for. A fake that only returns data would let the
    field be renamed to something GitHub does not act on, silently.
    """
    seen: list[list[str]] = []

    def run(*args: str) -> str:
        seen.append(list(args))
        for key, payload in payloads.items():
            if key in args:
                return payload
        raise AssertionError(f"unexpected gh call: {args}")

    monkeypatch.setattr(handoff, "_gh", run)
    return seen


def test_closing_issues_asks_for_what_the_platform_acts_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = '{"closingIssuesReferences": [{"number": 171, "title": "add a thing"}]}'
    seen = fake_gh(monkeypatch, {"closingIssuesReferences": payload})

    found = handoff.closing_issues("9")

    assert found == [{"number": 171, "title": "add a thing"}]
    assert seen == [["pr", "view", "9", "--json", "closingIssuesReferences"]], (
        "asked GitHub something other than what it acts on at merge"
    )


def test_a_pull_request_closing_nothing_comes_back_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_gh(monkeypatch, {"closingIssuesReferences": '{"closingIssuesReferences": []}'})

    assert handoff.closing_issues("9") == []


def test_labels_are_read_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = '{"labels": [{"name": "good first issue"}, {"name": "docs"}]}'
    seen = fake_gh(monkeypatch, {"labels": payload})

    assert handoff.labels_of(171) == {"good first issue", "docs"}
    assert seen == [["issue", "view", "171", "--json", "labels"]]


def test_an_issue_with_no_labels_comes_back_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_gh(monkeypatch, {"labels": '{"labels": []}'})

    assert handoff.labels_of(171) == set()


def test_the_command_declares_a_time_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `gh` that never answers would eat the whole job and be blamed on the job.

    This drives the real `_gh`, so the argv, the flags and the timeout are the
    ones that ship — not a description of them.
    """
    captured: dict[str, object] = {}

    class Done:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def fake_run(argv: list[str], **kwargs: object) -> Done:
        captured["argv"] = argv
        captured.update(kwargs)
        return Done()

    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/gh")
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert handoff._gh("pr", "view", "9") == "{}"  # noqa: SLF001 — the point is the shipped call
    assert captured["argv"] == ["/usr/bin/gh", "pr", "view", "9"]
    assert captured["timeout"] == handoff.TOOL_TIMEOUT_SECONDS


def test_the_copy_keeps_the_wrappers_time_budget() -> None:
    """Two copies of one number — the test is what stops them drifting."""
    assert handoff.TOOL_TIMEOUT_SECONDS == gh.NETWORK_TIMEOUT_SECONDS


def test_a_machine_without_gh_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="no gh on this machine"):
        handoff._gh("pr", "view", "9")  # noqa: SLF001 — the shipped call is the subject


def test_a_failure_carries_gh_s_own_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """`gh` usually says which scope is missing — summarising it away loses the fix.

    The shipped copy used to raise `CalledProcessError`, which carries the
    return code and not the words; the wrapper's contract is `PermissionError`
    with stderr attached, and this copy now keeps it.
    """

    class Refused:
        stdout = ""
        stderr = "HTTP 403: Resource not accessible by integration"
        returncode = 1

    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/gh")
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: Refused())

    with pytest.raises(PermissionError, match="not accessible by integration"):
        handoff._gh("pr", "view", "9")  # noqa: SLF001 — the shipped call is the subject


def test_a_platform_the_gate_cannot_ask_is_the_third_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2, not a traceback and not a pass — the same contract as the censuses."""

    def refuse(_pr: str) -> list[dict[str, Any]]:
        raise PermissionError("`gh pr view 9` failed: HTTP 403")

    monkeypatch.setattr(handoff, "closing_issues", refuse)

    assert handoff.main(["--pr", "9"]) == 2
    assert "cannot ask the platform" in capsys.readouterr().err
