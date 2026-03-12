"""Environment fingerprinting for TR137 synthesis reproducibility.

Captures the synthesis environment (Python, packages, platform) rather than
GPU/CUDA (TR137 runs no experiments). Adapted from TR126's env_fingerprint.py.
"""

from __future__ import annotations

import os
import platform
import sys
from typing import Any


def capture_environment() -> dict[str, Any]:
    """Capture environment fingerprint for the synthesis run."""
    env: dict[str, Any] = {
        "platform": platform.platform(),
        "platform_system": platform.system(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "machine": platform.machine(),
    }

    # Key packages for synthesis
    for pkg_name in ("numpy", "scipy", "pandas"):
        try:
            mod = __import__(pkg_name)
            env[f"{pkg_name}_version"] = mod.__version__
        except ImportError:
            env[f"{pkg_name}_version"] = None

    # Ollama availability (source TRs depend on it)
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:11434/api/version",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            import json

            data = json.loads(resp.read())
            env["ollama_available"] = True
            env["ollama_version"] = data.get("version")
    except Exception:
        env["ollama_available"] = False
        env["ollama_version"] = None

    # Docker detection
    env["in_docker"] = (
        os.path.exists("/.dockerenv") or os.environ.get("container") == "docker"
    )

    return env
