"""Audit installed external pairs AND every universal lock variant.

All locked registry versions are retained without evaluating platform markers.
This is an advisory lookup inventory, not a binary-integrity assertion.
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib
from packaging.utils import canonicalize_name
from packaging.version import Version


def _inventory() -> dict[tuple[str, str], set[str]]:
    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    if (
        type(lock.get("version")) is not int
        or lock["version"] != 1
        or type(lock.get("revision")) is not int
        or lock["revision"] != 5
        or not isinstance(lock.get("package"), list)
    ):
        raise ValueError("Unsupported audit lock schema")
    inventory: dict[tuple[str, str], set[str]] = {}

    def add(name: object, version: object, role: str) -> None:
        if not isinstance(name, str) or not isinstance(version, str):
            raise TypeError("Invalid audit package identity")
        name = canonicalize_name(name, validate=True)
        Version(version)
        inventory.setdefault((name, version), set()).add(role)

    app = canonicalize_name(project["name"], validate=True)
    for dist in importlib.metadata.distributions():
        if canonicalize_name(dist.metadata["Name"], validate=True) != app:
            add(dist.metadata["Name"], dist.version, "installed")
    root_count = 0
    registry_count = 0
    for package in lock["package"]:
        if not isinstance(package, dict):
            raise TypeError("Invalid audit package record")
        source = package.get("source")
        if source == {"editable": "."}:
            if (
                package.get("name") != project["name"]
                or package.get("version") != project["version"]
            ):
                raise ValueError("Unexpected root audit package")
            root_count += 1
            continue
        if (
            not isinstance(source, dict)
            or set(source) != {"registry"}
            or source["registry"] not in {"https://pypi.org/simple"}
        ):
            raise ValueError("Unsupported audit package source")
        add(package.get("name"), package.get("version"), "lock")
        registry_count += 1
    if root_count != 1 or not registry_count:
        raise ValueError("Incomplete audit lock inventory")
    return inventory


def _layers(inventory: dict[tuple[str, str], set[str]]) -> list[list[str]]:
    lookups: dict[str, set[str]] = {}
    for name, original in sorted(inventory):
        version = original
        lookups.setdefault(name, set()).add(version)
    layers: list[list[str]] = [[] for _ in range(max(map(len, lookups.values())))]
    for name, versions in sorted(lookups.items()):
        for index, version in enumerate(
            sorted(versions, key=lambda value: (Version(value), value))
        ):
            layers[index].append(f"{name}=={version}")
    expected = {f"{name}=={version}" for name, versions in lookups.items() for version in versions}
    if {pin for layer in layers for pin in layer} != expected or sum(map(len, layers)) != len(
        expected
    ):
        raise ValueError("Incomplete advisory lookup partition")
    print(
        "advisory inventory: "
        + json.dumps(
            {
                "original_pairs": [
                    {"name": name, "version": version, "roles": sorted(roles)}
                    for (name, version), roles in sorted(inventory.items())
                ],
                "installed_pairs": sum("installed" in roles for roles in inventory.values()),
                "lock_pairs": sum("lock" in roles for roles in inventory.values()),
                "lookup_pairs": len(expected),
                "layers": layers,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return layers


def main() -> None:
    layers = _layers(_inventory())
    failed = False
    with tempfile.TemporaryDirectory(prefix="chimeraforge-audit-") as name:
        for index, pins in enumerate(layers):
            path = Path(name) / f"advisory-{index + 1}.txt"
            path.write_text("\n".join(pins) + "\n", encoding="utf-8")
            print(f"advisory layer {index + 1}/{len(layers)}: {len(pins)} exact pins", flush=True)
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip_audit",
                        "--strict",
                        "--disable-pip",
                        "--no-deps",
                        "--progress-spinner",
                        "off",
                        "--cache-dir",
                        str(Path(name) / "cache"),
                        "-r",
                        str(path),
                    ],
                    check=False,
                    stdin=subprocess.DEVNULL,
                )
                failed |= result.returncode != 0
            except OSError:
                failed = True
                print("advisory layer unavailable", file=sys.stderr)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
