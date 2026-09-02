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
is kept, because a scanner the installer rewrites runs by its mode; a file that did not
exist is created `0o644` before the umask, so the sibling is never, even for the length
of the write, a file anyone could write to. A symlink is written *through*, as
`write_text` did, not replaced by a file. Whatever the write raises is raised: every
caller already answers an `OSError` in a sentence of its own.

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

__all__ = ["copy_atomically", "write_bytes_atomically", "write_text_atomically"]

_CREATE = os.O_WRONLY | os.O_CREAT | os.O_EXCL
# The mode a file that did not exist is created with, before the umask narrows it.
# Not `0o666`: the sibling exists under its own name for the length of the write, and
# for that moment a mode the umask does not narrow would be a file anyone could write
# (CodeQL `py/overly-permissive-file`, on the first push of this change). A file that
# already exists keeps the mode it had — see `_keep_mode`.
_NEW_FILE = 0o644


def write_text_atomically(path: pathlib.Path, text: str, encoding: str = "utf-8") -> None:
    """`text` as `path`, whole or not at all."""
    write_bytes_atomically(path, text.encode(encoding))


def write_bytes_atomically(path: pathlib.Path, data: bytes) -> None:
    """`data` as `path`, whole or not at all: a sibling file, flushed, renamed over."""
    target = path.resolve()
    beside = _beside(target)
    try:
        with os.fdopen(os.open(beside, _CREATE, _NEW_FILE), "wb") as out:
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
    """A file that exists keeps its mode; a new one gets the process's default."""
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        return
    beside.chmod(mode)


if __name__ == "__main__":
    # A helper is not a command: see `workflows.py` and self-audit round 12.
    sys.stderr.write(
        "verifiable_gates.files is a helper, not a command — it has no entry point of\n"
        "its own; the readers that answer for themselves are listed in CONTRIBUTING.\n"
    )
    sys.exit(2)
