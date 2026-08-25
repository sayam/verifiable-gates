"""Fixtures shared by the test files that install the bundle somewhere."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import bundle
import pytest

from verifiable_gates import manifest as manifest_module

if TYPE_CHECKING:
    import pathlib


@pytest.fixture
def bundle_copy(tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the bundle, so a test may remove a file from it without harm."""
    target = tmp_path / "bundle"
    target.mkdir()
    manifest = manifest_module.load(bundle.BUNDLE / "overlay.json")
    for name in manifest_module.shipped(manifest):
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle.BUNDLE / name, destination)
    return target
