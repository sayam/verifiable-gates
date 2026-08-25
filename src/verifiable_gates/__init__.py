"""verifiable-gates — a gate registry that is enforced two ways against reality.

The governance core extracted from the reference implementation
(`sayam/flask-todolist`) under its ADR 0075 §6. **Stage 1 shipped the registry
schema only** — the enforcers (checks, doctor, preflight) arrive in stage 2 and
the governance checkers in stage 3.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.0.1"
