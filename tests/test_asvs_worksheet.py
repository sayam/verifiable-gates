"""The worksheet is refreshed from a pinned standard and never loses a person's verdict.

Two directions on the one thing that matters: a verdict somebody wrote survives
a rebuild, and a requirement the standard dropped disappears from the table —
while everything above the marker is left exactly as it was.
"""

from __future__ import annotations

import io
import json
import urllib.request
from typing import TYPE_CHECKING, Any

from verifiable_gates import asvs_worksheet as ws

if TYPE_CHECKING:
    import pathlib

    import pytest

WORDS = ws.Words(
    marker="<!-- table starts here — everything below is generated -->",
    unassessed="unassessed",
    header="| id | L | requirement | status | evidence |",
)

STANDARD = [
    {
        "req_id": "V1.2.10",
        "chapter_id": "V1",
        "chapter_name": "Encoding",
        "section_id": "V1.2",
        "section_name": "Injection",
        "level": "1",
        "text": "Ten.",
    },
    {
        "req_id": "V1.2.9",
        "chapter_id": "V1",
        "chapter_name": "Encoding",
        "section_id": "V1.2",
        "section_name": "Injection",
        "level": "2",
        "text": "Nine.",
    },
    {
        "req_id": "V2.1.1",
        "chapter_id": "V2",
        "chapter_name": "Validation",
        "section_id": "V2.1",
        "section_name": "Input",
        "level": "3",
        "text": "Out of scope.",
    },
]


def test_requirement_ids_sort_as_numbers_not_text() -> None:
    """`V1.2.10` after `V1.2.9` — text order would put it first."""
    ordered = [item["req_id"] for item in sorted(STANDARD, key=ws.sort_key)]

    assert ordered == ["V1.2.9", "V1.2.10", "V2.1.1"]


