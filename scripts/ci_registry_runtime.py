"""Exercise the registry's exact uvx command against candidate or public wheels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PACKAGE = "chimeraforge"


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
    args = parser.parse_args()
    expected = args.expect_version
    if expected is None:
        import tomllib

        expected = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    command = registry_command(metadata, expected, args.candidate_dist)
    from probe_mcp_stdio import probe

    info, tools = probe(command)
    assert info.get("version") == expected, (info, expected)
    print(json.dumps({"serverInfo": info, "tools": tools, "tool_calls": "passed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
