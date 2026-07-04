"""Claude Code PostToolUse hook: fast lint of the just-edited file.

stdin: hook JSON {tool_name, tool_input: {file_path}, ...}
exit 0: clean / not lintable / linter unavailable (never block edits on infra)
exit 2: findings -> stderr is fed back to the model to fix immediately

Per-file checks only. Project-wide gates (pytest/cargo/tsc) live in the
/verify skill and CI, not in an edit hook. Self-adapting: flake8/eslint run
only when the repo has a config for them, so the hook is zero-noise in repos
that are not lint-clean yet.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

TIMEOUT_S = 45
PY_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
NODE_CHECK_EXTS = {".js", ".mjs", ".cjs"}


def _run(cmd: list) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _flake8_configured() -> bool:
    if Path(".flake8").exists():
        return True
    for name in ("setup.cfg", "tox.ini"):
        p = Path(name)
        if p.exists() and "[flake8]" in p.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def _eslint_configured() -> bool:
    return bool(list(Path(".").glob("eslint.config.*")) or list(Path(".").glob(".eslintrc*")))


def check_python(path: Path) -> str:
    proc = _run([sys.executable, "-m", "py_compile", str(path)])
    if proc is not None and proc.returncode != 0:
        return (proc.stderr or proc.stdout).strip()
    if _flake8_configured():
        proc = _run([sys.executable, "-m", "flake8", str(path)])
        if proc is None:
            return ""
        out = (proc.stdout + proc.stderr).strip()
        if proc.returncode != 0 and out and "No module named" not in out:
            return out
    return ""


def check_js(path: Path) -> str:
    if _eslint_configured():
        npx = shutil.which("npx")
        if npx:
            proc = _run([npx, "eslint", "--no-warn-ignored", str(path)])
            if proc is not None:
                out = (proc.stdout + proc.stderr).strip()
                if proc.returncode != 0 and out:
                    return out
        return ""
    if path.suffix.lower() in NODE_CHECK_EXTS:
        node = shutil.which("node")
        if node:
            proc = _run([node, "--check", str(path)])
            if proc is not None and proc.returncode != 0:
                return (proc.stderr or proc.stdout).strip()
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = payload.get("tool_input") or {}
    fp = tool_input.get("file_path") or (payload.get("tool_response") or {}).get("filePath")
    if not fp:
        return 0
    path = Path(fp)
    if not path.exists():
        return 0
    ext = path.suffix.lower()
    if ext in PY_EXTS:
        findings = check_python(path)
    elif ext in JS_EXTS:
        findings = check_js(path)
    else:
        return 0
    if findings:
        sys.stderr.write(f"[lint hook] {path.name}:\n{findings}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
