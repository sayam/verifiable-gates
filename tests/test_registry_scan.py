"""The registry scanner, and the hand-written YAML reader underneath it.

Two things are being defended here, and the second is easy to forget.

**The scanner** holds a project's gate index to reality in four directions. Most
rules in this bundle end with "register it in your gates.yaml", and that
instruction means nothing unless something checks the register — so every one of
the four directions gets a case that breaks it alone.

**The reader** is hand-written and stdlib-only, because this file is shipped into
projects that have installed nothing. That makes it the riskiest code in the
bundle: a reader that is *more forgiving* than the real one reports green on files
it did not understand, and nothing about that looks wrong. Two defences —
everything outside the subset must **raise**, and on this repository's own files
the reader must agree with PyYAML value for value.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
import yaml

from verifiable_gates.checks import scan_gates_registry as scanner

ROOT = pathlib.Path(__file__).resolve().parent.parent

# A workflow with no `on:` never runs, and a gate naming a job in one is a row and
# nothing else — so the fixture every case here builds on carries a trigger, as a
# real workflow must (self-audit round 3, 2026-09-01).
PINNED = "on: push\njobs:\n  test:\n    steps:\n      - name: a step\n        run: true\n"


def build(
    root: pathlib.Path, files: dict[str, str], config: dict[str, Any] | None = None
) -> pathlib.Path:
    if config is not None:
        (root / "scaffold.json").write_text(json.dumps(config), encoding="utf-8")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def a_project(root: pathlib.Path, registry: str, **extra: str) -> pathlib.Path:
    """A project on the defaults. `tests_path` is *not* named here: a path the
    project names and does not have is a finding (round 26), and most cases below
    build no tests directory — the default `tests` is the same path, unnamed."""
    files = {".github/workflows/ci.yml": PINNED, "gates.yaml": registry, **extra}
    return build(root, files, {})


# ---------------------------------------------------------------- the reader


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a: 1\nb: two\n", {"a": "1", "b": "two"}),
        ("a:\n  b: c\n", {"a": {"b": "c"}}),
        ("a:\n  - x\n  - y\n", {"a": ["x", "y"]}),
        ("a: [x, y]\n", {"a": ["x", "y"]}),
        ("a: {j: test, s: [p, q]}\n", {"a": {"j": "test", "s": ["p", "q"]}}),
        ('a: "quoted: colon"\n', {"a": "quoted: colon"}),
        ("a: 1  # trailing comment\n", {"a": "1"}),
        ('a: "a # b"\n', {"a": "a # b"}),
        ("# only a comment\n", None),
        ("a: |\n  prose that is\n  not structure: really\nb: 2\n", {"a": "", "b": "2"}),
        ("- one\n- two\n", ["one", "two"]),
        ("a:\n- x\n", {"a": ["x"]}),
        ("a: {}\nb: []\n", {"a": {}, "b": []}),
    ],
    ids=[
        "flat",
        "nested",
        "sequence",
        "flow-list",
        "flow-map",
        "quoted-colon",
        "comment",
        "hash-in-quotes",
        "comment-only",
        "block-scalar",
        "top-list",
        "sequence-at-same-column",
        "empty-flow",
    ],
)
def test_the_reader_understands_the_subset(text: str, expected: object) -> None:
    assert scanner.load(text) == expected


@pytest.mark.parametrize("opener", ["---\n", "--- # the index\n", "\n---\n\n"])
def test_a_document_may_open_with_its_marker(opener: str) -> None:
    """`---` in front of the one document is YAML, not a second document (self-audit,
    2026-08-31: a workflow's first line made the whole index unreadable)."""
    assert scanner.load(opener + "a: 1\n") == {"a": "1"}


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("a:\tb\n", "tab"),
        ("a: 1\n---\nb: 2\n", "more than one document"),
        ("---\na: 1\n---\nb: 2\n", "more than one document"),
        ("---\na: 1\n...\n", "more than one document"),
        ("a: &anchor 1\n", "anchor"),
        ('a: "unclosed\n', "unclosed quote"),
        ("a: [x, y\n", "flow closed wrongly"),
        ("a: {x 1}\n", "missing ':'"),
        ("a: [x] extra\n", "trailing content"),
        ("a: 1\n   b: 2\n", "inconsistent indentation"),
    ],
    ids=[
        "tab",
        "multi-document",
        "opened-then-a-second-document",
        "end-marker",
        "anchor",
        "unclosed-quote",
        "unclosed-flow",
        "flow-without-colon",
        "trailing-after-flow",
        "ragged-indent",
    ],
)
def test_anything_outside_the_subset_is_loud(text: str, needle: str) -> None:
    """A reader more forgiving than the real one reports green on what it misread."""
    with pytest.raises(scanner.SubsetError, match=needle):
        scanner.load(text)


