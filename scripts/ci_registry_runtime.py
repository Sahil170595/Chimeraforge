"""Exercise the registry's exact uvx command against candidate or public wheels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PACKAGE = "chimeraforge"
MAX_INDEX_WAIT_SECONDS = 300
INDEX_POLL_SECONDS = 10
INDEX_REQUEST_TIMEOUT_SECONDS = 15
PROBE_TIMEOUT_SECONDS = 120
MAX_NATIVE_STDERR_BYTES = 64 * 1024
MAX_NATIVE_RECEIPT_BYTES = 16 * 1024
# The pinned uv 0.12.23 client negotiates this representation; PyPI varies on Accept.
UV_SIMPLE_ACCEPT = (
    "application/vnd.pypi.simple.v1+json, "
    "application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"
)
PYTHON_LIBRARY_RE = re.compile(r"\blibpython\d+\.\d+\.so(?:\.\d+)*\b")
ABSENT_PACKAGE_RE = re.compile(r"\bno versions? of ([A-Za-z0-9][A-Za-z0-9._-]*)")
MAX_DIAGNOSTIC_PACKAGES = 32
RESOLVER_HINTS = (
    (
        "requires_python",
        re.compile(
            r"requires? Python|Python requirement|requires-python|"
            r"Python interpreter uses a Python version that is not supported by your dependencies",
            re.I,
        ),
    ),
    (
        "wheel_tag",
        re.compile(
            r"compatible wheels?|wheel tags?|"
            r"only found wheels.{0,256}Python (?:implementation|ABI) tags?",
            re.I,
        ),
    ),
    (
        "invalid_metadata",
        re.compile(
            r"invalid metadata|failed to parse metadata|Metadata for .{0,256}could not be parsed",
            re.I,
        ),
    ),
    (
        "http_status",
        re.compile(
            r"HTTP.*?status(?: code)?\s+[45]\d\d|"
            r"An index(?: URL)?.{0,256}(?:401 Unauthorized|403 Forbidden)|"
            r"the server returned:\s*`?[45]\d\d",
            re.I,
        ),
    ),
)


def public_package_names() -> set[str]:
    """Only names already declared in the checkout's canonical public-PyPI lock."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    lock = Path(__file__).resolve().parents[1] / "uv.lock"
    with lock.open("rb") as stream:
        packages = tomllib.load(stream)["package"]
    return {PACKAGE} | {
        row["name"]
        for row in packages
        if row.get("source", {}).get("registry") == "https://pypi.org/simple"
    }


def resolution_context(error: str, version: str, public_names: set[str]) -> dict:
    """Observed diagnostic hints, never raw clauses or a reason to widen retries."""
    boundary = r"(?=\s|[,;]|$)"
    shape = "none"
    for label, pattern in (
        ("singleton", rf"\bno version of {PACKAGE}=={re.escape(version)}{boundary}"),
        ("plural", rf"\bno versions of {PACKAGE}{boundary}"),
        ("extra", rf"\bno version of {PACKAGE}\[[^\]\s]+\]=={re.escape(version)}{boundary}"),
    ):
        if re.search(pattern, error):
            shape = label
            break
    missing = sorted(set(ABSENT_PACKAGE_RE.findall(error)) & public_names)
    hints = [name for name, pattern in RESOLVER_HINTS if pattern.search(error)]
    return {
        "no_solution": "no solution found" in error.lower(),
        "root_absence_shape": shape,
        "missing_public_packages": missing[:MAX_DIAGNOSTIC_PACKAGES],
        "cause_hints": hints or ["unknown"],
    }


def native_root_absence(error: str, version: str) -> bool:
    """Only the complete observed uv 0.12.23 pre-application proof permits retry."""
    expected = (
        "error: No solution found when resolving tool dependencies cause: "
        f"Because there is no version of {PACKAGE}=={version} and "
        f"you require {PACKAGE}=={version}, we can conclude that "
        "your requirements are unsatisfiable."
    )
    return " ".join(error.split()) == expected


