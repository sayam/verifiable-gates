"""The Marketplace listing's categories, held to the ones this repository declares.

The two categories of a listed action are set on the release form, by a person, and no API
writes them. Nothing here read them back until 2026-09-05, when the owner opened the form and
found the two the other way round from the runbook that listed the action — and no record in
this repository could say when it had changed, because none had ever looked. A setting a
person can change on a web form that nobody reads back is a setting that drifts in silence.

This file holds the reader that closes that, and carries the copy of what is declared: the
tuple lives in `marketplace.py` and again here, so changing what we mean is a change a
reviewer sees twice — the same two-way hold as the posture switches and the decision ids.

Nothing here touches the network: the pages are strings. The live read is `posture.yml`'s,
weekly and on every push to `main`, where the platform is already asked.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Self

import pytest

from verifiable_gates import gh, marketplace

if TYPE_CHECKING:
    import pathlib

# The copy. `marketplace.DECLARED` is the source; this is the register a reviewer reads.
HELD = frozenset({"Code quality", "Continuous integration"})

PAYLOAD = '{"payload":{"action":{"categories":[%s],"color":"28a745"}}}'
QUALITY = '{"name":"Code quality","slug":"code-quality"}'
INTEGRATION = '{"name":"Continuous integration","slug":"continuous-integration"}'
DEPLOYMENT = '{"name":"Deployment","slug":"deployment"}'
DECLARED_ORDER = f"{QUALITY},{INTEGRATION}"
LIVE_ORDER = f"{INTEGRATION},{QUALITY}"


def a_page(categories: str = DECLARED_ORDER) -> str:
    return f"<html><title>verifiable-gates</title>{PAYLOAD % categories}</html>"


class _Answer(io.BytesIO):
    """What `urlopen` hands back: a context manager over the bytes, and nothing else."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def test_what_is_declared_is_what_this_file_says_it_is() -> None:
    """Both directions, in one line: the tuple and its copy, in order."""
    assert marketplace.DECLARED == HELD, (
        "the declared categories moved — change `marketplace.DECLARED` and this copy in one"
        " pull request, where a reviewer sees both"
    )


def test_the_categories_are_read_whichever_order_the_listing_carries_them_in() -> None:
    """The reader still takes them in the order the page gives, so the message can print
    what the listing actually shows; the comparison is the part that ignores it."""
    assert marketplace.categories(a_page()) == ("Code quality", "Continuous integration")
    assert marketplace.categories(a_page(LIVE_ORDER)) == (
        "Continuous integration",
        "Code quality",
    )


def test_the_order_between_them_is_not_held_because_the_platform_does_not_keep_it() -> None:
    """Measured 2026-09-05, in this order: the owner set *Primary Category = Code quality* on
    the release form and pressed Update release; the listing payload still read `Continuous
    integration, Code quality` eight minutes later over repeated uncached fetches; and the
    owner reopened the form and found **Continuous integration selected as primary again**.
    The order is GitHub's. A register claiming to hold it would be one nobody can make true
    (`DECISIONS.md` `the-listings-primary-category-is-not-ours-to-hold`).

    Both orders are clean, and this test is what goes red if the order is put back without
    re-deciding that row.
    """
    assert marketplace.problems(("Code quality", "Continuous integration")) == []
    assert marketplace.problems(("Continuous integration", "Code quality")) == []


@pytest.mark.parametrize("order", [DECLARED_ORDER, LIVE_ORDER])
def test_a_listing_that_carries_both_categories_is_clean(
    order: str, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    """Either way round — the live page shows one order and the form another, and both are
    the listing saying what this repository declared."""
    page = tmp_path / "listing.html"
    page.write_text(a_page(order), encoding="utf-8")

    assert marketplace.main(["--page", str(page)]) == 0

    printed = capsys.readouterr()
    assert printed.err == ""
    assert "Code quality · Continuous integration" in printed.out


def test_a_category_gone_is_a_finding_that_says_who_can_change_it(
    capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    """A listing that stopped saying what this is. The message has to say what to do,
    because no machine can do it — the fix is a person on the release form."""
    page = tmp_path / "listing.html"
    page.write_text(a_page(QUALITY), encoding="utf-8")

    assert marketplace.main(["--page", str(page)]) == 1

    said = capsys.readouterr().err
    assert "no longer carries ['Continuous integration']" in said
    assert "Only a person can change it" in said
    assert "release form" in said


def test_a_category_nobody_declared_is_a_finding_too(
    capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    """The other direction: a category added on the form is the listing saying something
    nobody here decided, and it is as much a finding as one going missing."""
    page = tmp_path / "listing.html"
    page.write_text(a_page(f"{DECLARED_ORDER},{DEPLOYMENT}"), encoding="utf-8")

    assert marketplace.main(["--page", str(page)]) == 1
    assert "carries ['Deployment'], which nobody here declared" in capsys.readouterr().err


def test_a_page_that_is_not_the_listing_is_the_third_answer(
    capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    """A challenge page, a login wall or a 404 body served with 200 carries no categories,
    and "no categories" reads exactly like "the listing was emptied". Measured the same day
    on another host: pypi.org answered `curl` with a 3038-byte challenge page, HTTP 200
    (L-0191). So a page that does not look like the listing is *could not answer*, not a
    finding — exit 2, the answer this package reserves for a question it could not put."""
    page = tmp_path / "challenge.html"
    page.write_text("<html><title>Client Challenge</title></html>", encoding="utf-8")

    assert marketplace.main(["--page", str(page)]) == 2
    assert "is not the listing" in capsys.readouterr().err


def test_a_page_that_is_not_there_is_the_third_answer_too(
    capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    assert marketplace.main(["--page", str(tmp_path / "gone.html")]) == 2
    assert "No such file" in capsys.readouterr().err


def test_the_listing_is_fetched_with_the_package_wide_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same budget every live check here uses, and the answer's own two ceilings on top
    of it (`net.body`) — a reader with no ceiling eats a job's whole budget in silence."""
    asked: list[dict[str, Any]] = []

    def fake_urlopen(url: str, timeout: int = 0) -> _Answer:
        asked.append({"url": url, "timeout": timeout})
        return _Answer(a_page().encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert set(marketplace.categories(marketplace.fetch_listing())) == HELD
    assert asked[0]["url"] == marketplace.LISTING
    assert asked[0]["timeout"] == gh.NETWORK_TIMEOUT_SECONDS


def test_a_listing_that_cannot_be_asked_is_the_third_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(url: str, timeout: int = 0) -> None:  # noqa: ARG001 — the call's shape is the point
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)

    assert marketplace.main([]) == 2
    assert "the listing could not be asked" in capsys.readouterr().err
