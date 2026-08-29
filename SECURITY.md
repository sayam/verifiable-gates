# Security policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository:
**Security → Report a vulnerability** on
<https://github.com/sayam/verifiable-gates/security/advisories/new>. It is
enabled, and it is the only channel — no address is published here, because an
address in a file is one that gets copied into three places and answered from
none of them.

## What to expect

- Acknowledgement within **3 days** of the report.
- An assessment — confirmed, not reproducible, or out of scope — within **14 days**.
- A fix or a mitigation before disclosure, and coordinated disclosure no later
  than **90 days** after the report unless we agree otherwise with you.

These three numbers appear only in this file. `tests/test_security_policy.py`
holds every "N days" in it to the declared set, so a copy cannot drift.

## Supported versions

The latest release on `main` receives fixes. Consume this repository as a pinned
submodule or a versioned dependency, never from `main` directly — a fix reaches
you when you move the pin.

## Scope

The checkers, censuses and instruments in `src/verifiable_gates/`, the shipped
bundle, and this repository's own workflows. The reference implementation,
`sayam/flask-todolist`, has its own policy.