def test_a_block_scalar_body_is_skipped_not_parsed() -> None:
    """Prose inside `>-` contains colons and dashes; read as structure it invents gates."""
    text = "gates:\n  - id: a-rule\n    born_from: >-\n      a: not a key\n      - not an item\n"
    assert scanner.load(text) == {"gates": [{"id": "a-rule", "born_from": ""}]}


BLOCK_OPENER = scanner.BLOCK_SCALAR


def _count_block_scalars(text: str) -> int:
    return sum(1 for line in text.splitlines() if BLOCK_OPENER.search(line.split("#")[0].rstrip()))


def _key(key: object) -> str:
    """PyYAML follows YAML 1.1, where the bare key `on` is the boolean True.

    GitHub Actions writes `on:` and means the word. The subset reader keeps the
    word, which is right here; this puts PyYAML's answer back into the same shape
    so the comparison is about the reader and not about that quirk.
    """
    if isinstance(key, bool):
        return "on" if key else "off"
    return str(key)


def _walk(value: object, path: str = "") -> dict[str, object]:
    """Flatten to path → scalar, so a disagreement names where it is."""
    if isinstance(value, dict):
        return {
            k: v
            for key, item in value.items()
            for k, v in _walk(item, f"{path}.{_key(key)}").items()
        }
    if isinstance(value, list):
        return {
            k: v for i, item in enumerate(value) for k, v in _walk(item, f"{path}[{i}]").items()
        }
    return {path: None if value is None else str(value)}


def our_own_yaml() -> list[str]:
    """Every YAML file this repository keeps — found, not listed.

    The list used to be three names typed here, and one of them (`.github/dependabot.yml`)
    stopped existing when the machine that read it was turned off. A list somebody typed
    decays exactly like every other hand-kept list, which is a thing this project has
    already had to learn twice.

    **What the shipped reader is pointed at**, and nothing else: a gate registry and the
    workflow files, here and in the copies the bundle ships. `rules.yaml` is deliberately
    not among them — it uses a YAML anchor, and the subset reader refuses anchors out loud
    rather than guessing at them, which is the reader working, not drifting.
    """
    bundle = ROOT / "src" / "verifiable_gates"
    found = [ROOT / "gates.yaml", *(ROOT / ".github" / "workflows").glob("*.y*ml")]
    found += [bundle / "ci-template.yml", bundle / "gates.yaml.default"]
    return sorted(str(path.relative_to(ROOT)) for path in found)


@pytest.mark.parametrize("name", our_own_yaml())
def test_the_shipped_reader_agrees_with_pyyaml_on_our_own_files(name: str) -> None:
    """The guard that keeps a hand-written parser honest.

    This bundle has two readers of the same files — PyYAML in the package, this
    subset reader in the shipped scanner — and nothing stops them drifting apart
    except a test that reads the same bytes with both. Where they disagree, the
    shipped one is the one that lies, because it is the one that answers in a
    project where the other cannot be installed.

    **The reader discards the body of a block scalar on purpose** — it never uses
    those values, and skipping them correctly is what stops prose being read as
    structure. That is the one accepted divergence, so it is *measured* rather
    than waved through: the number of values it blanks must equal the number of
    block scalars in the file. A reader that started blanking anything else would
    fail here.
    """
    text = (ROOT / name).read_text(encoding="utf-8")
    ours = _walk(scanner.load(text))
    theirs = _walk(yaml.safe_load(text))

    assert ours.keys() == theirs.keys(), "the two readers disagree about the shape of the file"

    blanked = [path for path, value in ours.items() if value == "" and theirs[path] != ""]
    assert len(blanked) == _count_block_scalars(text), (
        f"the reader blanked {len(blanked)} values but the file has "
        f"{_count_block_scalars(text)} block scalars: {blanked}"
    )
    for path in ours:
        if path not in blanked:
            assert ours[path] == theirs[path], f"the readers disagree at {path}"


# ---------------------------------------------------------------- forward


