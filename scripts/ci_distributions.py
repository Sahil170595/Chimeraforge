"""Accept the exact wheel and a wheel rebuilt from the sdist, without source shadowing."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import tomllib


def run(*argv: str | Path, cwd: Path | None = None) -> None:
    """Stop immediately when a build, installation or acceptance command fails."""
    subprocess.run([str(arg) for arg in argv], cwd=cwd, check=True)


def interpreter(venv: Path) -> Path:
    """Return the virtual environment interpreter on either supported layout."""
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def accept(wheel: Path, root: Path, temp: Path, requirements: Path, version: str) -> None:
    """Install locked dependencies and the candidate into a separate clean environment."""
    run("uv", "venv", "--python", sys.executable, temp)
    python = interpreter(temp)
    run("uv", "pip", "sync", "--python", python, "--require-hashes", requirements)
    run("uv", "pip", "install", "--python", python, "--no-deps", wheel)
    run(
        python,
        root / "scripts/ci_installed_acceptance.py",
        "--expect-version",
        version,
        "--checkout",
        root,
        cwd=temp,
    )
    run(
        python,
        root / "scripts/ci_local_rest.py",
        "--expect-version",
        version,
        "--checkout",
        root,
        cwd=temp,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    wheels = list((root / "dist").glob("*.whl"))
    sdists = list((root / "dist").glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError("acceptance requires exactly one original wheel and one sdist")
    with tempfile.TemporaryDirectory(prefix="chimeraforge-distributions-") as directory:
        temp = Path(directory)
        requirements = temp / "requirements.txt"
        run(
            "uv",
            "export",
            "--locked",
            "--all-extras",
            "--no-emit-project",
            "--output-file",
            requirements,
            "--quiet",
            cwd=root,
        )
        accept(wheels[0], root, temp / "wheel-venv", requirements, version)
        source = temp / "sdist"
        source.mkdir()
        with tarfile.open(sdists[0]) as archive:
            archive.extractall(source, filter="data")
        projects = list(source.glob("*/pyproject.toml"))
        if len(projects) != 1:
            raise RuntimeError("sdist must contain exactly one project")
        rebuilt = temp / "rebuilt"
        run(
            interpreter(temp / "wheel-venv"),
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            rebuilt,
            projects[0].parent,
            cwd=temp,
        )
        rebuilt_wheels = list(rebuilt.glob("*.whl"))
        if len(rebuilt_wheels) != 1:
            raise RuntimeError("sdist did not produce exactly one wheel")
        accept(rebuilt_wheels[0], root, temp / "sdist-venv", requirements, version)
        print(
            json.dumps(
                {
                    "original_wheel": "accepted",
                    "sdist_rebuilt_wheel": "accepted",
                    "version": version,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
