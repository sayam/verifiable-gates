"""The manifest schema, and what it refuses.

`manifest.problems()` is what stands between "the bundle installed" and "the
bundle installed something that works". Each rule gets a case that breaks it
alone, because a validator that only ever sees valid input is a validator nobody
has watched work.

The `suite`-with-a-script case is the subtle one. A suite gate is by definition a
rule this bundle *cannot* decide; giving it a script would let it run, pass, and
be counted — turning "the project still has to write this test" into "checked".
"""

from __future__ import annotations

import json
import pathlib

import pytest
import yaml

from verifiable_gates import manifest as manifest_module

ROOT = pathlib.Path(__file__).resolve().parent.parent

BUNDLE = pathlib.Path(__file__).resolve().parent.parent / "src" / "verifiable_gates"


def write(path: pathlib.Path, data: object) -> pathlib.Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def a_bundle(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory holding one real script, so `ship` can point at something."""
    (tmp_path / "checks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "checks" / "scan_x.py").write_text("def main(root): return 0\n", encoding="utf-8")
    (tmp_path / "overlay.json").write_text("{}", encoding="utf-8")
    return tmp_path


VALID = {
    "ship": ["checks/scan_x.py"],
    "gates": {"a-rule": {"kind": "scan", "script": "checks/scan_x.py", "title": "A rule"}},
}


def test_this_bundles_own_manifest_is_valid() -> None:
    """The bundle that ships manifests passes its own manifest schema."""
    loaded = manifest_module.load(BUNDLE / "overlay.json")
    assert manifest_module.problems(loaded, BUNDLE) == []


def test_a_valid_manifest_is_silent(tmp_path: pathlib.Path) -> None:
    assert manifest_module.problems(VALID, a_bundle(tmp_path)) == []


def test_the_manifest_ships_itself() -> None:
    """A project holding the scripts but not the catalogue cannot say what it has."""
    assert "overlay.json" in manifest_module.shipped(VALID)


def test_only_scan_entries_have_scripts_to_run() -> None:
    manifest = {
        "ship": [],
        "gates": {
            "decided-here": {"kind": "scan", "script": "checks/scan_x.py", "title": "t"},
            "yours-to-write": {"kind": "suite", "title": "t"},
        },
    }
    assert manifest_module.scripts(manifest) == {"decided-here": "checks/scan_x.py"}


@pytest.mark.parametrize(
    ("broken", "needle"),
    [
        ({"kind": "check", "script": "checks/scan_x.py", "title": "t"}, "kind"),
        ({"kind": "scan", "script": "checks/scan_x.py", "title": "  "}, "no title"),
        ({"kind": "scan", "title": "t"}, "no script"),
        ({"kind": "scan", "script": "checks/absent.py", "title": "t"}, "not in ship"),
        ({"kind": "suite", "script": "checks/scan_x.py", "title": "t"}, "cannot decide"),
    ],
    ids=[
        "unknown-kind",
        "no-title",
        "scan-without-script",
        "script-not-shipped",
        "suite-with-script",
    ],
)
def test_each_rule_of_the_schema_is_enforced(
    tmp_path: pathlib.Path, broken: dict[str, str], needle: str
) -> None:
    manifest = {"ship": ["checks/scan_x.py"], "gates": {"a-rule": broken}}
    found = manifest_module.problems(manifest, a_bundle(tmp_path))
    assert any(needle in problem for problem in found), (
        f"expected a problem naming {needle}: {found}"
    )


def test_an_entry_that_is_not_an_object_is_caught(tmp_path: pathlib.Path) -> None:
    manifest = {"ship": [], "gates": {"a-rule": "just a string"}}
    found = manifest_module.problems(manifest, a_bundle(tmp_path))
    assert any("must be an object" in problem for problem in found)


def test_a_shipped_file_that_is_not_there_is_caught(tmp_path: pathlib.Path) -> None:
    manifest = {"ship": ["checks/gone.py"], "gates": {}}
    found = manifest_module.problems(manifest, a_bundle(tmp_path))
    assert any("not in the bundle" in problem for problem in found)


def test_a_script_listed_in_ship_but_absent_from_disk_is_caught(tmp_path: pathlib.Path) -> None:
    """`ship` and the filesystem can disagree, and the gate has to notice which way."""
    manifest = {
        "ship": ["checks/gone.py"],
        "gates": {"a-rule": {"kind": "scan", "script": "checks/gone.py", "title": "t"}},
    }
    found = manifest_module.problems(manifest, a_bundle(tmp_path))
    assert any("missing from the bundle" in problem for problem in found)


@pytest.mark.parametrize("name", ["../../outside/PLANTED.txt", "/etc/PLANTED.txt", "a/../../b.py"])
def test_a_ship_name_that_leaves_the_destination_is_caught(
    tmp_path: pathlib.Path, name: str
) -> None:
    """`install.py` joins ship names under `dest/tools/`; a climbing name lands elsewhere."""
    manifest = {"ship": [*VALID["ship"], name], "gates": VALID["gates"]}
    found = manifest_module.problems(manifest, a_bundle(tmp_path))
    assert f"ship lists {name}, which would land outside the destination" in found


@pytest.mark.parametrize(
    ("content", "error", "needle"),
    [
        ("[]", TypeError, "JSON object"),
        ('{"gates": {}}', KeyError, "ship"),
        ('{"ship": []}', KeyError, "gates"),
        ('{"ship": {}, "gates": {}}', TypeError, "list"),
        ('{"ship": [], "gates": []}', TypeError, "object keyed"),
    ],
    ids=["not-an-object", "no-ship", "no-gates", "ship-not-a-list", "gates-not-an-object"],
)
def test_an_unusable_manifest_raises_rather_than_reports(
    tmp_path: pathlib.Path, content: str, error: type[Exception], needle: str
) -> None:
    """Unusable and merely-wrong are different failures and must not look alike."""
    path = tmp_path / "overlay.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(error, match=needle):
        manifest_module.load(path)


def test_the_overlay_says_of_each_rule_exactly_what_the_catalogue_says() -> None:
    """The shipped overlay's scan gates and `rules.yaml` are one register in two files:
    same ids, same titles, two-way. All nine titles had drifted, and a test held only
    that a title was non-empty (outside audit, 2026-08-31)."""
    overlay = json.loads((ROOT / "src" / "verifiable_gates" / "overlay.json").read_text("utf-8"))
    rules = yaml.safe_load((ROOT / "rules.yaml").read_text("utf-8"))["rules"]
    scripted = {rule["id"]: rule["title"] for rule in rules if "script" in rule}
    shipped = {
        gid: entry["title"]
        for gid, entry in overlay["gates"].items()
        if entry.get("kind") == "scan"
    }
    assert shipped == scripted, "an id or a title differs between overlay.json and rules.yaml"


def test_the_default_registry_says_of_each_rule_exactly_what_the_catalogue_says() -> None:
    """`gates.yaml.default` is what every installed project receives as its own index —
    a third register describing the nine scan gates in words of its own, held by nothing,
    while the overlay was held to the catalogue (self-audit, 2026-08-31)."""
    default = yaml.safe_load(
        (ROOT / "src" / "verifiable_gates" / "gates.yaml.default").read_text("utf-8")
    )
    rules = yaml.safe_load((ROOT / "rules.yaml").read_text("utf-8"))["rules"]
    scripted = {rule["id"]: rule["title"] for rule in rules if "script" in rule}
    shipped = {gate["id"]: gate["title"] for gate in default["gates"]}
    assert shipped == scripted, "an id or a title differs between gates.yaml.default and rules.yaml"
