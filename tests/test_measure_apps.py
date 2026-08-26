"""One battery over every arm, and the ways a comparison stops being one.

Nothing here checks that the numbers are *good*. It checks that they are
comparable: the same configuration everywhere, the measurer's own work removed
from the side that received it, and three answers per scanner rather than two.

The rules that cost the bundle are the ones tested hardest, because those are the
ones a person with a stake in the answer is tempted to skip.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import pathlib

from verifiable_gates import measure_apps

APP = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": "def create_app():\n    return None\n",
}


def plant(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


# ----------------------------------------------- the measurer's own work comes out


def test_what_the_installer_added_is_removed_before_measuring(tmp_path: pathlib.Path) -> None:
    """**The direction that costs the bundle**, which is the correct direction here.

    The arm that installed the bundle receives tooling, a config and a starting
    workflow. Counting those as its own output is adding the measurer's work to
    one side of the measurer's own experiment.
    """
    app = plant(tmp_path / "app1", {**APP, "tools/overlay.json": "{}", "scaffold.json": "{}"})
    (app / ".github" / "workflows").mkdir(parents=True)
    (app / ".github" / "workflows" / "gates.yml").write_text("on: push\n", encoding="utf-8")

    staged = measure_apps.staged(app, tmp_path / "staging")

    assert not (staged / "tools").exists()
    assert not (staged / "scaffold.json").exists()
    assert not (staged / ".github" / "workflows" / "gates.yml").exists()
    assert (staged / "run.py").is_file(), "the app's own work has to survive"


def test_an_app_that_installed_nothing_loses_nothing(tmp_path: pathlib.Path) -> None:
    """Removing what was never there takes nothing away from the arm without it."""
    app = plant(tmp_path / "app1", {**APP, "tools/mine.py": "# the app's own tool\n"})

    staged = measure_apps.staged(app, tmp_path / "staging")

    assert (staged / "tools" / "mine.py").is_file()


def test_the_original_is_never_touched(tmp_path: pathlib.Path) -> None:
    """Measuring must not edit what is being measured — the next run reads it too."""
    app = plant(tmp_path / "app1", {**APP, "tools/overlay.json": "{}"})

    measure_apps.staged(app, tmp_path / "staging")

    assert (app / "tools" / "overlay.json").is_file()


# --------------------------------------------------------- three answers, not two


def test_a_scanner_that_had_nothing_to_look_at_says_so(tmp_path: pathlib.Path) -> None:
    """**`na` never collapses into `ok`.**

    "There was nothing of that kind" and "we looked and it was clean" are different
    facts, and folding them together flatters the smallest app in the set.
    """
    bundle = _fake_bundle(tmp_path, {"scan_nothing.py": _scanner("NA: no such thing here", 0)})
    app = plant(tmp_path / "app1", APP)

    assert measure_apps.run_scans(app, bundle) == {"nothing": "na"}


def test_a_clean_scanner_and_a_finding_are_told_apart(tmp_path: pathlib.Path) -> None:
    bundle = _fake_bundle(
        tmp_path,
        {
            "scan_clean.py": _scanner("", 0),
            "scan_dirty.py": _scanner("first thing\nsecond thing", 1),
        },
    )
    app = plant(tmp_path / "app1", APP)

    assert measure_apps.run_scans(app, bundle) == {"clean": "ok", "dirty": 2}


def test_every_app_is_scanned_with_the_same_configuration(tmp_path: pathlib.Path) -> None:
    """A different config is a different gate, and then the arms are not comparable."""
    bundle = _fake_bundle(tmp_path, {"scan_clean.py": _scanner("", 0)})
    app = plant(tmp_path / "app1", {**APP, "scaffold.json": '{"theirs": true}'})

    measure_apps.run_scans(app, bundle)

    assert json.loads((app / "scaffold.json").read_text(encoding="utf-8")) == {"ours": True}


# ------------------------------------------------------- the outside scanner


def test_an_outside_scanner_that_was_not_asked_for_is_skipped(tmp_path: pathlib.Path) -> None:
    """**Skipped is reported as skipped, never as zero.**

    Zero findings and no scan look identical in a table, and only one of them is
    evidence.
    """
    assert measure_apps.run_scanner(tmp_path, None, []) is None


def test_the_scanner_binary_comes_from_an_argument(tmp_path: pathlib.Path) -> None:
    """A runner named by the environment can change without appearing in the command."""
    stub = tmp_path / "stub"
    stub.write_text("#!/bin/sh\necho '{\"results\": [1, 2, 3]}'\n", encoding="utf-8")
    stub.chmod(0o755)
    app = plant(tmp_path / "app1", APP)

    assert measure_apps.run_scanner(app, stub, ["p/one", "p/two"]) == 3


def test_a_scanner_path_that_is_not_there_is_loud(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        measure_apps.run_scanner(tmp_path, tmp_path / "absent", [])


def test_a_scanner_that_broke_is_loud_rather_than_zero(tmp_path: pathlib.Path) -> None:
    """Exit 0 and 1 are "clean" and "found things"; anything else is the tool failing."""
    stub = tmp_path / "stub"
    stub.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    stub.chmod(0o755)
    app = plant(tmp_path / "app1", APP)

    with pytest.raises(SystemExit, match="the scanner failed"):
        measure_apps.run_scanner(app, stub, [])


# ------------------------------------------------------------ one battery, all arms


def test_the_battery_cannot_be_changed_between_arms() -> None:
    """Varying the instrument mid-run is the failure this module exists to avoid.

    Frozen so that a caller holding one cannot quietly point the second arm at a
    different scanner or a different bundle.
    """
    battery = measure_apps.Battery(configs=("p/one",))

    assert battery.scanner is None
    assert dataclasses.fields(battery), "Battery stopped being a record of the settings"
    with pytest.raises(dataclasses.FrozenInstanceError):
        battery.configs = ("p/two",)  # type: ignore[misc]


def test_a_row_counts_only_the_files_the_probe_read(tmp_path: pathlib.Path) -> None:
    """The counter and the instrument have to be looking at one tree.

    Otherwise "lines the agent wrote" quietly includes an environment somebody left
    in the directory, and the arms stop being comparable at all.
    """
    bundle = _fake_bundle(tmp_path, {"scan_clean.py": _scanner("", 0)})
    app = plant(
        tmp_path / "app1",
        {**APP, ".venv/lib/site-packages/huge.py": "x = 1\n" * 500},
    )

    row = measure_apps.measure(
        app, "ctrl", tmp_path / "staging", measure_apps.Battery(bundle=bundle)
    )

    assert row["py_files"] == 2, "an environment in the tree was counted as the app's work"
    assert row["py_lines"] < 10


def test_a_row_records_which_arm_it_came_from(tmp_path: pathlib.Path) -> None:
    bundle = _fake_bundle(tmp_path, {"scan_clean.py": _scanner("", 0)})
    app = plant(tmp_path / "app1", APP)

    row = measure_apps.measure(
        app, "review", tmp_path / "staging", measure_apps.Battery(bundle=bundle)
    )

    assert row["arm"] == "review"
    assert row["app"] == "app1"
    assert row["overlay_installed"] is False
    assert row["scanner"] is None


def test_the_table_says_what_was_skipped_and_what_was_not_applicable() -> None:
    """A check silent about its own gaps is one nobody can read honestly."""
    rows: list[dict[str, Any]] = [
        {
            "arm": "ctrl",
            "app": "app1",
            "py_lines": 100,
            "gate_findings": 2,
            "asvs_pass": 8,
            "asvs_na": ["V4.1.1-ownership-filter"],
            "scanner": None,
        }
    ]

    printed = measure_apps.table(rows)

    assert "skipped" in printed
    assert "+1 n/a" in printed


# --------------------------------------------------------------------- helpers


def _scanner(output: str, code: int) -> str:
    """A stand-in scanner: prints what it was told to, exits how it was told to."""
    return f"import sys\n\nprint({output!r})\nsys.exit({code})\n"


def _fake_bundle(root: pathlib.Path, scanners: dict[str, str]) -> pathlib.Path:
    """A bundle laid out the way the real one is, with scanners we control."""
    bundle = root / "bundle"
    (bundle / "checks").mkdir(parents=True)
    for name, body in scanners.items():
        (bundle / "checks" / name).write_text(body, encoding="utf-8")
    (bundle / "scaffold.json.default").write_text('{"ours": true}', encoding="utf-8")
    return bundle


def test_the_scanners_used_are_the_bundle_s_own(tmp_path: pathlib.Path) -> None:
    """**Measuring with a copy measures something other than what the report names.**"""
    bundle = _fake_bundle(tmp_path, {"scan_a.py": _scanner("", 0), "scan_b.py": _scanner("", 0)})

    found = [path.name for path in measure_apps.checkers(bundle)]

    assert found == ["scan_a.py", "scan_b.py"]


def test_a_command_declares_a_time_budget(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a timeout the wait is forever, which in CI is a job that never ends."""
    budget: dict[str, object] = {}
    real = subprocess.run

    def watched(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        budget.update(kwargs)
        return real(argv, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(subprocess, "run", watched)
    bundle = _fake_bundle(tmp_path, {"scan_clean.py": _scanner("", 0)})
    measure_apps.run_scans(plant(tmp_path / "app1", APP), bundle)

    assert budget["timeout"] == measure_apps.CHECKER_TIMEOUT_SECONDS


# --------------------------------------------------------------- the command


def test_a_scanner_path_that_is_a_directory_is_loud(tmp_path: pathlib.Path) -> None:
    """Existing is not enough — a directory cannot be started."""
    with pytest.raises(SystemExit, match="not a file"):
        measure_apps.run_scanner(tmp_path, tmp_path, [])


def test_the_command_walks_every_arm_and_every_app(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**One row per app, every arm** — a runner that skips an arm reports a gap as parity."""
    bundle = _fake_bundle(tmp_path, {"scan_clean.py": _scanner("", 0)})
    monkeypatch.setattr(measure_apps, "BUNDLE", bundle)
    root = tmp_path / "apps"
    for arm in ("ctrl", "skill"):
        for name in ("app1", "app2"):
            plant(root / arm / name, APP)
    out = tmp_path / "rows.json"

    assert measure_apps.main([str(root), "--output", str(out)]) == 0

    printed = capsys.readouterr().out
    assert printed.count("| ctrl |") == 2
    assert printed.count("| skill |") == 2
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert [(row["arm"], row["app"]) for row in rows] == [
        ("ctrl", "app1"),
        ("ctrl", "app2"),
        ("skill", "app1"),
        ("skill", "app2"),
    ]


def test_the_command_writes_nothing_when_not_asked_to(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _fake_bundle(tmp_path, {"scan_clean.py": _scanner("", 0)})
    monkeypatch.setattr(measure_apps, "BUNDLE", bundle)
    root = tmp_path / "apps"
    plant(root / "ctrl" / "app1", APP)

    assert measure_apps.main([str(root)]) == 0
    assert capsys.readouterr().out.count("| ctrl |") == 1
    assert not list(tmp_path.glob("*.json"))
