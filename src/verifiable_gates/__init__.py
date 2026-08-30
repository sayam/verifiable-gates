"""verifiable-gates — a gate registry that is enforced two ways against reality.

The governance core extracted from the reference implementation
(`sayam/flask-todolist`) under its ADR 0075 §6. The extraction closed on
2026-08-28: the registry schema, the nine standalone checkers, the doctor, the
installer, preflight, the sheet renderer, the governance and supply-chain
deciders, and the research instruments are all here. `v0.1.0` marks the point
where the two repositories separate.
"""

from __future__ import annotations

from verifiable_gates import registry, rules

# The two things the README shows being imported are on the surface by name —
# `import verifiable_gates` followed by `verifiable_gates.rules` used to fail,
# and the example worked only because `from … import rules` reaches a submodule
# on its own. An outside audit (2026-08-29) read that as an example that lies.
__all__ = ["__version__", "registry", "rules"]

__version__ = "0.1.10"
