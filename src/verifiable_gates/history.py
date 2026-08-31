"""One reader for the run history every census measures against.

Three censuses read the same thing — a JSON file when offline, the platform when
not — and each had its own copy of the reading, each catching a different set of
failures. The gap between the copies was the finding of an outside audit
(2026-08-29): a file that did not exist produced a traceback, malformed JSON
produced a traceback, and a *valid* file holding nothing at all produced a green
— "every promise holds (0 watched)", "examined 0 runs" — from instruments whose
own docstrings say a quiet measurement reports every promise as kept on the day
it can see nothing.

So the contract is in one place: **anything that stops the census from seeing
is `UnreadableError`**, and the caller exits 2 for all of it. That includes a history
of the wrong shape and, when the caller says there is something to measure, an
empty one. Exit 2 is neither pass nor fail; it is the third answer, "could not
look", which is the one that must never be rounded to pass.

"Wrong shape" reaches into the records: a caller names the fields its records
carry, and a list whose records lack them is not its history. The output of
`gh run list --json` — `databaseId`, `createdAt` — fed to `--input` made one
census count zero failures over a hundred runs holding thirteen and another
raise `KeyError` (outside audit, 2026-08-30). Both are now the third answer.

Role: helper — one reader for three censuses. Its evidence is that every way
of not seeing comes out the same, proved in its own tests and the censuses'.
"""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["UnreadableError", "read"]


class UnreadableError(RuntimeError):
    """The history could not be seen — for whichever reason, the answer is the same."""


def read(
    path: str | None,
    fetch: Callable[[], Any],
    *,
    shape: type,
    must_hold_something: bool = True,
    fields: tuple[str, ...] | dict[str, tuple[type, ...]] = (),
) -> Any:  # noqa: ANN401 — the shape is whichever the caller asked for
    """The history: the file at `path` if given, otherwise what `fetch()` returns.

    Raises `UnreadableError` when the file cannot be read or parsed, when what came
    back is not of `shape`, when a record of a list (or the mapping itself) lacks
    one of `fields`, or — while `must_hold_something` — when it is empty. `fields`
    may be a mapping from name to the kinds the census reads it as: a name starting
    with `?` may be absent, and `datetime.datetime` among the kinds means an ISO
    timestamp in a string. A record with every key and the wrong kinds behind them
    raised `TypeError`, `AttributeError` or `ValueError` from inside the count, exit
    1 — the code for a broken promise (self-audit, 2026-08-31). `fetch` is expected
    to raise on its own when the platform refuses; that is let through unchanged so
    the caller's message can say what the platform said.
    """
    if path is None:
        found = fetch()
    else:
        try:
            found = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        except OSError as problem:
            raise UnreadableError(f"{path}: {problem.strerror or problem}") from problem
        except json.JSONDecodeError as problem:
            where = f"{problem.msg} at line {problem.lineno}"
            raise UnreadableError(f"{path}: not JSON ({where})") from problem
    if not isinstance(found, shape):
        raise UnreadableError(
            f"the history is a {type(found).__name__}, not a {shape.__name__} — "
            "this is not a run history"
        )
    if must_hold_something and not found:
        raise UnreadableError(
            "the history is empty — a census over nothing counts nothing, and must not "
            "report it as a pass"
        )
    records = found if isinstance(found, list) else [found]
    if fields:
        _hold_fields(records, fields)
    return found


def _hold_kind(index: int, field: str, value: object, kinds: tuple[type, ...]) -> None:
    """One field that is there is of a kind the census reads — a stamp among them parses."""
    plain = tuple(k for k in kinds if k is not datetime.datetime)
    if isinstance(value, plain):
        return
    if datetime.datetime in kinds and isinstance(value, str):
        try:
            datetime.datetime.fromisoformat(value)
        except ValueError as problem:
            raise UnreadableError(
                f"record {index}: {field} is {value!r}, not an ISO timestamp"
            ) from problem
        return
    wanted = " or ".join("ISO timestamp" if k is datetime.datetime else k.__name__ for k in kinds)
    raise UnreadableError(f"record {index}: {field} is a {type(value).__name__}, not {wanted}")


def _hold_fields(records: list[Any], fields: tuple[str, ...] | dict[str, tuple[type, ...]]) -> None:
    """Every record is a mapping carrying `fields`, or the list is not this history."""
    kinds = fields if isinstance(fields, dict) else {}
    required = [f.removeprefix("?") for f in fields if not f.startswith("?")]
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise UnreadableError(f"record {index} is a {type(record).__name__}, not a mapping")
        for named, wanted in kinds.items():
            field = named.removeprefix("?")
            if field in record:
                _hold_kind(index, field, record[field], wanted)
        missing = [field for field in required if field not in record]
        if missing:
            hint = (
                " — this looks like `gh run list --json`, which is not the shape the census "
                "fetches for itself; run it without --input, or write records that carry "
                f"{list(fields)}"
                if {"databaseId", "createdAt"} & set(record)
                else ""
            )
            raise UnreadableError(f"record {index} has no {missing}{hint}")
