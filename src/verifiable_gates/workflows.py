"""Reading GitHub Actions workflows — **the one reader**.

`on:` is valid in three shapes, and the idiom most projects reach for handles two:

    on: push                    → str    fine
    on: [push, pull_request]    → list   **raises TypeError**
    on:
      pull_request:             → dict   fine

The idiom was `"pull_request" in (triggers if isinstance(triggers, dict) else {triggers: None})`,
which uses the value as a dict key — and a list cannot be one. The reference
implementation had that copied in **five places**, three of them broken the same
way, and they had already drifted: one guarded itself with `isinstance`, two did
not.

That is why this is a module rather than an idiom. A parser is a command like any
other, and a second copy of it drifts exactly as fast.

**The directory is an input.** Baking one project's layout in would make this
readable only from a checkout of that project.

Role: helper — shared machinery. Its evidence is its callers and their tests.
"""

from __future__ import annotations

import pathlib  # noqa: TC003 — used at run time by workflow_dir, not only as a type
from typing import Any

import yaml

# **The key type is `Any`, not `str`, and that is not laziness.** YAML 1.1 reads an
# unquoted `on:` as the boolean `True`, so a real workflow's top-level mapping has
# a non-string key in it. Declaring `dict[str, Any]` would be a type that says
# something untrue about every workflow this reader was written for.
Workflow = dict[Any, Any]

__all__ = [
    "Workflow",
    "all_workflows",
    "event_config",
    "jobs",
    "load",
    "runs_on",
    "schedules",
    "triggers",
    "workflow_dir",
]


def workflow_dir(root: pathlib.Path) -> pathlib.Path:
    """Where a project keeps its workflows, given its root."""
    return root / ".github" / "workflows"


def load(path: pathlib.Path) -> Workflow:
    """One workflow's body — an empty file is an empty dict, never None."""
    loaded: Workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded


def all_workflows(directory: pathlib.Path) -> dict[str, Workflow]:
    """Filename → body for every workflow in a directory, sorted by name."""
    return {path.name: load(path) for path in sorted(directory.glob("*.y*ml"))}


def triggers(workflow: Workflow) -> set[str]:
    """The events that start this workflow — covering all three shapes of `on:`.

    **The key really can be `True`**: YAML 1.1 reads an unquoted `on:` as a
    boolean, since `yes`/`on`/`true` are one value in that spec, and PyYAML
    follows it. A reader that only looks for the string `"on"` finds nothing in
    most real workflows.
    """
    declared = workflow.get(True, workflow.get("on"))
    if declared is None:
        return set()
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, dict):
        return {str(key) for key in declared}
    return {str(item) for item in declared}


def runs_on(workflow: Workflow, event: str) -> bool:
    """Is this workflow started by this event?"""
    return event in triggers(workflow)


def event_config(workflow: Workflow, event: str) -> object:
    """What is declared under that event — `None` if absent or shapeless.

    `on: [schedule]` can name the event but cannot carry a cron; GitHub does not
    accept one there either. So "no config" is the right answer, not a surrender.
    """
    declared = workflow.get(True, workflow.get("on"))
    return declared.get(event) if isinstance(declared, dict) else None


def schedules(workflow: Workflow) -> list[str]:
    """Every cron line this workflow declares — `on.schedule` is a list of `{cron: ...}`."""
    declared = event_config(workflow, "schedule")
    if not isinstance(declared, list):
        return []
    return [entry["cron"] for entry in declared if isinstance(entry, dict) and entry.get("cron")]


def jobs(workflow: Workflow) -> dict[str, Workflow]:
    """Every job in this workflow."""
    found: dict[str, Workflow] = workflow.get("jobs") or {}
    return found
