"""One wrapper for `gh`, and the three things it must not get wrong.

The reference implementation counted this call copied in five places, two of them
identical character for character, each carrying its own `S603` suppression — five
exemptions for one command. Collapsing them is the point; these tests are what
stop the one that remains from being subtly wrong.

Nothing here calls the real `gh`. What is checked is the argv, the flags and the
failure mode — the parts a caller depends on and cannot see.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest

from verifiable_gates import gh


class Done:
    def __init__(self, code: int = 0, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def fake(monkeypatch: pytest.MonkeyPatch, result: Done) -> dict[str, Any]:
    """Replace subprocess.run and record exactly how it was called."""
    seen: dict[str, Any] = {}

    def run(argv: list[str], **kwargs: Any) -> Done:  # noqa: ANN401 — mirroring subprocess
        seen["argv"] = argv
        seen.update(kwargs)
        return result

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/gh")
    return seen


def test_the_binary_is_found_rather_than_assumed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The resolved path is what makes the suppression on that call defensible."""
    seen = fake(monkeypatch, Done(out="ok\n"))

    assert gh.run(["pr", "view", "9"]) == "ok"
    assert seen["argv"] == ["/usr/bin/gh", "pr", "view", "9"]


def test_a_machine_without_gh_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing tool is not a permission problem, and must not read as one."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="no gh"):
        gh.run(["pr", "view", "9"])


def test_the_command_declares_a_time_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `gh` that never answers would eat the job's whole budget and be blamed on it."""
    seen = fake(monkeypatch, Done(out="ok"))
    gh.run(["api", "repos/x/y"])

    assert seen["timeout"] == gh.NETWORK_TIMEOUT_SECONDS
    assert seen["capture_output"] is True
    assert seen["text"] is True


def test_a_failure_carries_gh_s_own_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cause is nearly always scope or an expired token, and gh usually says which.

    Summarising it would throw away the only line that tells the reader what to
    fix, so the message is attached whole.
    """
    fake(monkeypatch, Done(code=1, err="  HTTP 403: Resource not accessible  \n"))

    with pytest.raises(PermissionError, match="HTTP 403"):
        gh.run(["api", "repos/x/y"])


def test_a_failure_is_raised_not_returned_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """`check=False` plus a returncode test — an empty answer must never look like data."""
    seen = fake(monkeypatch, Done(code=1, err="boom"))

    with pytest.raises(PermissionError):
        gh.run(["api", "x"])
    assert seen["check"] is False, "check=True would raise before the message is attached"


def test_output_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Callers compare these strings; trailing newlines are a class of silent mismatch."""
    fake(monkeypatch, Done(out="  value  \n\n"))

    assert gh.run(["x"]) == "value"


def test_the_api_helper_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = fake(monkeypatch, Done(out=json.dumps({"default_branch": "main"})))

    assert gh.api("repos/x/y")["default_branch"] == "main"
    assert seen["argv"][1:] == ["api", "repos/x/y"], "the api helper must go through gh api"
