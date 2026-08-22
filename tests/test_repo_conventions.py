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


class TestReadmeTracksTheCode:
    """The README is the shopfront, and it rots silently.

    PyPI, the Glama listing and the MCP registry all render it and each
    re-indexes on its own schedule, so a stale line keeps being served long
    after the code moved. The Glama listing was found advertising three MCP
    tools, 12 commands and 549 tests well after all three had changed.

    These are the claims that actually rotted, so these are the ones pinned.
    """

    @pytest.fixture(scope="class")
    def readme(self) -> str:
        return (ROOT / "README.md").read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def commands(self) -> list[str]:
        from chimeraforge.cli import app

        return sorted(c.name or c.callback.__name__ for c in app.registered_commands)

    def test_every_command_has_a_readme_section(self, readme, commands):
        missing = [c for c in commands if f"### `{c}`" not in readme]
        assert not missing, (
            f"commands shipped with no README section: {missing}. "
            "Document it in the PR that adds it, not in a later cleanup."
        )

    def test_no_readme_section_for_a_command_that_no_longer_exists(self, readme, commands):
        documented = set(re.findall(r"^### `([a-z-]+)`", readme, re.MULTILINE))
        assert documented <= set(commands), (
            f"README documents commands the CLI does not register: "
            f"{sorted(documented - set(commands))}"
        )

    def test_headline_command_count_is_right(self, readme, commands):
        match = re.search(r"\*\*(\d+) commands, one tool", readme)
        assert match, "the '**N commands, one tool**' headline is gone from the README"
        assert int(match.group(1)) == len(commands)

    def test_headline_lists_every_command(self, readme, commands):
        line = next(ln for ln in readme.splitlines() if "commands, one tool" in ln)
        missing = [c for c in commands if f"`{c}`" not in line]
        assert not missing, f"headline command list omits: {missing}"

    def test_advertised_test_count_is_not_stale(self, readme):
        """A lower bound, not an exact match: parametrization only pushes the real
        count higher, so a `def test_` tally can never legitimately exceed the
        advertised number. This is the check that would have caught 549 vs 1233."""
        match = re.search(r"\*\*([\d,]+) automated tests\*\*", readme)
        assert match, "the '**N automated tests**' claim is gone from the README"
        claimed = int(match.group(1).replace(",", ""))
        defined = sum(
            len(re.findall(r"^\s*def test_", p.read_text(encoding="utf-8"), re.MULTILINE))
            for p in (ROOT / "tests").glob("test_*.py")
        )
        assert claimed >= defined, (
            f"README advertises {claimed} tests but {defined} test functions are "
            "defined (and parametrization makes the real number higher still)"
        )

    def test_mcp_tool_count_matches_the_server(self, readme):
        """Counts the actual `server.tool(name="chimeraforge_...")` registrations.

        An earlier version of this test counted `_DESC` constants instead, which
        happened to equal the stale claim and so passed on the very README that
        was wrong. Read the registrations from source rather than a proxy -- and
        from source, not a live import, so it holds without the `mcp` extra.
        """
        source = (ROOT / "src" / "chimeraforge" / "mcp_server.py").read_text(encoding="utf-8")
        registered = len(set(re.findall(r'name="(chimeraforge_\w+)"', source)))
        assert registered, "no MCP tool registrations found -- did the pattern change?"
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
        match = re.search(r"Exposes (\w+) tools", readme)
        assert match, "the 'Exposes N tools' line is gone from the README"
        claimed = words.get(match.group(1))
        assert claimed is not None, f"unrecognised tool count word: {match.group(1)!r}"
        assert claimed == registered, (
            f"README says {match.group(1)} MCP tools; {registered} are registered"
        )


class TestGlamaJson:
    """glama.json is the ownership proof for the Glama registry listing.

    It is tiny, which is exactly why it rots unnoticed: a typo'd username or a
    stray comma silently un-claims the listing (Glama re-validates the file on
    every claim), and nothing else in the repo would fail.
    """

    @pytest.fixture(scope="class")
    def glama(self) -> dict:
        return json.loads((ROOT / "glama.json").read_text(encoding="utf-8"))

    def test_exists_at_the_repo_root(self):
        # Glama reads it from the root only; anywhere else is invisible to it.
        assert (ROOT / "glama.json").is_file()

    def test_declares_the_published_schema(self, glama):
        assert glama["$schema"] == "https://glama.ai/mcp/schemas/server.json"

    def test_maintainer_matches_the_repo_owner(self, glama):
        # The claim flow checks the authenticated GitHub user against this list,
        # so a mismatch here fails the claim with no other symptom.
        assert glama["maintainers"] == ["Sahil170595"]

    def test_maintainers_are_unique_non_empty_strings(self, glama):
        names = glama["maintainers"]
        assert names and all(isinstance(n, str) and n.strip() for n in names)
        assert len(set(names)) == len(names)

    def test_no_unknown_top_level_keys(self, glama):
        # The schema defines only these two; Docker build spec, related servers
        # and metadata overrides are web-UI settings after claiming, not fields
        # here -- putting them in the file does nothing and reads as if it did.
        assert set(glama) == {"$schema", "maintainers"}


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
