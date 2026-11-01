"""Record actual scoped release gates without changing historical validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from packaging.utils import parse_wheel_filename

BASE = "f31761fb13f223e356aab1e4e7b0502a736dc6d8"
ROOT = Path(__file__).resolve().parents[2]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gates", type=Path, required=True)
    args = parser.parse_args()
    gates = json.loads(args.gates.read_text(encoding="utf-8"))
    commands = gates["commands"]
    assert commands and all(command["exit"] == 0 for command in commands)
    for command in commands:
        assert digest(Path(command["log"]).read_bytes()) == command["log_sha256"]
    audit = next(command for command in commands if command["name"] == "advisory")
    text = Path(audit["log"]).read_text(encoding="utf-8")
    inventory = json.loads(
        next(
            line.removeprefix("advisory inventory: ")
            for line in text.splitlines()
            if line.startswith("advisory inventory: ")
        )
    )
    assert text.count("No known vulnerabilities found") == len(inventory["layers"])
    assert sum(map(len, inventory["layers"])) == inventory["lookup_pairs"]
    assert all(
        len(layer) == len({pin.split("==")[0] for pin in layer}) for layer in inventory["layers"]
    )
    expected = {f"{p['name']}=={p['version']}" for p in inventory["original_pairs"]}
    assert {pin for layer in inventory["layers"] for pin in layer} == expected
    counts = Counter(p["name"] for p in inventory["original_pairs"])
    assert len(inventory["layers"]) == max(counts.values())

    old = tomllib.loads(git("show", f"{BASE}:uv.lock").decode())
    new = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))

    def identity(package: dict) -> tuple:
        return package["name"], package["version"], json.dumps(package["source"], sort_keys=True)

    old_map = {identity(package): package for package in old["package"]}
    new_map = {identity(package): package for package in new["package"]}
    assert not (new_map.keys() - old_map.keys())
    changed = []
    pruned = []
    for key in sorted(new_map):
        before, after = old_map[key], new_map[key]
        assert before.get("sdist") == after.get("sdist")
        assert all(wheel in before.get("wheels", []) for wheel in after.get("wheels", []))
        if before != after:
            changed.append(
                {
                    "name": key[0],
                    "version": key[1],
                    "fields": sorted(
                        field
                        for field in before.keys() | after.keys()
                        if before.get(field) != after.get(field)
                    ),
                }
            )
        for wheel in before.get("wheels", []):
            if wheel not in after.get("wheels", []):
                filename = unquote(Path(urlsplit(wheel["url"]).path).name)
                tags = parse_wheel_filename(filename)[3]
                assert all(
                    tag.interpreter in {"cp310", "pp310"} and tag.abi != "abi3" for tag in tags
                )
                pruned.append({"name": key[0], "filename": filename})
    marker = "## [0.81.0] - 2026-10-29"
    old_history = git("show", f"{BASE}:CHANGELOG.md").decode().split(marker, 1)[1]
    new_history = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split(marker, 1)[1]
    assert old_history == new_history
    assert git("diff", BASE, "--name-only", "--", "src/chimeraforge") == b""
    existing_tests = set(git("ls-tree", "-r", "--name-only", BASE, "tests").decode().splitlines())
    changed_tests = set(git("diff", BASE, "--name-only", "--", "tests").decode().splitlines())
    assert not (existing_tests & changed_tests)
    old_validation = git("ls-tree", "-r", BASE, "validation").splitlines()
    old_validation_paths = {line.decode().split("\t", 1)[1] for line in old_validation}
    changed_validation = set(
        git("diff", BASE, "--name-only", "--", "validation").decode().splitlines()
    )
    assert not (old_validation_paths & changed_validation)
    package_paths = (
        git("ls-tree", "-r", "--name-only", BASE, "src/chimeraforge").decode().splitlines()
    )
    root = ET.parse(gates["junit"]).getroot()
    cases = root.findall(".//testcase")
    assert cases and not root.findall(".//failure") and not root.findall(".//error")
    paths = [
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        "scripts/ci_dependency_audit.py",
        "tests/test_ci_dependency_audit.py",
        "README.md",
        "CLAUDE.md",
        "CHANGELOG.md",
        "docs/ci.md",
        "docs/quick_start.md",
        "docs/authenticated-active.md",
        "server.json",
        "src/chimeraforge/__init__.py",
        "validation/2026-10-31-release082-security/regenerate.py",
    ]
    result = {
        "candidate": "0.82.0",
        "recorded_on": "2026-10-31",
        "base": BASE,
        "python_floor": ">=3.11",
        "filelock_requirement": ">=4.2.1,<5",
        "graph": {
            "before_nodes": len(old_map),
            "after_nodes": len(new_map),
            "after_names": len({key[0] for key in new_map}),
            "removed": [
                {"name": key[0], "version": key[1]}
                for key in sorted(old_map.keys() - new_map.keys())
            ],
            "added": [],
            "surviving_changes": changed,
            "pruned_unsupported_wheels": len(pruned),
            "pruned_interpreters_only": ["cp310", "pp310"],
            "abi3_pruned": 0,
            "retained_artifact_metadata_exact": True,
        },
        "advisory": inventory,
        "scoped": {
            "qualification_basis": (
                "Executed on release/security A; held runtime/static/advisory "
                "facts carry to docs-only B."
            ),
            "commands": len(commands),
            "all_exit_zero": True,
            "passed": len(cases) - len(root.findall(".//skipped")),
            "skipped": len(root.findall(".//skipped")),
            "audit_log_sha256": audit["log_sha256"],
        },
        "held": {
            "application_git_files": len(package_paths),
            "application_python_files": sum(path.endswith(".py") for path in package_paths),
            "application_git_content_equal_base": True,
            "existing_tests_unchanged": True,
            "old_validation_files": len(old_validation),
            "published_history_basis": "complete 0.81 marker suffix, Git LF versus read_text LF",
            "published_history_sha256": digest((marker + new_history).encode()),
        },
        "source_sha256_basis": "actual current raw bytes",
        "source_sha256": {path: digest((ROOT / path).read_bytes()) for path in paths},
        "limits": [
            "No new local full/native-wheel run claimed; "
            "earlier feature results remain historical.",
            "Fresh hosted CI, tagged artifact, publication and "
            "cryptographic acceptance are separate.",
            "Advisory lookup observations do not establish absence of compromise.",
        ],
    }
    path = Path(__file__).with_name("summary.json")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(path),
                "registry_pairs": inventory["lock_pairs"],
                "installed_pairs": inventory["installed_pairs"],
                "lookups": inventory["lookup_pairs"],
                "layer_sizes": list(map(len, inventory["layers"])),
                "passed": result["scoped"]["passed"],
            }
        )
    )


if __name__ == "__main__":
    main()
