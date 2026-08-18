"""Repo-convention guards.

Both of these encode a rule that has already been broken more than once, where
the breakage is invisible until it reaches someone else: non-ASCII bytes that
render as mojibake on a cp1252 console, and a server.json version that drifts
away from the package it claims to describe.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("src", "tests")


def _python_files() -> list[pathlib.Path]:
    return sorted(p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py"))


def test_there_are_python_files_to_check():
    # Guard the guard: a bad glob would make the ASCII test vacuously pass.
    assert len(_python_files()) > 20


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_source_is_ascii_only(path: pathlib.Path):
    """CLAUDE.md: ASCII-only in all files, for universal compatibility.

    Smart quotes, em-dashes and arrows arrive by copy-paste and survive review
    because they look right in the editor; they show up as mojibake on a Windows
    cp1252 console, and have twice crashed a plain `print()` of tool output.
    """
    offenders = [
        (n, sorted({c for c in line if ord(c) > 127}))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if any(ord(c) > 127 for c in line)
    ]
    assert not offenders, (
        f"non-ASCII in {path.relative_to(ROOT)}: "
        + "; ".join(f"line {n}: {[hex(ord(c)) for c in cs]}" for n, cs in offenders)
        + ". Use -- for an em-dash, -> for an arrow, and spell out symbols."
    )


class TestServerJsonStaysInSync:
    """server.json pins the version the MCP registry will advertise.

    The registry rejects a version that is not live on PyPI, and 0.12.3 shipped
    with server.json still pointing at 0.12.2 -- so the registry entry silently
    described an older release than the package.
    """

    @pytest.fixture(scope="class")
    def server_json(self) -> dict:
        return json.loads((ROOT / "server.json").read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def pyproject_version(self) -> str:
        # Read with a regex rather than tomllib: tomllib is 3.11+ stdlib and this
        # project supports 3.10, so importing it fails on the oldest Python in CI.
        # The [project] version line is a stable one-liner, so this is enough.
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        assert match, "no version line in pyproject.toml"
        return match.group(1)

    def test_server_version_matches_package(self, server_json, pyproject_version):
        assert server_json["version"] == pyproject_version

    def test_package_entry_version_matches(self, server_json, pyproject_version):
        assert server_json["packages"][0]["version"] == pyproject_version

    def test_dunder_version_matches(self, pyproject_version):
        import chimeraforge

        assert chimeraforge.__version__ == pyproject_version

    def test_claude_md_version_line_matches(self, pyproject_version):
        # This line silently drifted two releases behind before it was guarded.
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        match = re.search(r"^\*\*Version:\*\* (\S+)", text, re.MULTILINE)
        assert match, "no **Version:** line in CLAUDE.md"
        assert match.group(1) == pyproject_version

    def test_description_within_registry_limit(self, server_json):
        # The registry returns 422 above 100 characters.
        assert len(server_json["description"]) <= 100

    def test_ownership_token_present_in_readme(self, server_json):
        # Proves PyPI package ownership; the registry reads it from the published
        # description, so it must match server.json's name exactly.
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert f"mcp-name: {server_json['name']}" in readme
