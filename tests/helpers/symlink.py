"""Shared test helpers."""

import os
import tempfile

# Re-export for convenience so callers can use pytest.mark.skipif directly.
import pytest

_symlink_support = None


def symlink_supported() -> bool:
    """Return True if os.symlink actually works in this environment.

    Windows without Developer Mode / admin privilege raises WinError 1314
    (privilege not held) on every os.symlink call.  Tests that exercise
    symlink-escape logic cannot run there, so they skip.
    """
    global _symlink_support
    if _symlink_support is None:
        try:
            with tempfile.TemporaryDirectory() as d:
                link = os.path.join(d, "link")
                os.symlink(d, link)
                os.unlink(link)
            _symlink_support = True
        except OSError:
            _symlink_support = False
    return _symlink_support


skip_if_no_symlink = pytest.mark.skipif(
    not symlink_supported(),
    reason="os.symlink unavailable (WinError 1314 without privilege/Developer Mode)",
)
