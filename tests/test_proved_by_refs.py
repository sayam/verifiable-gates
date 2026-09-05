"""Every `proved_by.ref` resolved against the platform — on fakes; the live read is posture's cron.

Role: the offline half of the gate `proved-by-refs-resolve-on-the-platform`. Nothing here
reaches GitHub: `gh.api` and `gh.run` are replaced with answers that say what the platform
said on 2026-09-05 (200 for a merged pull request, 404 for a run that is not there, 410 for
a log past the retention window) so the decider's three exit codes are pinned to the cases.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from verifiable_gates import gh, proved_by_refs

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "sayam/verifiable-gates"


def refused(status: str) -> Callable[..., object]:
    def _refuse(*_args: object, **_kwargs: object) -> object:
        raise PermissionError(f"`gh api x` failed: gh: Not Found (HTTP {status})")

    return _refuse


def registry(tmp_path: pathlib.Path, refs: list[tuple[str, str]]) -> pathlib.Path:
    rows = "".join(
        f"  - id: {gid}\n    title: t\n    kind: test\n    severity: blocking\n"
        f"    enforced_by: {{job: test}}\n    layer: internal\n    pillar: devx\n"
        f"    proved_by:\n      - {{kind: mutation, ref: {ref}, date: 2026-09-05, caught: c}}\n"
        for gid, ref in refs
    )
    path = tmp_path / "gates.yaml"
    path.write_text(f"version: 1\ngates:\n{rows}", encoding="utf-8")
    return path


# ---------------------------------------------------------------- the shapes


def test_a_bare_ref_belongs_to_the_default_repository() -> None:
    ref = proved_by_refs.parse("pr/245")
    assert (ref.repo, ref.kind, ref.number) == (REPO, "pr", "245")
    assert ref.path == f"repos/{REPO}/pulls/245"


def test_a_prefixed_ref_names_its_own_repository() -> None:
    ref = proved_by_refs.parse("sayam/flask-todolist#pr/151")
    assert ref.repo == "sayam/flask-todolist"
    assert ref.path == "repos/sayam/flask-todolist/pulls/151"


def test_runs_and_commits_have_paths_and_an_unknown_shape_has_none() -> None:
    assert proved_by_refs.parse("run/33244862480").path == f"repos/{REPO}/actions/runs/33244862480"
    assert proved_by_refs.parse("commit/e20fd24").path == f"repos/{REPO}/commits/e20fd24"
    assert proved_by_refs.parse("issue/7").path is None


def test_every_ref_in_this_registry_has_a_shape_the_platform_can_be_asked_about() -> None:
    """The schema holds the shape; this holds that the resolver can ask about every shape."""
    cited = proved_by_refs.collect(ROOT / "gates.yaml")
    assert cited, "the registry cites no proof at all"
    unaskable = [text for text in cited if proved_by_refs.parse(text).path is None]
    assert unaskable == []


def test_collect_groups_the_gates_behind_each_distinct_ref(tmp_path: pathlib.Path) -> None:
    path = registry(tmp_path, [("a", "pr/1"), ("b", "pr/1"), ("c", "run/9")])
    assert proved_by_refs.collect(path) == {"pr/1": ["a", "b"], "run/9": ["c"]}


# ---------------------------------------------------------------- resolving one ref


def test_a_pull_request_that_answers_is_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gh, "api", lambda _path: {"state": "closed"})
    assert proved_by_refs.resolve(proved_by_refs.parse("pr/245")) is None


def test_a_ref_the_platform_has_nothing_for_is_a_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """RC-12 as filed: `pr/999999999` passed the schema; here it is the sentence."""
    monkeypatch.setattr(gh, "api", refused("404"))
    why = proved_by_refs.resolve(proved_by_refs.parse("pr/999999999"))
    assert why is not None
    assert "404" in why
    assert "pulls/999999999" in why


def test_a_refusal_that_is_not_a_404_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token without scope must read as "could not look", never as "nothing there"."""
    monkeypatch.setattr(gh, "api", refused("403"))
    with pytest.raises(PermissionError):
        proved_by_refs.resolve(proved_by_refs.parse("pr/245"))


def test_a_run_whose_log_is_still_readable_is_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[list[str]] = []

    def run(args: list[str]) -> str:
        asked.append(args)
        return ""

    monkeypatch.setattr(gh, "api", lambda _path: {"status": "completed"})
    monkeypatch.setattr(gh, "run", run)
    assert proved_by_refs.resolve(proved_by_refs.parse("run/33244862480")) is None
    assert asked == [["api", f"repos/{REPO}/actions/runs/33244862480/logs", "--silent"]]


