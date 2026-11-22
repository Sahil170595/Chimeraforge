"""Tests for model discovery orchestration (network fetchers excluded).

The discover/resolve/rank pipeline is exercised with manually-built specs so the
ranking logic is validated offline; the HTTP fetchers are thin seams tested
implicitly via the resolver's error contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from chimeraforge.planner.discovery import (
    best_per_model,
    build_catalog,
    load_catalog,
    load_seed_catalog,
    suggest,
)
from chimeraforge.planner.resolver import ModelSpec


def _strip_ansi(text: str) -> str:
    """Drop ANSI escapes so assertions don't break when Rich forces colour.

    Under a forced-colour terminal (e.g. CI) Rich injects escape codes between
    characters -- ``--build`` renders as ``-<esc>-build`` -- so a raw substring
    check fails. Stripping first makes the assertion terminal-independent.
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _offreg(name, params_b, n_kv_heads=8):
    return ModelSpec(
        name=name,
        params_b=params_b,
        n_layers=32,
        n_kv_heads=n_kv_heads,
        d_head=128,
        family="mistral",
        source="hf",
    )


class TestBestPerModel:
    def test_keeps_first_per_model(self):
        from chimeraforge.planner.engine import Candidate

        def cand(model, cost):
            return Candidate(
                model=model,
                quant="Q4_K_M",
                backend="ollama",
                n_agents=1,
                vram_gb=4.0,
                quality=0.6,
                quality_tier="negligible",
                throughput_tps=100.0,
                total_throughput_tps=100.0,
                eta=1.0,
                p95_latency_ms=500.0,
                utilisation=0.3,
                monthly_cost=cost,
                cost_per_1m_tok=0.1,
                safety_refusal=None,
                rtsi_risk="UNKNOWN",
                warnings=[],
            )

        # Already cost-sorted (as enumerate_candidates returns).
        cands = [cand("a", 10), cand("a", 20), cand("b", 15), cand("b", 30)]
        best = best_per_model(cands)
        assert [c.model for c in best] == ["a", "b"]
        assert [c.monthly_cost for c in best] == [10, 15]

    def test_empty(self):
        assert best_per_model([]) == []


class TestSuggest:
    def test_ranks_resolved_specs(self, bundled_models):
        specs = {
            "small/m": _offreg("small/m", 1.5),
            "big/m": _offreg("big/m", 7.0),
        }
        ranked = suggest(
            bundled_models,
            specs,
            hardware="RTX 4090 24GB",
            request_rate=1.0,
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
        )
        # One best config per model, globally cost-sorted.
        models = [c.model for c in ranked]
        assert set(models) <= {"small/m", "big/m"}
        assert len(models) == len(set(models))  # no model appears twice
        costs = [c.monthly_cost for c in ranked]
        assert costs == sorted(costs)

    def test_vram_gate_drops_oversized(self, bundled_models):
        # A 7B FP16 won't fit an 8GB card; suggest must drop it (or only offer
        # quants that fit), never crash.
        specs = {"big/m": _offreg("big/m", 7.0)}
        ranked = suggest(
            bundled_models,
            specs,
            hardware="RTX 4060 8GB",
            request_rate=1.0,
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
        )
        for c in ranked:
            assert c.vram_gb <= 8.0


