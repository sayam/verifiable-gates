"""The settings on the hosting platform, held to what the project declared.

Every gate in a repository rests on settings that live somewhere else: that the
default branch takes changes only through a pull request, that administrators are
not exempt, that the required checks are the ones that actually run. **Nothing
inside a repository can see any of it.** Switch one off in a web form, or let the
platform change a default, and the documents keep saying what they always said.
It is the one control every other control leans on, and the one nobody watches.

Four kinds of drift, kept apart because they fail differently:

- **A required check no job can produce** — every pull request waits for
  something that never arrives. Nothing goes red; it simply never merges.
- **A check that runs and is not required** — it goes red and merges anyway.
  Allowed, but only as a signed decision: the exemption register is what turns
  "we chose this" into something a reader can check. Held against the wrong set,
  such a register can never match anything, so nothing consults it and it quietly
  becomes a text file — which is what the reference implementation found in its
  own, after it had sat there unread since the day it was written.
- **A flag whose value is not the declared one** — the plain case.
- **An alert nobody has judged** — sitting on the page outsiders read first.

Three rules run through all of it:

**Cannot read is not the same as switched off.** A field a token may not see comes
back as `None`, and reporting that as "off" is a lie in the direction that causes
work; reporting it as "on" is a lie in the direction that causes breaches. It is
reported as its own third answer.

**A value nobody can read still has a declared value.** The reference
implementation lost one setting entirely for that reason: it lived in the
unreadable class, so the register recorded that no machine could see it and no
line anywhere recorded what it should be. A setting that cannot be proven has no
owner, and one without an owner has no default — the rule it carried was then
enforced by one person's memory, and forgotten about thirty times running.

**Both directions, always.** An entry excusing something that no longer exists is
worse than no entry: exemptions go quiet exactly when the thing they excuse
disappears, so the register grows a tail of lines that will one day excuse
something nobody decided about.

**The wording of every message is an input**, as with every decider here: the
mechanism travels, the prose does not.

Role: decider — it answers pass or fail. It is handed the platform's answers; how
those are fetched belongs to the caller.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "MESSAGES",
    "Setting",
    "alert_problems",
    "check_problems",
    "setting_problems",
    "unreadable",
]


@dataclasses.dataclass(frozen=True)
class Setting:
    """One platform switch, the value it should hold, and why.

    `why` is not decoration: a switch whose reason nobody wrote down is one the
    next person turns off to make something else work.

    `readable` says whether a least-privilege token can see this at all. A false
    one is still declared — the value it should hold is the point, and losing the
    declaration because no machine can read it is how a setting ends up with no
    owner.
    """

    want: object
    why: str
    readable: bool = True


MESSAGES = {
    "missing_check": "checks that run on a pull request but are not required: {names}",
    "ghost_check": ("required checks no job can produce, so a pull request waits forever: {names}"),
    "undeclared_check": (
        "checks that are neither required nor declared: {names} — require them, or "
        "declare them with a reason: a check that blocks nobody is not wrong, but it has "
        "to say who sees it and within how many days"
    ),
    "stale_exemption": (
        "the exemption register excuses {name!r}, and nothing by that name exists any "
        "more — take the line out: an exemption goes quiet exactly when the thing it "
        "excused disappears"
    ),
    "wrong_value": "{name} = {said!r}, but this project declares {want!r} ({why})",
    # **`want` is a field here on purpose.** A report saying only that a value
    # could not be read leaves the reader with nothing to act on; saying what it
    # should be turns an unreadable setting back into something a person can check
    # by hand. That is the whole of the "a value nobody can read still has a
    # declared value" rule, at the point where it becomes visible.
    "unreadable": "{name} = cannot be read, and should be {want!r} ({why})",
    "unjudged_alert": (
        "alert {name} ({state}) has not been judged — fix it, dismiss it with a reason, "
        "or enter it in the register"
    ),
    "stale_alert": (
        "the register accepts alert {name}, and no such alert exists any more — take the line out"
    ),
    "unreadable_alerts": "cannot read the code-scanning alerts — the token lacks the scope",
}


def _text(messages: Mapping[str, str] | None) -> dict[str, str]:
    return {**MESSAGES, **(messages or {})}


def _bare(name: str) -> str:
    """A check name without its matrix suffix — the exemption register names jobs."""
    return name.split(" (", 1)[0]


def check_problems(
    required: set[str],
    on_pull_requests: set[str],
    produced: set[str],
    exempt: Mapping[str, str],
    messages: Mapping[str, str] | None = None,
) -> list[str]:
    """Three directions at once, because each is invisible to the other two.

    `produced` is **every** check the repository can make, not only the ones a pull
    request shows. The exemption register has to be held against that wider set: an
    entry naming a scheduled job can never appear among pull-request checks, so a
    check written the narrow way consults the register exactly never.
    """
    text = _text(messages)
    problems = []

    missing = sorted(name for name in on_pull_requests - required if _bare(name) not in exempt)
    if missing:
        problems.append(text["missing_check"].format(names=missing))

    ghosts = sorted(required - on_pull_requests)
    if ghosts:
        problems.append(text["ghost_check"].format(names=ghosts))

    undeclared = sorted({_bare(name) for name in produced - required} - set(exempt))
    if undeclared:
        problems.append(text["undeclared_check"].format(names=undeclared))

    everything = {_bare(name) for name in produced}
    problems += [
        text["stale_exemption"].format(name=name) for name in sorted(set(exempt) - everything)
    ]
    return problems


def setting_problems(
    state: Mapping[str, object],
    declared: Mapping[str, Setting],
    messages: Mapping[str, str] | None = None,
) -> list[str]:
    """Every declared switch whose value is not the declared one.

    **A `None` is skipped rather than reported as wrong.** It means the token could
    not see the field, which is a different answer from "switched off" — see
    `unreadable`, which is where that answer belongs.
    """
    text = _text(messages)
    return [
        text["wrong_value"].format(
            name=name, said=state.get(name), want=setting.want, why=setting.why
        )
        for name, setting in declared.items()
        if state.get(name) is not None and state.get(name) != setting.want
    ]


def unreadable(
    state: Mapping[str, object],
    declared: Mapping[str, Setting],
    messages: Mapping[str, str] | None = None,
) -> list[str]:
    """Switches the answer did not carry — reported as their own third outcome.

    Only for settings declared unreadable at least privilege. A readable one coming
    back empty is a change in the platform or the token, and that belongs in the
    caller's hands rather than being absorbed here as normal.
    """
    text = _text(messages)
    return [
        text["unreadable"].format(name=name, want=setting.want, why=setting.why)
        for name, setting in declared.items()
        if not setting.readable and state.get(name) is None
    ]


def alert_problems(
    alerts: Sequence[Mapping[str, object]] | None,
    accepted: Mapping[str, str],
    messages: Mapping[str, str] | None = None,
) -> list[str]:
    """Every alert has been judged, and every register line still matches one.

    "Judged" has two accepted shapes: a line in the project's own register, **or**
    dismissed on the platform with a reason that is not empty. What is refused is
    an alert with neither, because that is one sitting on the page outsiders read
    first with nobody having read it.

    An alert the platform calls `fixed` needs no entry — it went away because the
    code changed, not because somebody decided. It must also not count as present,
    or a register line that ought to be removed can stay forever.
    """
    text = _text(messages)
    if alerts is None:
        return [text["unreadable_alerts"]]

    problems = []
    seen = set()
    for alert in alerts:
        if alert.get("state") == "fixed":
            continue
        tool = alert.get("tool") or {}
        rule = alert.get("rule") or {}
        name = f"{tool.get('name') if isinstance(tool, dict) else None}/"
        name += f"{rule.get('id') if isinstance(rule, dict) else None}"
        seen.add(name)
        if name in accepted:
            continue
        comment = alert.get("dismissed_comment") or ""
        if alert.get("state") == "dismissed" and str(comment).strip():
            continue
        problems.append(text["unjudged_alert"].format(name=name, state=alert.get("state")))

    problems += [text["stale_alert"].format(name=name) for name in sorted(set(accepted) - seen)]
    return problems
