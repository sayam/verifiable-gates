"""The scanners a project runs against itself.

Every module here is **standalone on purpose**: stdlib only, no imports from this
package, and a `main(root) -> int` plus a `__main__` block. That is what lets
`install.py` copy a single file into a target project that has not installed its
first dependency yet, and run it with a bare `python3`. `tests/test_checks.py`
enforces the property, because it is the kind that a helpful refactor into a
shared helper breaks without anybody noticing until a target project fails.

Exit codes are the contract: `0` clean or not-applicable, `1` findings printed to
stdout, `2` called wrongly.
"""

from __future__ import annotations

__all__: list[str] = []