def native_diagnostic(error: str, version: str) -> dict:
    """Project a closed categorical diagnostic; never disclose raw native stderr."""
    diagnostic = {"reason": "resolver_error"}
    diagnostic.update(resolution_context(error, version, public_package_names()))
    library = PYTHON_LIBRARY_RE.search(error)
    if "error while loading shared libraries" in error and library is not None:
        diagnostic.update(reason="python_shared_library", library=library.group())
    elif "unexpected argument" in error:
        diagnostic["reason"] = "cli_unknown_argument"
    elif "Failed to inspect Python interpreter" in error:
        diagnostic["reason"] = "python_discovery"
    return diagnostic


def command_digest(command: list[str]) -> str:
    """Bind a private receipt to the exact native argv."""
    return hashlib.sha256(json.dumps(command, ensure_ascii=True).encode("utf-8")).hexdigest()


def native_runner_command(command: list[str], version: str, receipt: Path) -> list[str]:
    """Wrap the unchanged registry argv using the observed SDK interpreter."""
    return [
        sys.executable,
        "-B",
        str(Path(__file__).with_name("ci_registry_native_runner.py")),
        "--receipt",
        str(receipt),
        "--version",
        version,
        "--",
        *command,
    ]


def read_native_receipt(path: Path, command: list[str]) -> dict:
    """Missing, oversized, incomplete, or mismatched control evidence is terminal."""
    fields = {
        "schema",
        "command_sha256",
        "native_exit",
        "stdout_bytes",
        "stderr_bytes",
        "stream_error",
        "stderr_overflow",
        "reaped",
        "drained",
        "root_absent",
        "diagnostic",
    }
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError
        with path.open("rb") as stream:
            raw = stream.read(MAX_NATIVE_RECEIPT_BYTES + 1)
        if len(raw) > MAX_NATIVE_RECEIPT_BYTES:
            raise ValueError
        result = json.loads(raw)
        if not isinstance(result, dict) or set(result) != fields:
            raise ValueError
        if type(result["schema"]) is not int or result["schema"] != 1:
            raise ValueError
        if result["command_sha256"] != command_digest(command):
            raise ValueError
        for key in ("native_exit", "stdout_bytes", "stderr_bytes"):
            if type(result[key]) is not int:
                raise ValueError
        if result["stdout_bytes"] < 0 or result["stderr_bytes"] < 0:
            raise ValueError
        for key in ("stream_error", "stderr_overflow", "reaped", "drained", "root_absent"):
            if type(result[key]) is not bool:
                raise ValueError
        if result["stderr_overflow"] != (result["stderr_bytes"] > MAX_NATIVE_STDERR_BYTES):
            raise ValueError
        diagnostic = result["diagnostic"]
        if not isinstance(diagnostic, dict) or set(diagnostic) not in (
            {
                "reason",
                "no_solution",
                "root_absence_shape",
                "missing_public_packages",
                "cause_hints",
            },
            {
                "reason",
                "no_solution",
                "root_absence_shape",
                "missing_public_packages",
                "cause_hints",
                "library",
            },
        ):
            raise ValueError
        # Re-validate all values before publishing even this private control channel.
        if (
            diagnostic["reason"]
            not in {
                "resolver_error",
                "python_shared_library",
                "cli_unknown_argument",
                "python_discovery",
            }
            or type(diagnostic["no_solution"]) is not bool
        ):
            raise ValueError
        if diagnostic["root_absence_shape"] not in {"none", "singleton", "plural", "extra"}:
            raise ValueError
        names = diagnostic["missing_public_packages"]
        if not isinstance(names, list) or len(names) > MAX_DIAGNOSTIC_PACKAGES:
            raise ValueError
        if any(not isinstance(name, str) or name not in public_package_names() for name in names):
            raise ValueError
        hints = diagnostic["cause_hints"]
        if not isinstance(hints, list) or not hints or len(hints) > len(RESOLVER_HINTS):
            raise ValueError
        if any(hint not in {"unknown", *(name for name, _ in RESOLVER_HINTS)} for hint in hints):
            raise ValueError
        if "library" in diagnostic and (
            not isinstance(diagnostic["library"], str)
            or PYTHON_LIBRARY_RE.fullmatch(diagnostic["library"]) is None
        ):
            raise ValueError
        if result["root_absent"] and (
            result["stderr_bytes"] == 0
            or result["stderr_overflow"]
            or diagnostic
            != {
                "reason": "resolver_error",
                "no_solution": True,
                "root_absence_shape": "singleton",
                "missing_public_packages": [PACKAGE],
                "cause_hints": ["unknown"],
            }
        ):
            raise ValueError
        return result
    except (OSError, ValueError, TypeError, KeyError):
        raise RuntimeError("Native registry control receipt is missing or malformed") from None


