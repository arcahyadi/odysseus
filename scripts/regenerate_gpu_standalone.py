"""Regenerate the standalone GPU compose files from base + overlay.

Stack-management UIs (Portainer, Coolify, Dockhand, ...) accept a single
compose file and do not honor ``COMPOSE_FILE`` or multiple ``-f`` overlays,
so the repo ships ``docker-compose.gpu-nvidia.yml`` and
``docker-compose.gpu-amd.yml`` that inline the GPU overlay into the base
``docker-compose.yml``.

Source of truth:
    docker-compose.yml        +  docker/gpu.nvidia.yml  ->  docker-compose.gpu-nvidia.yml
    docker-compose.yml        +  docker/gpu.amd.yml     ->  docker-compose.gpu-amd.yml

The merge semantics mirror what docker compose does for the keys these
overlays touch (see tests/test_gpu_compose_standalone.py): mappings merge
recursively, list-valued service fields (``environment``, ``group_add``) are
concatenated, scalars are overwritten.

Run:  python scripts/regenerate_gpu_standalone.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docker-compose.yml"
NVIDIA_OVERLAY = ROOT / "docker" / "gpu.nvidia.yml"
AMD_OVERLAY = ROOT / "docker" / "gpu.amd.yml"
NVIDIA_STANDALONE = ROOT / "docker-compose.gpu-nvidia.yml"
AMD_STANDALONE = ROOT / "docker-compose.gpu-amd.yml"

SERVICE = "odysseus"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Mirror docker compose overlay semantics for the keys we use."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif isinstance(value, list) and isinstance(result.get(key), list):
            result[key] = copy.deepcopy(result[key]) + copy.deepcopy(value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _merge_overlay_into_base(base: dict, overlay: dict) -> dict:
    """base + overlay merged into the odysseus service only."""
    expected = copy.deepcopy(base)
    overlay_service = overlay["services"][SERVICE]
    expected["services"][SERVICE] = _deep_merge(expected["services"][SERVICE], overlay_service)
    return expected


def _dump(config: dict) -> str:
    return yaml.safe_dump(
        config,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=120,
    )


def main() -> int:
    base = _load(BASE)
    pairs = [
        (NVIDIA_OVERLAY, NVIDIA_STANDALONE),
        (AMD_OVERLAY, AMD_STANDALONE),
    ]
    for overlay_path, out_path in pairs:
        overlay = _load(overlay_path)
        standalone = _merge_overlay_into_base(base, overlay)
        out_path.write_text(_dump(standalone), encoding="utf-8")
        print(f"regenerated {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
