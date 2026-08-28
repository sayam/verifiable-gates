"""verifiable-gates — a gate registry that is enforced two ways against reality.

The governance core extracted from the reference implementation
(`sayam/flask-todolist`) under its ADR 0075 §6. The extraction closed on
2026-08-28: the registry schema, the nine standalone checkers, the doctor, the
installer, preflight, the sheet renderer, the governance and supply-chain
deciders, and the research instruments are all here. `v0.1.0` marks the point
where the two repositories separate.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
