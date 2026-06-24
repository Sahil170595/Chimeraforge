"""Tests for measure-on-demand: folding real benchmarks into the planner corpus.

The live benchmarking shell (``measure_model``) needs a backend, so it's verified
manually; here we test the offline-deterministic pieces: the corpus fold, the
effective-models precedence, and that a measured corpus actually flips planner
provenance to ``measured``.
"""

from __future__ import annotations

import json

from chimeraforge.bench.metrics import (
    BenchmarkResult,
    RunMetrics,
    aggregate_runs,
    collect_environment,
)
from chimeraforge.measure import fold_into_corpus
from chimeraforge.planner.engine import enumerate_candidates
from chimeraforge.planner.models import load_effective_models, load_models
from chimeraforge.planner.resolver import ModelSpec, measured_corpus_path


def _bench_result(model, backend, quant, tps, dur_ms=500.0):
    runs = [
        RunMetrics(
            tokens_generated=100,
            throughput_tps=tps,
            ttft_ms=10.0,
            total_duration_ms=dur_ms,
            prompt_eval_duration_ms=5.0,
            eval_duration_ms=400.0,
        )
        for _ in range(5)
    ]
    return BenchmarkResult(
        model=model,
        backend=backend,
        quant=quant,
        workload="single",
        runs=5,
        context_length=2048,
        individual_runs=runs,
        aggregate=aggregate_runs(runs),
        environment=collect_environment(backend),
        timestamp="2026-01-01T00:00:00+00:00",
    )


class TestFoldIntoCorpus:
    def test_writes_throughput_and_scaling(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        corpus = measured_corpus_path()
        result = _bench_result("qwen3:14b", "ollama", "Q4_K_M", tps=41.8)

        fold_into_corpus(result, "qwen3:14b|ollama", 0.71, corpus)

        data = json.loads(corpus.read_text(encoding="utf-8"))
        assert data["throughput"]["lookup"]["qwen3:14b|ollama|Q4_K_M"] == 41.8
        assert data["scaling"]["serial_fractions"]["qwen3:14b|ollama"] == 0.71

    def test_accumulates_across_calls(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        corpus = measured_corpus_path()
        fold_into_corpus(_bench_result("a:1b", "ollama", "Q8_0", 100.0), None, None, corpus)
        fold_into_corpus(_bench_result("b:3b", "ollama", "Q8_0", 50.0), None, None, corpus)
        lookup = json.loads(corpus.read_text(encoding="utf-8"))["throughput"]["lookup"]
        assert "a:1b|ollama|Q8_0" in lookup and "b:3b|ollama|Q8_0" in lookup


class TestLoadEffectiveModels:
    def test_prefers_measured_corpus(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        corpus = measured_corpus_path()
        corpus.parent.mkdir(parents=True, exist_ok=True)
        corpus.write_text(
            json.dumps({"throughput": {"lookup": {"foo|ollama|FP16": 42.0}}}), encoding="utf-8"
        )
        models = load_effective_models()
        assert models.throughput.lookup.get("foo|ollama|FP16") == 42.0

    def test_falls_back_to_bundled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))  # empty -> no corpus
        models = load_effective_models()
        # Bundled data has the registry models.
        assert any("llama3.2-3b" in k for k in models.throughput.lookup)

    def test_explicit_path_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        explicit = tmp_path / "explicit.json"
        explicit.write_text(json.dumps({"throughput": {"lookup": {"x|y|FP16": 7.0}}}))
        models = load_effective_models(str(explicit))
        assert models.throughput.lookup.get("x|y|FP16") == 7.0


class TestMeasuredCorpusFlipsProvenance:
    def test_offregistry_throughput_becomes_measured(self, tmp_path, monkeypatch):
        # Fold a measurement, then plan that off-registry model from the corpus
        # and assert provenance flips from estimated (roofline) to measured.
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        corpus = measured_corpus_path()
        fold_into_corpus(
            _bench_result("qwen3:14b", "ollama", "Q4_K_M", 41.8), "qwen3:14b|ollama", 0.71, corpus
        )
        models = load_models(corpus)
        spec = ModelSpec(
            name="qwen3:14b",
            params_b=14.8,
            n_layers=40,
            n_kv_heads=8,
            d_head=128,
            native_quant="Q4_K_M",
            source="ollama",
        )
        cands = enumerate_candidates(
            models=models,
            target_models=["qwen3:14b"],
            hardware="RTX 4080 12GB",
            request_rate=0.1,
            latency_slo=60000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
            specs={"qwen3:14b": spec},
        )
        assert cands
        ollama_cands = [c for c in cands if c.backend == "ollama"]
        assert ollama_cands
        assert ollama_cands[0].provenance["throughput"] == "measured"
        assert ollama_cands[0].throughput_tps == 41.8  # reference GPU, unscaled