def test_fetch_trims_to_the_kept_fields_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Upstream carries more fields than the digest should move on."""
    upstream = {
        "requirements": [
            {
                "req_id": "V1.2.10",
                "chapter_id": "V1",
                "chapter_name": "Encoding",
                "section_id": "V1.2",
                "section_name": "Injection",
                "L": "1",
                "req_description": "Ten.",
                "cwe": ["CWE-79"],
            },
            {
                "req_id": "V1.2.9",
                "chapter_id": "V1",
                "chapter_name": "Encoding",
                "section_id": "V1.2",
                "section_name": "Injection",
                "L": "2",
                "req_description": "Nine.",
                "cwe": [],
            },
        ]
    }

    asked: list[tuple[str, int]] = []

    def fake_urlopen(url: str, timeout: int) -> io.BytesIO:
        asked.append((url, timeout))
        return io.BytesIO(json.dumps(upstream).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetched = ws.fetch("https://example.test/asvs.json", timeout=7)

    assert asked == [("https://example.test/asvs.json", 7)]
    assert [item["req_id"] for item in fetched] == ["V1.2.9", "V1.2.10"]
    assert fetched[0] == STANDARD[1], "the kept fields, renamed — and nothing else"
    assert "cwe" not in fetched[0]


def test_the_digest_moves_only_when_a_requirement_does() -> None:
    same_order_different_bytes = [dict(reversed(list(item.items()))) for item in STANDARD]
    changed = [dict(item) for item in STANDARD]
    changed[0]["text"] = "Ten, reworded."

    assert ws.digest_of(same_order_different_bytes) == ws.digest_of(STANDARD)
    assert ws.digest_of(changed) != ws.digest_of(STANDARD)


def test_pin_and_load_round_trip(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "asvs.json"

    ws.pin(target, STANDARD, version="5.0.0", url="https://example.test/asvs.json")
    body = json.loads(target.read_text(encoding="utf-8"))

    assert body["version"] == "5.0.0"
    assert body["source"] == "https://example.test/asvs.json"
    assert ws.load(target) == STANDARD
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_everything_above_the_marker_is_the_persons_and_below_is_the_tools() -> None:
    text = "intro\n| V9.9.9 | 1 | backlog row | not ours | — |\n" + WORDS.marker + "\ntable\n"

    assert ws.preamble(text, WORDS.marker) == "intro\n| V9.9.9 | 1 | backlog row | not ours | — |\n"
    assert ws.assessment_part(text, WORDS.marker) == "\ntable\n"


def test_a_document_without_the_marker_has_no_preamble_and_no_table() -> None:
    assert ws.preamble("anything", WORDS.marker) == ""
    assert ws.assessment_part("anything", WORDS.marker) == ""


def test_verdicts_are_read_only_below_the_marker() -> None:
    """The preamble's backlog table has rows shaped exactly like the assessment's.

    The first version of the tool did not cut the head and rewrote those rows —
    silently, because the result was still a valid table.
    """
    text = (
        "| V1.2.9 | 2 | backlog | wrong | from the preamble |\n"
        + WORDS.marker
        + "\n| id | L | requirement | status | evidence |\n"
        "|---|---|---|---|---|\n"
        "| V1.2.9 | 2 | Nine. | pass | `tests/test_x.py` |\n"
        "| V1.2.10 | 1 | Ten. | fail |\n"  # four cells — malformed, skipped
        "not a row\n"
    )

    assert ws.existing_verdicts(text, WORDS.marker) == {"V1.2.9": ("pass", "`tests/test_x.py`")}


def test_render_groups_by_chapter_and_section_and_keeps_to_the_levels_in_scope() -> None:
    rendered = ws.render(STANDARD, {}, levels=("1", "2"), words=WORDS)

    assert rendered == (
        "\n## V1 — Encoding\n"
        "\n### V1.2 Injection\n"
        "\n| id | L | requirement | status | evidence |\n"
        "|---|---|---|---|---|\n"
        "| V1.2.9 | 2 | Nine. | unassessed | — |\n"
        "| V1.2.10 | 1 | Ten. | unassessed | — |\n"
    )
    assert "V2.1.1" not in rendered, "a level out of scope must not be rendered"


def test_a_second_chapter_opens_a_new_heading() -> None:
    rendered = ws.render(STANDARD, {}, levels=("1", "2", "3"), words=WORDS)

    assert "\n## V2 — Validation\n\n### V2.1 Input\n" in rendered
    assert "| V2.1.1 | 3 | Out of scope. | unassessed | — |" in rendered


def test_a_rebuild_keeps_every_verdict_a_person_wrote_and_the_preamble() -> None:
    """The direction that matters most: refreshing must not be the same as resetting."""
    before = (
        "# Preamble the person wrote\n\n| V1.2.9 | 2 | backlog | x | y |\n\n"
        + WORDS.marker
        + "\n\n## V1 — Encoding\n\n### V1.2 Injection\n\n"
        "| id | L | requirement | status | evidence |\n"
        "|---|---|---|---|---|\n"
        "| V1.2.9 | 2 | Nine. | pass | `tests/test_nine.py` |\n"
        "| V1.2.10 | 1 | Ten. | fail | backlog |\n"
    )

    after = ws.rebuild(before, STANDARD, levels=("1", "2"), words=WORDS)

    assert after.startswith("# Preamble the person wrote\n\n| V1.2.9 | 2 | backlog | x | y |\n\n")
    assert "| V1.2.9 | 2 | Nine. | pass | `tests/test_nine.py` |" in after
    assert "| V1.2.10 | 1 | Ten. | fail | backlog |" in after
    assert after == ws.rebuild(after, STANDARD, levels=("1", "2"), words=WORDS), (
        "a rebuild is idempotent"
    )


def test_a_requirement_the_standard_dropped_leaves_the_table() -> None:
    """The other direction — a row nobody can judge any more must not linger."""
    before = (
        WORDS.marker + "\n"
        "| V1.2.9 | 2 | Nine. | pass | ok |\n"
        "| V7.7.7 | 1 | Retired. | pass | ok |\n"
    )
    only_nine: list[dict[str, Any]] = [STANDARD[1]]

    after = ws.rebuild(before, only_nine, levels=("1", "2"), words=WORDS)

    assert "V7.7.7" not in after
    assert "| V1.2.9 | 2 | Nine. | pass | ok |" in after


def test_a_new_requirement_arrives_unassessed_not_passed() -> None:
    """A row nobody judged must say so — a default of "pass" would be a lie by omission."""
    after = ws.rebuild(WORDS.marker + "\n", STANDARD, levels=("1",), words=WORDS)

    assert "| V1.2.10 | 1 | Ten. | unassessed | — |" in after
