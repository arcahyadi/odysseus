"""Windows-friendly bash availability helper.

WSL's bash.exe exists on Windows but fails at runtime when no distro is
installed (``execvpe(/bin/bash) failed``).  Tests that execute real bash
scripts must skip when bash cannot actually run.
"""

from __future__ import annotations

import shutil
import subprocess

_cache: bool | None = None


def bash_available() -> bool:
    """Return True when ``bash`` resolves AND executes a trivial command."""
    global _cache
    if _cache is None:
        exe = shutil.which("bash")
        if not exe:
            _cache = False
        else:
            try:
                proc = subprocess.run(
                    [exe, "-c", "echo ok"],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                _cache = proc.returncode == 0
            except (OSError, subprocess.SubprocessError):
                _cache = False
    return _cache


def skip_if_no_bash() -> None:
    """pytest.skip() when bash cannot actually execute on this host."""
    if not bash_available():
        import pytest

        pytest.skip("bash (WSL) not available on this host")