class TestCatalog:
    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {"models": None},
            {"error": "fixture failure"},
            {"models": [0]},
            {"models": [{"name": 7}]},
        ],
    )
    def test_unusable_ollama_tags_cannot_replace_the_catalog(self, tmp_path, monkeypatch, payload):
        import httpx
        from typer.testing import CliRunner

        from chimeraforge.cli import app
        from chimeraforge.planner import discovery

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        discovery._write_catalog({"prior/model": _offreg("prior/model", 1.5)})
        index = discovery._catalog_path()
        before = index.read_bytes()
        monkeypatch.setattr(discovery, "load_seed_catalog", lambda: ["seed/model"])
        monkeypatch.setattr(discovery, "_httpx", lambda: httpx)

        def tags(url, **kwargs):
            assert url.endswith("/api/tags")
            return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", tags)

        def resolve(*args, **kwargs):
            pytest.fail("catalog resolved seed after requested discovery failed")

        monkeypatch.setattr(discovery, "resolve_many", resolve)
        result = CliRunner().invoke(app, ["catalog", "--build", "--with-ollama", "--json"])
        assert result.exit_code == 1
        document = json.loads(result.stdout)
        assert (
            set(document) == {"models", "errors"}
            and document["models"] == {}
            and document["errors"]
        )
        assert index.read_bytes() == before

    def test_empty_ollama_inventory_is_valid(self, monkeypatch):
        import httpx

        from chimeraforge.planner import discovery

        monkeypatch.setattr(discovery, "_httpx", lambda: httpx)
        monkeypatch.setattr(
            httpx,
            "get",
            lambda url, **kwargs: httpx.Response(
                200, json={"models": []}, request=httpx.Request("GET", url)
            ),
        )
        assert discovery.fetch_ollama_tags() == []

    def test_seed_is_nonempty_list(self):
        seed = load_seed_catalog()
        assert isinstance(seed, list) and len(seed) >= 5
        assert all(isinstance(s, str) for s in seed)

    def test_catalog_roundtrip_offline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        from chimeraforge.planner import discovery

        specs = {
            "a/b": _offreg("a/b", 1.5),
            "c/d": _offreg("c/d", 7.0),
        }
        discovery._write_catalog(specs)
        loaded = load_catalog()
        assert set(loaded.keys()) == {"a/b", "c/d"}
        assert loaded["a/b"] == specs["a/b"]

    def test_load_catalog_empty_when_unbuilt(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        assert load_catalog() == {}

    def test_build_catalog_no_sources_is_empty(self, tmp_path, monkeypatch):
        # include_seed=False + no ollama -> no ids -> no network, empty result.
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        specs, errors = build_catalog(include_seed=False, include_ollama=False)
        assert specs == {}
        assert errors == []

    def test_total_failure_keeps_the_last_catalog(self, tmp_path, monkeypatch):
        from chimeraforge.planner import discovery

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        prior = {"prior/model": _offreg("prior/model", 1.5)}
        discovery._write_catalog(prior)
        path = discovery._catalog_path()
        before = path.read_bytes()
        monkeypatch.setattr(discovery, "load_seed_catalog", lambda: ["new/model"])
        errors = [("new/model", "fixture unavailable")]
        monkeypatch.setattr(discovery, "resolve_many", lambda ids, **kwargs: ({}, errors))
        assert build_catalog() == ({}, errors)
        assert path.read_bytes() == before and load_catalog() == prior


class TestCommandsOffline:
    """CLI surface checks that need no network."""

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {"models": None},
            {"error": "fixture failure"},
            {"models": [0]},
            {"models": [{"name": 7}]},
        ],
    )
    def test_unusable_ollama_tags_cannot_replace_the_catalog(self, tmp_path, monkeypatch, payload):
        import httpx
        from typer.testing import CliRunner

        from chimeraforge.cli import app
        from chimeraforge.planner import discovery

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        discovery._write_catalog({"prior/model": _offreg("prior/model", 1.5)})
        index = discovery._catalog_path()
        before = index.read_bytes()
        monkeypatch.setattr(discovery, "load_seed_catalog", lambda: ["seed/model"])
        monkeypatch.setattr(discovery, "_httpx", lambda: httpx)

        def tags(url, **kwargs):
            assert url.endswith("/api/tags")
            return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", tags)

        def resolve(*args, **kwargs):
            pytest.fail("catalog resolved seed after requested discovery failed")

        monkeypatch.setattr(discovery, "resolve_many", resolve)
        result = CliRunner().invoke(app, ["catalog", "--build", "--with-ollama", "--json"])
        assert result.exit_code == 1
        assert json.loads(result.stdout)["status"] == "failed"
        assert index.read_bytes() == before

    def test_empty_ollama_inventory_is_valid(self, monkeypatch):
        import httpx

        from chimeraforge.planner import discovery

        monkeypatch.setattr(discovery, "_httpx", lambda: httpx)
        monkeypatch.setattr(
            httpx,
            "get",
            lambda url, **kwargs: httpx.Response(
                200, json={"models": []}, request=httpx.Request("GET", url)
            ),
        )
        assert discovery.fetch_ollama_tags() == []

    @pytest.mark.parametrize("outcome", ["complete", "partial", "outage", "write_failure"])
    def test_catalog_refresh_reports_publication_and_has_one_json_document(
        self, tmp_path, monkeypatch, outcome
    ):
        from typer.testing import CliRunner

        from chimeraforge.cli import app
        from chimeraforge.planner import discovery

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        prior = {"prior/model": _offreg("prior/model", 1.5)}
        discovery._write_catalog(prior)
        path = discovery._catalog_path()
        before = path.read_bytes()
        requested = ["new/model", "other/model"]
        known = {name: _offreg(name, 1.5) for name in requested}
        if outcome == "partial":
            known.pop("other/model")
        elif outcome == "outage":
            known.clear()
        errors = [(name, "fixture unavailable") for name in requested if name not in known]

        def resolve(ids, **kwargs):
            assert ids == requested
            return known, errors

        monkeypatch.setattr(discovery, "load_seed_catalog", lambda: requested)
        monkeypatch.setattr(discovery, "resolve_many", resolve)
        if outcome == "write_failure":
            replace = Path.replace

            def refuse(source, target):
                if Path(target) == path:
                    raise PermissionError("fixture publication failure")
                return replace(source, target)

            monkeypatch.setattr(Path, "replace", refuse)

        result = CliRunner().invoke(app, ["catalog", "--build", "--json"])
        failed = outcome in {"outage", "write_failure"}
        assert result.exit_code == (1 if failed else 0), result.output
        report = json.loads(result.stdout)
        assert report["status"] == ("failed" if failed else outcome)
        if failed:
            assert report["models"] == {} and report["errors"]
            assert path.read_bytes() == before and load_catalog() == prior
        else:
            assert set(report["models"]) == set(known) and load_catalog() == known
            assert [row["id"] for row in report["errors"]] == [model for model, _ in errors]
        assert not list(tmp_path.glob("*.tmp"))

    def test_catalog_help(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(app, ["catalog", "--help"])
        assert result.exit_code == 0
        assert "--build" in _strip_ansi(result.output)

    def test_catalog_list_empty(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        result = CliRunner().invoke(app, ["catalog"])
        assert result.exit_code == 0
        assert "empty" in _strip_ansi(result.output).lower()

    @pytest.mark.parametrize("failure", ["unresolved", "publish"])
    def test_catalog_failed_build_preserves_existing_index(self, tmp_path, monkeypatch, failure):
        from typer.testing import CliRunner

        from chimeraforge.cli import app
        from chimeraforge.planner import discovery

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        previous = {"cached/model": _offreg("cached/model", 7.0)}
        discovery._write_catalog(previous)
        path = discovery._catalog_path()
        original = path.read_bytes()

        if failure == "unresolved":

            def resolve(*args, **kwargs):
                return {}, [("seed/model", "metadata unavailable")]
        else:

            def resolve(*args, **kwargs):
                return {"new/model": _offreg("new/model", 9.0)}, []

            def refuse_replacement(self, target):
                assert target == path.resolve()
                raise OSError("injected atomic replacement failure")

            monkeypatch.setattr(Path, "replace", refuse_replacement)
        monkeypatch.setattr(discovery, "resolve_many", resolve)

        result = CliRunner().invoke(app, ["catalog", "--build", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert set(payload) == {"models", "errors"}
        assert payload["models"] == {} and payload["errors"]
        assert path.read_bytes() == original
        assert discovery.load_catalog() == previous
        assert not list(path.parent.glob("*.tmp"))

    def test_suggest_bad_source(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(app, ["suggest", "--source", "bogus"])
        assert result.exit_code == 1

    def test_suggest_catalog_empty(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        result = CliRunner().invoke(app, ["suggest", "--source", "catalog"])
        assert result.exit_code == 1
        assert "catalog" in _strip_ansi(result.output).lower()
