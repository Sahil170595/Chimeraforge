"""Exercise the registry's exact uvx command against candidate or public wheels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PACKAGE = "chimeraforge"
MAX_INDEX_WAIT_SECONDS = 300
INDEX_POLL_SECONDS = 10
INDEX_REQUEST_TIMEOUT_SECONDS = 15
RESOLVER_TIMEOUT_SECONDS = 60
# The pinned uv 0.12.23 client negotiates this representation; PyPI varies on Accept.
UV_SIMPLE_ACCEPT = (
    "application/vnd.pypi.simple.v1+json, "
    "application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"
)
PYTHON_LIBRARY_RE = re.compile(r"\blibpython\d+\.\d+\.so(?:\.\d+)*\b")


def public_resolution_ready(
    version: str, timeout: float, *, candidate_dist: Path | None = None
) -> bool:
    """Resolve without installing, using the SDK's actual child environment boundary."""
    from mcp.client.stdio import get_default_environment

    command = [
        "uv",
        "pip",
        "install",
        "--dry-run",
        "--reinstall",
        "--no-cache",
        "--python",
        sys.executable,
    ]
    if candidate_dist is not None:
        command += ["--find-links", str(candidate_dist.resolve(strict=True))]
    command.append(f"{PACKAGE}[mcp]=={version}")
    result = subprocess.run(
        command,
        cwd=tempfile.gettempdir(),
        env=get_default_environment(),
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode == 0:
        return True
    error = " ".join(result.stderr.split())
    missing = f"Because there is no version of {PACKAGE}=={version} and "
    if result.returncode == 1 and missing in error and f"you require {PACKAGE}" in error:
        return False
    diagnostic = {"version": version, "exit_code": result.returncode, "reason": "resolver_error"}
    library = PYTHON_LIBRARY_RE.search(error)
    if "error while loading shared libraries" in error and library is not None:
        diagnostic.update(reason="python_shared_library", library=library.group())
    elif "unexpected argument" in error:
        diagnostic["reason"] = "cli_unknown_argument"
    elif "Failed to inspect Python interpreter" in error:
        diagnostic["reason"] = "python_discovery"
    print(json.dumps({"uv_resolution_failure": diagnostic}), flush=True)
    raise RuntimeError(f"Public exact-version resolution failed (uv exit {result.returncode})")


def public_files_ready(release: dict, simple: dict, version: str) -> bool:
    """JSON visibility alone does not prove the installer's exact files are indexed."""
    if release.get("info", {}).get("version") != version:
        return False
    files = release.get("urls", [])
    if len(files) != 2 or {row["packagetype"] for row in files} != {"bdist_wheel", "sdist"}:
        return False
    if any(row["yanked"] is not False for row in files):
        return False
    expected = {row["filename"]: row["digests"]["sha256"] for row in files}
    indexed = {row["filename"]: row for row in simple.get("files", [])}
    return len(expected) == 2 and all(
        name in indexed
        and indexed[name]["hashes"].get("sha256") == digest
        and indexed[name].get("yanked") is False
        for name, digest in expected.items()
    )


def wait_for_public_files(version: str) -> None:
    """Poll exact version/file/hash readiness; the application probe runs only once."""
    deadline = time.monotonic() + MAX_INDEX_WAIT_SECONDS
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        payloads = []
        for url in (
            f"https://pypi.org/pypi/{PACKAGE}/{version}/json",
            f"https://pypi.org/simple/{PACKAGE}/",
        ):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "PyPI exact files did not become installable within the deadline"
                )
            accept = UV_SIMPLE_ACCEPT if "/simple/" in url else "application/json"
            request = Request(url, headers={"Accept": accept})
            try:
                with urlopen(
                    request, timeout=min(INDEX_REQUEST_TIMEOUT_SECONDS, remaining)
                ) as response:
                    payloads.append(json.loads(response.read()))
            except HTTPError as error:
                if error.code != 404:
                    raise
                payloads.append({})
        files_ready = public_files_ready(*payloads, version)
        resolver_ready = None
        if files_ready:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("PyPI resolution did not qualify within the deadline")
            resolver_ready = public_resolution_ready(
                version, min(RESOLVER_TIMEOUT_SECONDS, remaining)
            )
        if time.monotonic() >= deadline:
            raise TimeoutError("PyPI resolution did not qualify within the deadline")
        ready = files_ready and resolver_ready is True
        print(
            json.dumps(
                {
                    "pypi_index_readiness": {
                        "version": version,
                        "attempt": attempt,
                        "ready": ready,
                        "files_ready": files_ready,
                        "resolver_ready": resolver_ready,
                    }
                }
            ),
            flush=True,
        )
        if ready:
            return
        time.sleep(min(INDEX_POLL_SECONDS, max(0, deadline - time.monotonic())))
    raise TimeoutError("PyPI exact files did not become installable within the deadline")


def registry_command(
    metadata: dict, expected_version: str, candidate_dist: Path | None = None
) -> list[str]:
    """Mirror the supported single-PyPI-package registry client launch shape."""
    assert metadata["version"] == expected_version
    packages = metadata["packages"]
    assert len(packages) == 1
    package = packages[0]
    assert package["registryType"] == "pypi" and package["runtimeHint"] == "uvx"
    assert package["identifier"] == PACKAGE and package["version"] == expected_version
    assert package["transport"] == {"type": "stdio"}
    runtime = package["runtimeArguments"]
    assert len(runtime) == 1 and runtime[0]["type"] == "named"
    assert runtime[0]["name"] == "--with"
    assert runtime[0]["value"] == f"{PACKAGE}[mcp]=={expected_version}"
    assert package["packageArguments"] == [{"type": "positional", "value": "mcp"}]
    assert "registryBaseUrl" not in package
    command = ["uvx", "--no-cache", runtime[0]["name"], runtime[0]["value"]]
    if candidate_dist is not None:
        directory = candidate_dist.resolve(strict=True)
        assert (directory / f"{PACKAGE}-{expected_version}-py3-none-any.whl").is_file()
        command += ["--find-links", str(directory)]
    command += [f"{package['identifier']}@{package['version']}", "mcp"]
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=Path("server.json"))
    parser.add_argument("--expect-version")
    parser.add_argument("--candidate-dist", type=Path)
    parser.add_argument("--wait-pypi", action="store_true")
    args = parser.parse_args()
    expected = args.expect_version
    if expected is None:
        import tomllib

        expected = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    command = registry_command(metadata, expected, args.candidate_dist)
    if args.wait_pypi:
        assert args.candidate_dist is None, "index readiness is for the public invocation only"
        wait_for_public_files(expected)
    elif args.candidate_dist is not None:
        assert public_resolution_ready(
            expected, RESOLVER_TIMEOUT_SECONDS, candidate_dist=args.candidate_dist
        ), "native resolution refused the existing candidate wheel"
    from probe_mcp_stdio import probe

    info, tools = probe(command)
    assert info.get("version") == expected, (info, expected)
    print(json.dumps({"serverInfo": info, "tools": tools, "tool_calls": "passed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
