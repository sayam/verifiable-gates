# Governance

Who decides things here, what is promised, and what is not. Written 2026-09-06 because
round 28 of this repository's own audit asked the question an adopter asks first and found
no answer anywhere.

## One maintainer, and no promise about how long

**This project has one maintainer: Sayam Sriphua**, who wrote it and decides everything in
it. There is no second maintainer, no organisation behind it, and no rota.

**There is no promise about how long it will be maintained.** Not a year, not a quarter, not
until the next release. Anything else here would be a sentence with nobody behind it, and a
tool whose whole subject is unearned promises has no business making one.

That is the honest half. The useful half is what has been built so that the answer costs you
less than it usually does.

## What survives if this stops

A tool being abandoned normally hurts in four ways. Three of them were designed out before
anybody asked, and it is worth knowing which:

- **Your CI keeps working.** The bundle is copied into your `tools/` as ordinary
  stdlib-only Python. It has no package to resolve, no service to call and no index to reach:
  `tests/test_checks_are_standalone.py` holds every file it installs to stdlib-only imports
  and to opening nothing off your machine. A repository that stops moving does not stop your
  build.
- **Your alerts keep meaning what they meant.** Rule ids are never removed — additions are
  free, removals are refused, and `tests/test_released_ids.py` checks every published tag on
  every run. A dismissal you filed against a rule id keeps pointing at that rule whether or
  not anything else ever ships.
- **You can fork it and be complete.** Apache-2.0, and the whole of it is in the repository:
  the catalogue is `rules.yaml` and `working.yaml`, the rendered sheets are generated from
  them, and every gate carries the incident that created it (`born_from`) and the evidence it
  has caught something (`proved_by`). There is nothing to reverse-engineer and no hosted
  component to replace. Releases are also archived at Zenodo with a DOI, so a version you
  depended on stays retrievable independently of this account.
- **What does not survive is new rules.** The catalogue stops growing, and rules that should
  have been retracted are not. That is the real cost, and nothing in the design removes it.

## How you would find out

You would not be told. Nobody is going to send you a notice, and a project that promised to
publish its own obituary would be promising the one thing an abandoned project cannot do.

What you can read, whenever you want to know:

- **The releases page** — when the newest tag was cut.
- **The posture workflow** — it runs every Monday and reports on the repository itself, so a
  green run recently is a sign that somebody is still here.
- **The commit history on `main`.**

**No staleness threshold is declared here.** Seventeen releases in nine days is not a history
you can calibrate "quiet means gone" against, and a number invented to fill the gap would be
exactly the unearned precision this project refuses everywhere else. When there is a year of
history, a threshold can be written from it, and then it belongs in this file.

## How a rule is withdrawn, and by whom

**By the maintainer, and only with a reason and a date on the record.** A rule never leaves
by being deleted: it stays in `rules.yaml` and carries `retracted:` with the date, the reason
and, where there is one, what replaced it. The entry stays, the id stays, and the rendered
sheet says it was withdrawn. That is the whole deprecation path, and it exists so that a
consumer who keyed something to that id is never left pointing at nothing.

The evidence needed to withdraw a rule is the same as the evidence needed to publish one: the
trap it was born from stopped being a trap, or a better rule covers it. "Nobody used it" is
not evidence, and neither is "it was noisy".

## What you get while it is maintained

`SECURITY.md` names three timeframes for a vulnerability report — acknowledgement,
assessment, disclosure. Those are what a report gets **while this is maintained**, and this
page is how you tell whether it still is. They are not a promise that it will be.

For anything else — a bug, a question, a rule you think is wrong — open an issue. There is no
service level and no queue: one person reads them when they can, and some will go unanswered.

## Why there is no CODEOWNERS file

`CODEOWNERS` exists so that the right second person is asked to review. With one maintainer
it would name that maintainer on every path and request a review from the author of the pull
request, which is a register with no second reader. When there is a second maintainer, the
file is written in the same change that adds them, and this section goes.

## What changes if a second maintainer appears

This page, `DECISIONS.md` `one-maintainer-and-no-promise`, and `CODEOWNERS`, in one pull
request. Until then, the accurate description of the governance of this project is the first
sentence of this file.
