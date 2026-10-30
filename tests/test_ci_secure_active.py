"""The installed consumer also runs against the actual source CLI transport."""

from __future__ import annotations

from typer.testing import CliRunner

from chimeraforge.cli import app
from test_ci_acceptance import load_script


def test_complete_secure_active_artifact_consumer_source_protocol(tmp_path, monkeypatch):
    parent = load_script("ci_installed_acceptance")
    fixture = load_script("ci_secure_active")
    origins = []
    monkeypatch.setattr(parent, "assert_installed_origin", lambda *args: origins.append(args))

    def source_cli(arguments, cwd, env, expected_code=0, *, forbidden=()):
        result = CliRunner().invoke(app, arguments, env=env)
        assert result.exit_code == expected_code, result.output
        assert all(value not in result.stdout + result.stderr for value in forbidden)
        return result.stdout

    monkeypatch.setattr(parent, "run_cli", source_cli)
    result = fixture.accept(tmp_path, {}, tmp_path / "checkout")
    assert origins
    assert result["positive_invocations"] == 40 and result["negative_invocations"] == 24
    assert len(result["output_aliases"]) == 9
    assert (
        result["source_bytes_unchanged"] and result["owned_fixture_listeners_and_handlers_closed"]
    )


def test_loaded_module_provenance_refuses_shadow_outside_package(tmp_path, monkeypatch):
    import sys
    from types import ModuleType
    import pytest

    parent = load_script("ci_installed_acceptance")
    monkeypatch.setattr(parent, "assert_installed_origin", lambda *args: None)
    shadow = ModuleType("chimeraforge.runtime_shadow")
    shadow.__file__ = str(tmp_path / "unrelated.py")
    monkeypatch.setitem(sys.modules, shadow.__name__, shadow)
    with pytest.raises(AssertionError, match="outside installed package"):
        parent.assert_installed_modules(tmp_path)