def test_a_gate_pointing_at_a_job_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: absent}\n"
    )
    assert scanner.main(a_project(tmp_path, registry)) == 1
    assert "no workflow defines" in capsys.readouterr().out


def test_a_step_gate_naming_a_step_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: step\n"
        "    enforced_by: {job: test, step: no such step}\n"
    )
    assert scanner.main(a_project(tmp_path, registry)) == 1
    assert "has no step" in capsys.readouterr().out


def test_a_test_gate_naming_a_file_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_absent.py]}\n"
    )
    assert scanner.main(a_project(tmp_path, registry)) == 1
    assert "no such file" in capsys.readouterr().out


def test_a_test_gate_with_no_files_listed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test}\n"
    )
    assert scanner.main(a_project(tmp_path, registry)) == 1
    assert "must list test files" in capsys.readouterr().out


# ---------------------------------------------------------------- back


def test_a_job_that_no_gate_claims(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The direction that catches new work: a job arrives, and nothing says why."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: test}\n"
    )
    project = a_project(tmp_path, registry)
    (project / ".github" / "workflows" / "extra.yml").write_text(
        "jobs:\n  brand_new:\n    steps:\n      - run: true\n", encoding="utf-8"
    )
    assert scanner.main(project) == 1
    assert "job with no gate in the index: brand_new" in capsys.readouterr().out


def test_one_job_name_in_two_workflow_files_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The platform runs both; a dict keyed by name kept one, so the second was
    covered by the first's gate in silence."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: build}\n"
    )
    project = a_project(tmp_path, registry)
    for name in ("one.yml", "two.yml"):
        (project / ".github" / "workflows" / name).write_text(
            "jobs:\n  build:\n    steps:\n      - run: true\n", encoding="utf-8"
        )
    assert scanner.main(project) == 1
    out = capsys.readouterr().out
    assert "job build is defined in" in out
    assert "one.yml and " in out


def test_a_test_file_that_no_gate_claims(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_known.py]}\n"
    )
    project = a_project(
        tmp_path,
        registry,
        **{"tests/test_known.py": "", "tests/test_unclaimed.py": ""},
    )
    assert scanner.main(project) == 1
    assert "no gate claims this test file: tests/test_unclaimed.py" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["tests/unit/test_hidden.py", "tests/hidden_test.py"])
def test_a_test_file_pytest_collects_is_in_the_partition(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    """pytest collects `test_*.py` and `*_test.py` in every directory under the tests
    root; the partition reads the same (self-audit, 2026-08-31: both were outside it)."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_known.py]}\n"
    )
    project = a_project(tmp_path, registry, **{"tests/test_known.py": "", name: ""})
    assert scanner.main(project) == 1
    assert f"no gate claims this test file: {name}" in capsys.readouterr().out


def test_a_claimed_nested_test_file_and_a_helper_module_are_not_findings(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/unit/test_known.py]}\n"
    )
    project = a_project(
        tmp_path, registry, **{"tests/unit/test_known.py": "", "tests/unit/helpers.py": ""}
    )
    assert scanner.main(project) == 0
    assert capsys.readouterr().out == ""


def test_two_gates_claiming_the_same_test_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A partition, not a covering — two owners means neither is accountable."""
    registry = (
        "version: 1\ngates:\n"
        "  - id: rule-one\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_shared.py]}\n"
        "  - id: rule-two\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_shared.py]}\n"
    )
    project = a_project(tmp_path, registry, **{"tests/test_shared.py": ""})
    assert scanner.main(project) == 1
    assert "the partition is broken" in capsys.readouterr().out


def test_the_index_claiming_a_test_file_that_is_gone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_gone.py]}\n"
    )
    project = a_project(tmp_path, registry, **{"tests/test_here.py": ""})
    (project / "tests" / "test_here.py").write_text("", encoding="utf-8")
    assert scanner.main(project) == 1
    output = capsys.readouterr().out
    assert "claims a file that is gone" in output


# ---------------------------------------------------------------- a finding says where to go
# Self-audit round 22 (2026-09-04), F7: the first finding a stranger sees from a fresh
# install is `job with no gate in the index: test — give it one`, and it said neither
# which file nor what a row looks like. The header of the installed `gates.yaml` explains
# both — and the finding is read before the file.

ONE_JOB_GATE = (
    "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
    "    enforced_by: {job: test}\n"
)


