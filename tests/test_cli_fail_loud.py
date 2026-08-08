"""Adversarial CLI tests: every invalid input must fail loud (exit code 1) with
a clean message -- never silently succeed, never leak a raw traceback.

Locks the bugs found in the pre-0.3.0 adversarial E2E pass: unguarded file/JSON
loads (plan/report/compare/refit), junk-but-valid JSON accepted by report, and
the unknown-backend path in bench.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from chimeraforge.cli import app

runner = CliRunner()

# These must never leak UNCAUGHT from a command -- they must be caught and turned
# into a clean typer.Exit(1). (JSONDecodeError subclasses ValueError.)
LEAKED = (FileNotFoundError, ValueError, KeyError)


def _write(tmp_path: Path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestPlanFailLoud:
    def test_negative_latency_slo_rejected(self):
        assert runner.invoke(app, ["plan", "--latency-slo", "-100"]).exit_code == 1

    def test_zero_latency_slo_rejected(self):
        assert runner.invoke(app, ["plan", "--latency-slo", "0"]).exit_code == 1

    def test_missing_models_path_fails_clean(self):
        r = runner.invoke(app, ["plan", "--models-path", "/nonexistent_xyz.json"])
        assert r.exit_code == 1
        assert not isinstance(r.exception, LEAKED)

    def test_malformed_models_path_fails_clean(self, tmp_path: Path):
        bad = _write(tmp_path, "bad.json", "{not json,,,")
        r = runner.invoke(app, ["plan", "--models-path", bad])
        assert r.exit_code == 1
        assert not isinstance(r.exception, LEAKED)

    def test_invalid_kv_quant_rejected(self):
        r = runner.invoke(app, ["plan", "--model-size", "3b", "--kv-quant", "q3"])
        assert r.exit_code == 1
        assert "kv-quant" in r.output

    def test_negative_electricity_rate_rejected(self):
        assert (
            runner.invoke(app, ["plan", "--model-size", "3b", "--electricity-rate", "-1"]).exit_code
            == 1
        )


class TestReportFailLoud:
    def test_malformed_json_fails_clean(self, tmp_path: Path):
        bad = _write(tmp_path, "bad.json", "{not json,,,")
        r = runner.invoke(app, ["report", "--results-files", bad])
        assert r.exit_code == 1
        assert not isinstance(r.exception, LEAKED)

    def test_empty_object_rejected(self, tmp_path: Path):
        # {} is valid JSON but not a bench result -- must not silently produce a report.
        empty = _write(tmp_path, "empty.json", "{}")
        assert runner.invoke(app, ["report", "--results-files", empty]).exit_code == 1


class TestCompareFailLoud:
    def test_malformed_json_fails_clean(self, tmp_path: Path):
        bad = _write(tmp_path, "bad.json", "{not json,,,")
        r = runner.invoke(app, ["compare", "--baseline", bad, "--candidate", bad])
        assert r.exit_code == 1
        assert not isinstance(r.exception, LEAKED)


class TestRefitFailLoud:
    def test_malformed_json_fails_clean(self, tmp_path: Path):
        bad = _write(tmp_path, "bad.json", "{not json,,,")
        r = runner.invoke(app, ["refit", "--bench-files", bad])
        assert r.exit_code == 1
        assert not isinstance(r.exception, LEAKED)


class TestBenchFailLoud:
    def test_unknown_backend_fails_clean(self):
        r = runner.invoke(app, ["bench", "--model", "x", "--backend", "nope"])
        assert r.exit_code == 1
        assert not isinstance(r.exception, LEAKED)


class TestRequireExtra:
    """A missing optional extra must fail loud (exit 1) with a clean hint --
    not a raw ModuleNotFoundError from a backend's module-level `import httpx`."""

    def test_missing_dep_exits_clean(self):
        from chimeraforge.commands._deps import require_extra

        with pytest.raises(typer.Exit) as ei:
            require_extra("bench", "a_module_that_does_not_exist_xyz")
        assert ei.value.exit_code == 1

    def test_present_dep_passes(self):
        from chimeraforge.commands._deps import require_extra

        require_extra("bench", "typer")  # always installed -> no raise

    def test_hint_shows_bracketed_extra(self, monkeypatch):
        # The install hint must contain the literal 'chimeraforge[bench]' --
        # Rich must not swallow the [bench] as a style tag.
        from chimeraforge.commands import _deps

        buf = io.StringIO()
        monkeypatch.setattr(_deps, "_console", Console(file=buf, width=200))
        real = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util, "find_spec", lambda m: None if m == "httpx" else real(m)
        )
        with pytest.raises(typer.Exit):
            _deps.require_extra("bench", "httpx")
        assert "chimeraforge[bench]" in buf.getvalue()
