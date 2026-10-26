import subprocess
from pathlib import Path

import pytest

from core.platform_compat import find_bash


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-docker-amd-gpu.sh"
_BASH = find_bash()

pytestmark = pytest.mark.skipif(
    _BASH is None,
    reason="check-docker-amd-gpu.sh is a bash script; no real bash on PATH (Windows/WSL shim excluded)",
)


def test_amd_gpu_check_rejects_unknown_extra_arg_before_diagnostics():
    proc = subprocess.run(
        [_BASH, str(SCRIPT), "--bad-option"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert proc.returncode == 1
    assert "Unknown option: --bad-option" in proc.stderr


def test_amd_gpu_check_shell_syntax():
    subprocess.run([_BASH, "-n", str(SCRIPT)], check=True)