def test_a_job_with_no_gate_is_told_the_row_to_add(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = a_project(tmp_path, ONE_JOB_GATE)
    (project / ".github" / "workflows" / "extra.yml").write_text(
        "jobs:\n  brand_new:\n    steps:\n      - run: true\n", encoding="utf-8"
    )
    assert scanner.main(project) == 1
    out = capsys.readouterr().out
    assert (
        "job with no gate in the index: brand_new — add a row to gates.yaml: id, title,"
        " kind: job, severity, enforced_by: {job: brand_new}"
    ) in out, out


def test_an_unclaimed_test_file_is_told_the_row_to_add(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = ONE_JOB_GATE.replace("kind: job", "kind: test").replace(
        "{job: test}", "{job: test, tests: [tests/test_known.py]}"
    )
    project = a_project(tmp_path, registry, **{"tests/test_known.py": "", "tests/test_new.py": ""})
    assert scanner.main(project) == 1
    out = capsys.readouterr().out
    assert (
        "no gate claims this test file: tests/test_new.py — add a row to gates.yaml with"
        " kind: test and enforced_by: {job: <the job that runs it>, tests: [tests/test_new.py]},"
        " or add it to a row's tests"
    ) in out, out


def test_a_claimed_file_that_is_gone_is_told_where_the_claim_is(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = ONE_JOB_GATE.replace("kind: job", "kind: test").replace(
        "{job: test}", "{job: test, tests: [tests/test_gone.py]}"
    )
    project = a_project(tmp_path, registry, **{"tests/test_here.py": ""})
    assert scanner.main(project) == 1
    out = capsys.readouterr().out
    assert (
        "the index claims a file that is gone: tests/test_gone.py — take it out of that"
        " row's tests in gates.yaml, or restore the file"
    ) in out, out


def test_a_gate_pointing_nowhere_is_told_what_was_read_and_where_to_fix_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = ONE_JOB_GATE.replace("{job: test}", "{job: absent}")
    assert scanner.main(a_project(tmp_path, registry)) == 1
    out = capsys.readouterr().out
    assert (
        "a-rule: points at job 'absent', which no workflow defines — rename it in"
        " gates.yaml, or add the job to a workflow under .github/workflows"
    ) in out, out


def test_the_finding_names_the_index_as_the_project_named_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project that moved its registry (`gates_path`) is pointed at that file, not at
    the default name — a pointer at a file that is not there is no pointer."""
    registry = ONE_JOB_GATE.replace("{job: test}", "{job: absent}")
    files = {".github/workflows/ci.yml": PINNED, "docs/gates.yaml": registry}
    project = build(tmp_path, files, {"gates_path": "docs/gates.yaml", "tests_path": "tests"})
    assert scanner.main(project) == 1
    out = capsys.readouterr().out
    assert "rename it in docs/gates.yaml, or add the job to a workflow" in out, out
    assert "in gates.yaml," not in out, out


# ---------------------------------------------------------------- shape


BAD_ID_ROW = "  - id: Not_Kebab\n    title: t\n    kind: job\n    enforced_by: {job: test}\n"
GOOD_ROW = "  - id: a-rule\n    title: t\n    kind: job\n    enforced_by: {job: test}\n"
DUPLICATE_ROWS = GOOD_ROW + GOOD_ROW


@pytest.mark.parametrize(
    ("rows", "needle"),
    [
        ("  - just a string\n", "not a mapping"),
        (
            "  - id: Not_Kebab\n    title: t\n    kind: job\n    enforced_by: {job: test}\n",
            "kebab-case",
        ),
        (DUPLICATE_ROWS, "duplicate id"),
        ("  - id: a-rule\n    kind: job\n    enforced_by: {job: test}\n", "no title"),
        ("  - id: a-rule\n    title: t\n    kind: guess\n    enforced_by: {job: test}\n", "kind"),
        ("  - id: a-rule\n    title: t\n    kind: job\n", "must name the job"),
    ],
    ids=["not-a-mapping", "bad-id", "duplicate-id", "no-title", "bad-kind", "no-enforcer"],
)
def test_a_malformed_row_is_reported(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], rows: str, needle: str
) -> None:
    assert scanner.main(a_project(tmp_path, f"version: 1\ngates:\n{rows}")) == 1
    assert needle in capsys.readouterr().out


# ---------------------------------------------------------------- the whole file


def test_an_index_that_matches_reality_is_quiet(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction: a rule that fires on everything is not a rule."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_known.py]}\n"
    )
    project = a_project(tmp_path, registry, **{"tests/test_known.py": ""})
    assert scanner.main(project) == 0
    assert "gates-registry-total" not in capsys.readouterr().out


def test_no_index_is_not_applicable(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    build(tmp_path, {".github/workflows/ci.yml": PINNED}, {})
    assert scanner.main(tmp_path) == 0
    assert capsys.readouterr().out.startswith("NA:")


def test_an_index_named_in_scaffold_and_missing_is_a_finding_not_na(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`gates_path` the project wrote and does not have is a broken configuration.

    Same rule as every scaffold path (an outside audit on 2026-08-29 found the
    Dockerfile scanner answering NA to a configured path that was not there):
    an unconfigured, absent index is "no index yet"; a configured, absent one is
    a finding, or one wrong line would turn "checked" into "nothing to check".
    """
    files = {".github/workflows/ci.yml": PINNED, "gates.yaml": "version: 1\ngates: []\n"}
    build(tmp_path, files, {"gates_path": "docs/gates.yaml"})
    assert scanner.main(tmp_path) == 1
    out = capsys.readouterr().out
    assert out.startswith("gates-registry-total: ")
    assert "gates_path" in out
    assert "docs/gates.yaml" in out
    assert "NA:" not in out


# One job gate on the fixture's one job — an index that matches reality, so the only
# thing left for the scanner to say is about the tests.
A_JOB_GATE = (
    "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
    "    enforced_by: {job: test}\n"
)


def test_a_tests_path_named_in_scaffold_and_missing_is_a_finding_not_silence(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tests_path` the project wrote and does not have is a broken configuration.

    The same rule as `gates_path` above, and it was not held here: on a brownfield
    where the test-file half of this gate is the whole first-day wall (627 of
    django's 772 findings, self-audit round 26, 2026-09-05), pointing `tests_path`
    at a directory that does not exist made every one of those findings vanish
    with no sentence saying the tests were not read — the cheapest move, and a
    silent one. A named path that is missing is a finding; an unnamed, absent
    `tests` stays the NA half it always was.
    """
    files = {".github/workflows/ci.yml": PINNED, "gates.yaml": A_JOB_GATE}
    build(tmp_path, files, {"tests_path": "no-such-dir"})
    assert scanner.main(tmp_path) == 1
    out = capsys.readouterr().out
    assert (
        "gates-registry-total: scaffold.json names tests_path no-such-dir, which is not there"
        in out
    )
    assert "NA:" not in out


def test_an_unnamed_absent_tests_directory_is_still_the_quiet_half(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The default `tests` not being there is "nothing of that kind", not a finding."""
    files = {".github/workflows/ci.yml": PINNED, "gates.yaml": A_JOB_GATE}
    build(tmp_path, files, {})
    assert scanner.main(tmp_path) == 0
    assert "tests_path" not in capsys.readouterr().out


def test_an_empty_index_enforces_nothing_and_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert scanner.main(a_project(tmp_path, "version: 1\ngates: []\n")) == 1
    assert "enforces nothing" in capsys.readouterr().out


def test_an_index_missing_its_gates_key(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert scanner.main(a_project(tmp_path, "version: 1\n")) == 1
    assert "must have a 'gates' key" in capsys.readouterr().out


def test_an_index_that_cannot_be_read_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unreadable is a finding, never a reason to skip and report clean."""
    assert scanner.main(a_project(tmp_path, "gates:\n\t- id: x\n")) == 1
    assert "could not be read" in capsys.readouterr().out


def test_a_workflow_that_cannot_be_read_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: test}\n"
    )
    project = a_project(tmp_path, registry)
    (project / ".github" / "workflows" / "broken.yml").write_text(
        "jobs:\n\tx: 1\n", encoding="utf-8"
    )
    assert scanner.main(project) == 1
    assert "could not be read" in capsys.readouterr().out


def test_a_workflow_that_is_not_a_mapping_is_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: test}\n"
    )
    project = a_project(tmp_path, registry)
    (project / ".github" / "workflows" / "list.yml").write_text("- a\n- b\n", encoding="utf-8")
    assert scanner.main(project) == 1
    assert "not a mapping" in capsys.readouterr().out


def test_the_index_path_can_be_configured(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: test}\n"
    )
    build(
        tmp_path,
        {".github/workflows/ci.yml": PINNED, "docs/gates.yaml": registry},
        {"gates_path": "docs/gates.yaml"},
    )
    assert scanner.main(tmp_path) == 0
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------- the reader's edges
#
# Found by coverage, not by imagination. Each is a shape a real file can take,
# and a reader that mishandles one of them misreads the file *quietly* — which is
# the whole reason this subset raises instead of guessing.


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a:\n  -\n    b: c\n", {"a": [{"b": "c"}]}),
        ("a:\n  -\n", {"a": [None]}),
        ('a: [x, "y, z"]\n', {"a": ["x", "y, z"]}),
        ('a: {k: "v: w"}\n', {"a": {"k": "v: w"}}),
        ("a: null\n", {"a": None}),
        ("a: ~\n", {"a": None}),
        ("a: true\nb: false\n", {"a": True, "b": False}),
        ('"quoted key": v\n', {"quoted key": "v"}),
        ("a: {k: [x]}\n", {"a": {"k": ["x"]}}),
    ],
    ids=[
        "dash-then-indented-map",
        "dash-with-nothing",
        "quoted-item-in-flow-list",
        "quoted-value-in-flow-map",
        "null",
        "tilde-null",
        "booleans",
        "quoted-key",
        "nested-flow",
    ],
)
def test_the_reader_handles_the_shapes_a_real_file_takes(text: str, expected: object) -> None:
    assert scanner.load(text) == expected


def test_an_anchor_at_the_start_of_a_line_is_loud() -> None:
    """The value-position check misses this one, and vice versa — both are needed."""
    with pytest.raises(scanner.SubsetError, match="anchor"):
        scanner.load("&anchor\n")


def test_an_unclosed_quote_inside_a_flow_is_loud() -> None:
    with pytest.raises(scanner.SubsetError, match="unclosed quote"):
        scanner.load('a: [x, "y]\n')


def test_a_step_gate_that_names_a_step_that_exists_is_quiet(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The passing branch of the step check — without it, only failure is proven."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: step\n"
        "    enforced_by: {job: test, step: a step}\n"
    )
    assert scanner.main(a_project(tmp_path, registry)) == 0
    assert capsys.readouterr().out == ""


def test_a_flow_mapping_can_be_a_list_item() -> None:
    """`- {id: x}` — the compact way to write a row, and the only shape that makes
    `_split_key` count brackets. Without the counting it would split at the colon
    *inside* the braces and read the row as a key nobody wrote."""
    assert scanner.load("gates:\n  - {id: a-rule, kind: job}\n") == {
        "gates": [{"id": "a-rule", "kind": "job"}]
    }


def test_a_flow_list_can_be_a_list_item() -> None:
    assert scanner.load("a:\n  - [x, y]\n") == {"a": [["x", "y"]]}


def test_a_gate_listing_tests_under_another_kind(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The files above are looked for only while `kind` reads `test`, and the harness
    runs a gate only while it reads the same. A row listing tests under any other kind
    is a gate nothing runs and nothing looks for, still counted by the index — one word
    on one row, every reader green (self-audit round 2, 2026-08-31)."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n"
        "    enforced_by: {job: test, tests: [tests/test_a.py]}\n"
    )

    assert scanner.main(a_project(tmp_path, registry)) == 1
    assert "lists tests" in capsys.readouterr().out


# ---------------------------------------------------------------- teeth


TOOTHLESS_JOB = (
    "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: job\n    enforced_by: {job: x}\n"
)
STEPS = "    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"


@pytest.mark.parametrize(
    ("workflow", "said"),
    [
        (f"name: t\njobs:\n  x:\n{STEPS}", "no trigger"),
        (f"name: t\non: push\njobs:\n  x:\n    if: false\n{STEPS}", "`if: false`"),
        (
            f"name: t\non: push\njobs:\n  x:\n    continue-on-error: true\n{STEPS}",
            "cannot fail the run",
        ),
    ],
    ids=["no-trigger", "if-false", "continue-on-error"],
)
def test_a_gate_whose_job_cannot_turn_the_build_red(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], workflow: str, said: str
) -> None:
    """A gate names a job so that the job fails when the rule is broken. Three shapes take
    that away without touching the index — and adding `continue-on-error: true` to this
    repository's own `test` job, which forty-five of its fifty-four gates name, left the
    whole suite, every reader and this scanner green (self-audit round 3, 2026-09-01)."""
    root = a_project(tmp_path, TOOTHLESS_JOB)
    (root / ".github" / "workflows" / "ci.yml").write_text(workflow, encoding="utf-8")

    assert scanner.main(root) == 1
    assert said in capsys.readouterr().out


def test_a_step_gate_whose_step_cannot_fail(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One level down: the step a `kind: step` gate names carrying `continue-on-error`
    takes the teeth from that gate while the job around it keeps its own."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: step\n"
        "    enforced_by: {job: x, step: lint}\n"
    )
    root = a_project(tmp_path, registry)
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "name: t\non: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - name: lint\n        continue-on-error: true\n        run: echo\n",
        encoding="utf-8",
    )

    assert scanner.main(root) == 1
    assert "cannot fail" in capsys.readouterr().out


def test_a_job_that_can_fail_is_left_alone(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction, and the shapes deliberately not judged: a workflow started
    only by `workflow_dispatch` or a schedule is how this repository runs `release-sign`
    and `posture`, and an `if:` holding an expression is not a literal false."""
    root = a_project(tmp_path, TOOTHLESS_JOB)
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "name: t\non: workflow_dispatch\njobs:\n  x:\n"
        "    if: github.event_name == 'push'\n" + STEPS,
        encoding="utf-8",
    )

    assert scanner.main(root) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "trigger",
    [
        '"on": push',
        "'on': push",
        "on:\n  push:\n    branches: [main]",
        "on: [push, pull_request]",
        "on: push  # every push",
    ],
    ids=["quoted", "single-quoted", "mapping", "flow-list", "trailing-comment"],
)
def test_every_spelling_of_a_trigger_is_a_trigger(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], trigger: str
) -> None:
    """The check for a workflow with no trigger must not invent one: a quoted key or a
    mapping is a trigger, and reporting it as missing would be a false red on a project
    that did nothing wrong — the failure mode this round found in other scanners."""
    root = a_project(tmp_path, TOOTHLESS_JOB)
    (root / ".github" / "workflows" / "ci.yml").write_text(
        f"name: t\n{trigger}\njobs:\n  x:\n" + STEPS, encoding="utf-8"
    )

    assert scanner.main(root) == 0
    assert capsys.readouterr().out == ""


def test_a_workflow_it_may_not_read_is_named(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The route this reader already had for a workflow it cannot parse now takes one it
    is not allowed to open, instead of a raw `PermissionError` (round 5, 2026-09-01)."""
    root = a_project(tmp_path, TOOTHLESS_JOB)
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.chmod(0o000)

    try:
        assert scanner.main(root) == 1
    finally:
        workflow.chmod(0o644)

    assert "could not be read" in capsys.readouterr().out


def test_a_registry_it_may_not_read_is_named(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """And the index itself, on the same route."""
    root = a_project(tmp_path, TOOTHLESS_JOB)
    (root / "gates.yaml").chmod(0o000)

    try:
        assert scanner.main(root) == 1
    finally:
        (root / "gates.yaml").chmod(0o644)

    assert "could not be read" in capsys.readouterr().out


# ---------------------------------------------------------------- a walk that saw less


def test_a_workflow_directory_it_cannot_enter_is_not_an_empty_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`glob` discards the `OSError`s it meets, so a directory this scanner may not open
    came back as *no workflows* — and no workflows means no jobs, which means every gate
    in the index names a job that is not there, or none does (self-audit round 19,
    2026-09-02). A directory that will not open is the third answer, not an empty one."""
    root = a_project(tmp_path, TOOTHLESS_JOB)
    closed = root / ".github" / "workflows"
    closed.chmod(0o000)

    try:
        code = scanner.main(root)
    finally:
        closed.chmod(0o755)

    assert code == 2, "a directory the scanner could not open was read as an empty one"
    assert "cannot read the tree" in capsys.readouterr().err


def test_a_tests_directory_it_cannot_enter_is_not_an_empty_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other walk: the partition holds the index against the test files on disk, and a
    tests directory it could not enter made every claimed file look like one that is gone."""
    registry = (
        "version: 1\ngates:\n  - id: a-rule\n    title: t\n    kind: test\n"
        "    enforced_by: {job: test, tests: [tests/test_a.py]}\n"
    )
    root = a_project(tmp_path, registry, **{"tests/test_a.py": "def test_a() -> None:\n    pass\n"})
    closed = root / "tests"
    closed.chmod(0o000)

    try:
        code = scanner.main(root)
    finally:
        closed.chmod(0o755)

    assert code == 2, "a tests directory it could not enter was read as one holding nothing"
    assert "cannot read the tree" in capsys.readouterr().err
