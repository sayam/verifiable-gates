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


# ---------------------------------------------------------------- a borrowed token
#
# Names, not secrets: the variable that would hold a token, and a stand-in value.
ALERTS_ENV = "GH_TOKEN_ALERTS"
LENT = "alerts-token"


def test_a_named_token_is_lent_to_that_call_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two questions in one job can need two tokens — one scope must not be forced on both."""
    monkeypatch.setenv(ALERTS_ENV, LENT)
    seen = fake(monkeypatch, Done(out="[]"))

    gh.api("repos/x/y/code-scanning/alerts", token_env=ALERTS_ENV)

    assert seen["env"]["GH_TOKEN"] == LENT
    assert seen["env"]["GITHUB_TOKEN"] == LENT


def test_an_unset_token_variable_falls_back_to_gh_s_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """On a maintainer's machine the variable is not set — that is the normal case, not an error."""
    monkeypatch.delenv(ALERTS_ENV, raising=False)
    seen = fake(monkeypatch, Done(out="{}"))

    gh.api("repos/x/y", token_env=ALERTS_ENV)

    assert seen["env"] is None, "an absent variable must not wipe the environment gh already has"


def test_no_token_name_means_no_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = fake(monkeypatch, Done(out="{}"))

    gh.api("repos/x/y")

    assert seen["env"] is None


# ---------------------------------------------------------------- paging


def _pager(monkeypatch: pytest.MonkeyPatch, pages: list[Any], *, ceiling: int = 6) -> list[str]:
    """Replace `api` with a fake that serves `pages` in order and refuses to go on forever."""
    asked: list[str] = []

    def fake_api(path: str, **_kwargs: Any) -> Any:  # noqa: ANN401 — the shape is the endpoint's
        asked.append(path)
        if len(asked) > ceiling:
            raise AssertionError(f"kept paging: {len(asked)} calls")
        return pages[len(asked) - 1] if len(asked) <= len(pages) else []

    monkeypatch.setattr(gh, "api", fake_api)
    return asked


def test_a_bare_list_endpoint_is_paged_until_the_first_empty_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The alerts endpoint answers with a list, not a wrapper — no `key` to unwrap."""
    asked = _pager(monkeypatch, [[{"n": 1}] * gh.PAGE_SIZE, [{"n": 2}], []])

    rows = gh.api_pages("repos/x/y/code-scanning/alerts?state=all")

    assert len(rows) == gh.PAGE_SIZE + 1
    assert len(asked) == 3, "did not stop at the first empty page"
    assert asked[0].endswith("?state=all&per_page=100&page=1"), asked[0]
    assert asked[2].endswith("&page=3"), asked[2]


def test_a_wrapped_endpoint_is_unwrapped_by_key(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _pager(monkeypatch, [{"workflow_runs": [{"id": 1}]}, {"workflow_runs": []}])

    rows = gh.api_pages("repos/x/y/actions/runs", key="workflow_runs")

    assert rows == [{"id": 1}]
    assert asked[0].endswith("?per_page=100&page=1"), "no query yet, so the joiner is `?`"


def test_a_limit_shrinks_the_last_page_and_stops_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asking for more than is left is the silent half-width the constant warns about."""
    full = [{"id": n} for n in range(gh.PAGE_SIZE)]
    asked = _pager(monkeypatch, [{"workflow_runs": full}, {"workflow_runs": full}])

    rows = gh.api_pages("repos/x/y/actions/runs", limit=150, key="workflow_runs")

    assert len(rows) == 150, "the last page must be trimmed to the limit"
    assert len(asked) == 2, "asked for a page past the limit"
    assert "per_page=100" in asked[0]
    assert "per_page=50" in asked[1], "the second page asked for more than was left"


def test_a_page_borrows_the_token_only_when_one_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forwarded only when set — so the one-argument fakes the census tests use still work."""
    lent: list[str | None] = []

    def fake_api(_path: str, **kwargs: Any) -> list[Any]:  # noqa: ANN401 — mirroring the wrapper
        lent.append(kwargs.get("token_env"))
        return []

    monkeypatch.setattr(gh, "api", fake_api)
    gh.api_pages("repos/x/y/alerts")
    gh.api_pages("repos/x/y/alerts", token_env=ALERTS_ENV)

    assert lent == [None, ALERTS_ENV]


def test_a_fake_that_takes_one_argument_is_still_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The census tests replace `api` with `def fake_api(path)` — that contract must hold."""
    monkeypatch.setattr(gh, "api", lambda _path: [])

    assert gh.api_pages("repos/x/y/alerts") == []
