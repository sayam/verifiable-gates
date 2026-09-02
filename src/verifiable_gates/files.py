"""One writer for every file this package writes whole, so that none of them is ever half.

`write_text` truncates first and writes second, and a reader that arrives between the two
sees an empty file or part of one. Measured on one machine with a reader in a loop: the
reader's copy was unusable **32% of the time at 1.5 KB** (the installer's record), **74%
at 100 KB** (a changelog) and **99.7% at 4.2 MB** (a SARIF log); and a writer killed
inside that window — a cancelled job — left the file at **0 bytes** (self-audit round 20,
2026-09-03). Eight places wrote that way and none the other. `advertised.py` had written
down that nothing there needed to be atomic because git tracks every file it touches,
which is true of the disk and not of the reader: git gives back the bytes, not the
answer a test or an agent read off the half-written file while it was being written.

So: the bytes go to a sibling file in the same directory — same filesystem, which is what
makes the rename atomic — are flushed to disk, and are renamed over the target with
`Path.replace`. A reader sees the old file or the new one and nothing between; a writer
killed at any point leaves the old file where it was and at most a temp file beside it,
named `.<name>.<token>.tmp` so it is recognisable. The mode of a file that already exists
is kept, because a scanner the installer rewrites runs by its mode, and a file that did
not exist gets what `write_text` gave it, `0o666` narrowed by the umask. The sibling
itself is written `0o600` and wears that final mode only at the end: it exists under its
own name for the length of the write, and for that moment nobody else has business
reading it. A symlink is written *through*, as `write_text` did, not replaced by a file.
Whatever the write raises is raised: every caller already answers an `OSError` in a
sentence of its own.

`gates_doctor.py` carries a copy of the text writer in a dozen lines. That file is
shipped standalone and imports nothing from here, for the same reason its manifest
reading is its own — the duplication is small and the property is not.

Role: helper — shared machinery. Its evidence is its callers and their tests.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import stat
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

__all__ = ["DEFAULT_MODE", "copy_atomically", "write_bytes_atomically", "write_text_atomically"]

_CREATE = os.O_WRONLY | os.O_CREAT | os.O_EXCL
# **The sibling is created private and given its final mode just before the rename.**
# It exists under its own name for the length of the write, and for that moment nobody
# else has any business reading it, still less writing to it — code scanning said so of
# the first two pushes of this change (`py/overly-permissive-file`), and it was right
# both times.
_PRIVATE = 0o600
# What a file that did not exist ends up with: exactly what `write_text` gave it, its
# `0o666` narrowed by the umask. Read here, once, at import: reading the umask means
# setting it, and a process that has already started threads cannot do that safely.
_UMASK = os.umask(0)
os.umask(_UMASK)
DEFAULT_MODE = 0o666 & ~_UMASK


def write_text_atomically(path: pathlib.Path, text: str, encoding: str = "utf-8") -> None:
    """`text` as `path`, whole or not at all."""
    write_bytes_atomically(path, text.encode(encoding))


def write_bytes_atomically(path: pathlib.Path, data: bytes) -> None:
    """`data` as `path`, whole or not at all: a sibling file, flushed, renamed over."""
    target = path.resolve()
    beside = _beside(target)
    try:
        with os.fdopen(os.open(beside, _CREATE, _PRIVATE), "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        _keep_mode(target, beside)
        beside.replace(target)
    except OSError:
        with contextlib.suppress(OSError):
            beside.unlink()
        raise


def copy_atomically(source: pathlib.Path, target: pathlib.Path) -> None:
    """`shutil.copy2` — bytes and metadata — landing whole or not at all."""
    target = target.resolve()
    beside = _beside(target)
    try:
        shutil.copy2(source, beside)
        beside.replace(target)
    except OSError:
        with contextlib.suppress(OSError):
            beside.unlink()
        raise


def _beside(target: pathlib.Path) -> pathlib.Path:
    return target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")


def _keep_mode(target: pathlib.Path, beside: pathlib.Path) -> None:
    """The replacement wears the mode the target has, or the one a new file would get."""
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = DEFAULT_MODE
    beside.chmod(mode)


if __name__ == "__main__":
    # A helper is not a command: see `workflows.py` and self-audit round 12.
    sys.stderr.write(
        "verifiable_gates.files is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
