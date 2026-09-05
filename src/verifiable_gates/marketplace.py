"""The Marketplace listing, read back: the categories it shows, against the ones declared here.

The action is listed at `github.com/marketplace/actions/verifiable-gates`, and its two
categories are set **only** on the release form, by a person — no API writes them, and
nothing in this repository could read them. On 2026-09-05 the owner opened that form and
found the two the other way round from the runbook that listed the action; the page had said
so since at least 07:43 UTC that day, and no record here could say when it changed, because
nothing had ever looked. A setting a person can change on a web form, that nobody reads
back, is a setting that drifts silently — the same shape as the branch-protection switches
`posture.yml` already reads, one surface along.

**Which of the two is primary is not held, because the platform does not keep it.** Measured
the same day, in this order: the owner set *Primary Category = Code quality* on the form and
pressed Update release; the listing payload still read `Continuous integration, Code quality`
eight minutes later, over repeated fetches, with the page served uncached
(`cache-control: max-age=0, private, must-revalidate`, a fresh `etag` each time); and the
owner reopened the form and found **Continuous integration selected as primary again**. The
order is GitHub's, not ours. A register that claimed to hold it would be a register nobody
can make true — the thing this repository exists to refuse — so what is held is that **both
categories are there and no third one is** (`DECISIONS.md`
`the-listings-primary-category-is-not-ours-to-hold`).

Three answers: 0 the listing carries the two categories declared · 1 it does not, and the
difference is named · 2 the listing could not be asked, or answered with something that is
not the listing.

Role: decider — it answers pass or fail with an exit code and a job blocks on it
(`posture.yml`'s cron, weekly and on every push to `main`). What it decides on is a page
read live; the tests feed it pages as strings.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request

from verifiable_gates import gh, net

__all__ = ["DECLARED", "LISTING", "categories", "fetch_listing", "main", "problems"]

LISTING = "https://github.com/marketplace/actions/verifiable-gates"

# **As a set, deliberately.** The two categories a reader should find on the listing; which
# one the platform calls primary is the platform's to decide (see the docstring — the form
# was set to Code quality, saved, and came back showing Continuous integration). A copy of
# this set lives in `tests/test_marketplace.py`, so changing what we mean is a change a
# reviewer sees twice.
DECLARED = frozenset({"Code quality", "Continuous integration"})

# The page embeds its own payload; the visible chips are rendered from it, and there is more
# than one of them on the page (the listing shows one category, the payload carries both), so
# the payload is what is read.
CATEGORIES = re.compile(r'"categories":\[(.*?)\]')
NAME = re.compile(r'"name":"([^"]+)"')
# A page that is not the listing — a login wall, a challenge, a 404 body served with 200 —
# answers every question with silence, and silence reads like "no categories at all". So the
# page has to look like the listing before anything is read off it (L-0191: pypi.org answered
# `curl` with a 3038-byte challenge page, 200, and a link check over it would have found
# nothing wrong).
MARKS = ('"categories":', "verifiable-gates")


def fetch_listing(url: str = LISTING, *, timeout: int = gh.NETWORK_TIMEOUT_SECONDS) -> str:
    """The listing page as text — or `RuntimeError` saying it could not be asked."""
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — a constant https URL, composed of nothing
            return net.body(response, url, deadline).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as problem:
        message = f"the listing could not be asked ({url}): {problem}"
        raise RuntimeError(message) from problem


def categories(page: str) -> tuple[str, ...]:
    """The categories the listing carries, in the order it carries them."""
    missing = [mark for mark in MARKS if mark not in page]
    if missing:
        message = f"the answer is not the listing — it does not carry {missing}"
        raise RuntimeError(message)
    payload = CATEGORIES.search(page)
    if payload is None:  # pragma: no cover — MARKS already refused a page without it
        message = "the listing carries no category payload"
        raise RuntimeError(message)
    return tuple(NAME.findall(payload.group(1)))


def problems(found: tuple[str, ...], declared: frozenset[str] = DECLARED) -> list[str]:
    """What the listing carries that the declaration does not, and the other way round.

    Order is not compared, and the docstring says why. What is compared is membership, in
    both directions: a category gone is a listing that stopped saying what this is, and a
    category added is one that says something nobody here decided.
    """
    if set(found) == set(declared):
        return []
    gone = sorted(set(declared) - set(found))
    extra = sorted(set(found) - set(declared))
    parts = []
    if gone:
        parts.append(f"the listing no longer carries {gone}")
    if extra:
        parts.append(f"the listing carries {extra}, which nobody here declared")
    said = (
        f"{'; '.join(parts)} (it shows {list(found)}). Only a person can change it: the"
        " release form of any release, Primary Category and the one beside it, then Update"
        " release — the order between them is GitHub's and is not held here."
    )
    return [said]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=LISTING, help="the listing to read (default: ours)")
    parser.add_argument("--page", help="read a saved page instead of the network")
    args = parser.parse_args(argv)

    try:
        page = pathlib_read(args.page) if args.page else fetch_listing(args.url)
        found = categories(page)
    except (RuntimeError, OSError) as unreadable:
        print(f"** {unreadable}", file=sys.stderr)
        return 2

    found_problems = problems(found)
    for problem in found_problems:
        print(f"** {problem}", file=sys.stderr)
    if found_problems:
        return 1
    print(f"the listing carries the two categories declared: {' · '.join(sorted(found))}")
    return 0


def pathlib_read(name: str) -> str:
    """A saved page, for the tests and for a person holding a capture beside a finding."""
    import pathlib  # noqa: PLC0415 — the only place a path is read; kept beside its use

    return pathlib.Path(name).read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