def retryable_native_absence(receipt: dict) -> bool:
    """Never turn a generic SDK/application failure into a resolution retry."""
    return (
        receipt["native_exit"] == 1
        and receipt["stdout_bytes"] == 0
        and receipt["root_absent"]
        and receipt["reaped"]
        and receipt["drained"]
        and not receipt["stream_error"]
        and not receipt["stderr_overflow"]
    )


def probe_registry(
    command: list[str], version: str, deadline: float, *, retry_absence: bool
) -> tuple[dict, list[str]]:
    """Close each SDK attempt before retrying only proven native pre-app absence."""
    from probe_mcp_stdio import probe

    attempt = 0
    with tempfile.TemporaryDirectory(prefix="cf-registry-control-") as directory:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Native registry qualification exceeded its deadline")
            attempt += 1
            receipt_path = Path(directory) / f"attempt-{attempt}.json"
            wrapped = native_runner_command(command, version, receipt_path)
            try:
                info, tools = probe(wrapped, timeout=remaining)
            except Exception:
                # probe returns/raises only after the public SDK context has closed.
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Native registry qualification exceeded its deadline"
                    ) from None
                receipt = read_native_receipt(receipt_path, command)
                print(
                    json.dumps(
                        {
                            "native_registry_failure": {
                                "version": version,
                                "attempt": attempt,
                                "sdk_python": sys.executable,
                                "exit_code": receipt["native_exit"],
                                "stdout_bytes": receipt["stdout_bytes"],
                                "stderr_overflow": receipt["stderr_overflow"],
                                **receipt["diagnostic"],
                            }
                        }
                    ),
                    flush=True,
                )
                if not retry_absence or not retryable_native_absence(receipt):
                    raise RuntimeError("Native registry application qualification failed") from None
                time.sleep(min(INDEX_POLL_SECONDS, max(0, deadline - time.monotonic())))
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError("Native registry qualification exceeded its deadline")
            # Success is also bound to a completed native launch and the same argv.
            receipt = read_native_receipt(receipt_path, command)
            if receipt["native_exit"] != 0 or not receipt["reaped"] or not receipt["drained"]:
                raise RuntimeError("Native registry application did not exit cleanly")
            if receipt["stream_error"] or receipt["stderr_overflow"]:
                raise RuntimeError("Native registry application transport did not complete")
            return info, tools


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


def wait_for_public_files(version: str, deadline: float) -> None:
    """Poll exact public version/file/hash visibility within the shared deadline."""
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
                raise TimeoutError("PyPI exact files did not become visible within the deadline")
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
        ready = public_files_ready(payloads[0], payloads[1], version)
        if time.monotonic() >= deadline:
            raise TimeoutError("PyPI exact files did not become visible within the deadline")
        print(
            json.dumps(
                {
                    "pypi_index_readiness": {
                        "version": version,
                        "attempt": attempt,
                        "files_ready": ready,
                    }
                }
            ),
            flush=True,
        )
        if ready:
            return
        time.sleep(min(INDEX_POLL_SECONDS, max(0, deadline - time.monotonic())))
    raise TimeoutError("PyPI exact files did not become visible within the deadline")


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
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        expected = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    command = registry_command(metadata, expected, args.candidate_dist)
    deadline = time.monotonic() + (
        MAX_INDEX_WAIT_SECONDS if args.wait_pypi else PROBE_TIMEOUT_SECONDS
    )
    if args.wait_pypi:
        assert args.candidate_dist is None, "index readiness is for the public invocation only"
        wait_for_public_files(expected, deadline)
    info, tools = probe_registry(command, expected, deadline, retry_absence=args.wait_pypi)
    assert info.get("version") == expected, (info, expected)
    print(json.dumps({"serverInfo": info, "tools": tools, "tool_calls": "passed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