def test_a_run_whose_log_is_gone_is_a_finding_that_says_what_to_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub keeps the run and answers 410 for its log after the retention window."""
    monkeypatch.setattr(gh, "api", lambda _path: {"status": "completed"})
    monkeypatch.setattr(gh, "run", refused("410"))
    why = proved_by_refs.resolve(proved_by_refs.parse("run/33244862480"))
    assert why is not None
    assert "410" in why
    assert "rewrite the ref to the pr/N" in why


def test_a_run_that_never_started_needs_no_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """`startup_failure` keeps no log — the record and its conclusion are the proof
    (measured 2026-09-05 on the release run the Actions policy refused)."""
    asked: list[list[str]] = []
    monkeypatch.setattr(gh, "api", lambda _path: {"conclusion": "startup_failure"})
    monkeypatch.setattr(gh, "run", asked.append)
    assert proved_by_refs.resolve(proved_by_refs.parse("run/33937392727")) is None
    assert asked == [], "the log was asked for although a run that never started has none"


def test_a_run_with_no_log_at_all_is_a_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gh, "api", lambda _path: {"status": "completed"})
    monkeypatch.setattr(gh, "run", refused("404"))
    why = proved_by_refs.resolve(proved_by_refs.parse("run/1"))
    assert why is not None
    assert "no log" in why


def test_a_log_refusal_that_is_neither_gone_nor_missing_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gh, "api", lambda _path: {"status": "completed"})
    monkeypatch.setattr(gh, "run", refused("401"))
    with pytest.raises(PermissionError):
        proved_by_refs.resolve(proved_by_refs.parse("run/1"))


def test_a_shape_the_module_cannot_ask_about_is_a_finding_not_a_pass() -> None:
    why = proved_by_refs.resolve(proved_by_refs.parse("issue/7"))
    assert why is not None
    assert "cannot ask" in why


def test_the_status_is_read_out_of_gh_messages_in_their_shapes() -> None:
    assert proved_by_refs.status_of(PermissionError("gh: Not Found (HTTP 404)")) == "404"
    assert proved_by_refs.status_of(PermissionError('{"status":"410"}')) == "410"
    assert proved_by_refs.status_of(PermissionError("something else entirely")) == "error"


# ---------------------------------------------------------------- the three exit codes


def test_a_registry_where_everything_resolves_exits_zero_and_counts(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry(tmp_path, [("a", "pr/1"), ("b", "pr/1"), ("c", "run/9")])
    monkeypatch.setattr(gh, "api", lambda _path: {})
    monkeypatch.setattr(gh, "run", lambda _args: "")
    assert proved_by_refs.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 distinct refs across 3 rows" in out
    assert "1 of them runs" in out


def test_one_missing_ref_exits_one_and_names_the_gates_that_cite_it(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry(tmp_path, [("a", "pr/1"), ("b", "pr/999999999"), ("c", "pr/999999999")])

    def api(path: str) -> object:
        if path.endswith("/999999999"):
            raise PermissionError("gh: Not Found (HTTP 404)")
        return {}

    monkeypatch.setattr(gh, "api", api)
    assert proved_by_refs.main(["--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "FAIL pr/999999999: the platform answers 404" in err
    assert "cited by: b, c" in err


def test_a_platform_that_cannot_be_asked_exits_two(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No token, a timeout: "could not look" is exit 2, never 0 and never a finding."""
    registry(tmp_path, [("a", "pr/1")])
    monkeypatch.setattr(gh, "api", refused("403"))
    assert proved_by_refs.main(["--root", str(tmp_path)]) == 2
    assert "could not ask the platform" in capsys.readouterr().err

    def timed_out(_path: str) -> object:
        raise RuntimeError("did not answer within 30 seconds")

    monkeypatch.setattr(gh, "api", timed_out)
    assert proved_by_refs.main(["--root", str(tmp_path)]) == 2


def test_an_unreadable_registry_exits_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert proved_by_refs.main(["--root", str(tmp_path)]) == 2
    assert "cannot read" in capsys.readouterr().err
    (tmp_path / "gates.yaml").write_text("gates: [{id: a, proved_by: [{}]}]\n", encoding="utf-8")
    assert proved_by_refs.main(["--root", str(tmp_path)]) == 2


def test_posture_runs_the_resolver_live_with_the_workflow_token() -> None:
    """The live half: a step in posture.yml, on the cron and on every push to main."""
    text = (ROOT / ".github" / "workflows" / "posture.yml").read_text(encoding="utf-8")
    assert "python -m verifiable_gates.proved_by_refs --root ." in text
