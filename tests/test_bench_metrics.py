"""Tests for bench metrics, prompts, profiles, environment, and result serialization."""

from __future__ import annotations

import json

import pytest

from chimeraforge.bench.metrics import (
    BenchmarkResult,
    EnvironmentInfo,
    RunMetrics,
    aggregate_runs,
    collect_environment,
    now_iso,
    result_to_dict,
    result_to_json,
    summarize,
)
from chimeraforge.bench.profiles import PROFILES, get_profile
from chimeraforge.bench.prompts import (
    DEFAULT_PROMPT,
    PROMPT_LONG,
    PROMPT_MEDIUM,
    PROMPT_SHORT,
)


# -- Metrics: StatSummary and aggregation ------------------------------------


class TestStatSummary:
    def test_summarize_basic(self):
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        s = summarize(vals)
        assert s.mean == 30.0
        assert s.min == 10.0
        assert s.max == 50.0
        assert s.stddev > 0

    def test_summarize_single_value(self):
        s = summarize([42.0])
        assert s.mean == 42.0
        assert s.p50 == 42.0
        assert s.p95 == 42.0
        assert s.min == 42.0
        assert s.max == 42.0
        assert s.stddev == 0.0

    def test_summarize_empty(self):
        s = summarize([])
        assert s.mean == 0.0
        assert s.p50 == 0.0
        assert s.stddev == 0.0

    def test_percentiles_ordered(self):
        vals = list(range(1, 101))  # 1..100
        s = summarize([float(v) for v in vals])
        assert s.p50 <= s.p95 <= s.p99
        assert s.min <= s.p50
        assert s.p99 <= s.max

    def test_summarize_two_values(self):
        s = summarize([10.0, 20.0])
        assert s.mean == 15.0
        assert s.min == 10.0
        assert s.max == 20.0
        assert s.stddev > 0


class TestAggregateRuns:
    def _make_run(self, tps: float, ttft: float, total: float, tokens: int) -> RunMetrics:
        return RunMetrics(
            tokens_generated=tokens,
            throughput_tps=tps,
            ttft_ms=ttft,
            total_duration_ms=total,
            prompt_eval_duration_ms=ttft,
            eval_duration_ms=total - ttft,
        )

    def test_aggregate_count(self):
        runs = [self._make_run(10, 50, 200, 20) for _ in range(5)]
        agg = aggregate_runs(runs)
        assert agg.count == 5

    def test_aggregate_total_tokens(self):
        runs = [self._make_run(10, 50, 200, 20) for _ in range(3)]
        agg = aggregate_runs(runs)
        assert agg.tokens_generated == 60

    def test_aggregate_throughput_stats(self):
        runs = [self._make_run(t, 50, 200, 20) for t in [10, 20, 30]]
        agg = aggregate_runs(runs)
        assert agg.throughput_tps.mean == 20.0
        assert agg.throughput_tps.min == 10.0
        assert agg.throughput_tps.max == 30.0

    def test_aggregate_single_run(self):
        runs = [self._make_run(42, 100, 500, 50)]
        agg = aggregate_runs(runs)
        assert agg.count == 1
        assert agg.throughput_tps.mean == 42.0
        assert agg.throughput_tps.stddev == 0.0


# -- Prompts -----------------------------------------------------------------


class TestPrompts:
    def test_prompts_non_empty(self):
        assert len(PROMPT_SHORT) > 0
        assert len(PROMPT_MEDIUM) > 0
        assert len(PROMPT_LONG) > 0

    def test_default_prompt_is_medium(self):
        assert DEFAULT_PROMPT is PROMPT_MEDIUM

    def test_short_shorter_than_long(self):
        assert len(PROMPT_SHORT) < len(PROMPT_LONG)

    def test_medium_between_short_and_long(self):
        assert len(PROMPT_SHORT) < len(PROMPT_MEDIUM) < len(PROMPT_LONG)


# -- Profiles ----------------------------------------------------------------


class TestProfiles:
    def test_profiles_exist(self):
        assert "single" in PROFILES
        assert "batch" in PROFILES
        assert "server" in PROFILES

    def test_single_profile(self):
        p = PROFILES["single"]
        assert p.concurrency == 1
        assert p.arrival_rate is None

    def test_server_profile_has_rate(self):
        p = PROFILES["server"]
        assert p.arrival_rate is not None
        assert p.arrival_rate > 0

    def test_get_profile_basic(self):
        p = get_profile("single")
        assert p.name == "single"
        assert p.total_requests == 5

    def test_get_profile_override_runs(self):
        p = get_profile("single", runs=10)
        assert p.total_requests == 10

    def test_get_profile_override_rate(self):
        p = get_profile("server", rate=5.0)
        assert p.arrival_rate == 5.0

    def test_get_profile_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile("nonexistent")

    def test_get_profile_preserves_concurrency(self):
        p = get_profile("batch", runs=8)
        assert p.concurrency == 4
        assert p.total_requests == 8


# -- Environment -------------------------------------------------------------


class TestEnvironment:
    def test_collect_environment_fields(self):
        env = collect_environment("ollama", "0.6.1")
        assert env.backend_name == "ollama"
        assert env.backend_version == "0.6.1"
        assert env.os != ""
        assert env.python_version != ""
        assert env.chimeraforge_version != ""

    def test_collect_environment_no_version(self):
        env = collect_environment("vllm")
        assert env.backend_version is None

    def test_now_iso_format(self):
        ts = now_iso()
        assert "T" in ts  # ISO 8601 has T separator


# -- Result serialization ----------------------------------------------------


class TestResultSerialization:
    def _make_result(self) -> BenchmarkResult:
        run = RunMetrics(
            tokens_generated=50,
            throughput_tps=25.0,
            ttft_ms=100.0,
            total_duration_ms=2000.0,
            prompt_eval_duration_ms=100.0,
            eval_duration_ms=1900.0,
        )
        agg = aggregate_runs([run])
        env = EnvironmentInfo(
            os="TestOS",
            platform="TestPlatform",
            python_version="3.10.0",
            chimeraforge_version="0.2.0",
            gpu_name=None,
            gpu_driver=None,
            cuda_version=None,
            backend_name="ollama",
            backend_version="0.6.1",
        )
        return BenchmarkResult(
            model="test-model",
            backend="ollama",
            quant="Q4_K_M",
            workload="single",
            runs=1,
            context_length=2048,
            individual_runs=[run],
            aggregate=agg,
            environment=env,
            timestamp="2026-01-01T00:00:00+00:00",
        )

    def test_result_to_dict(self):
        r = self._make_result()
        d = result_to_dict(r)
        assert d["model"] == "test-model"
        assert d["backend"] == "ollama"
        assert d["quant"] == "Q4_K_M"
        assert isinstance(d["individual_runs"], list)
        assert isinstance(d["aggregate"], dict)

    def test_result_to_json_roundtrip(self):
        r = self._make_result()
        j = result_to_json(r)
        parsed = json.loads(j)
        assert parsed["model"] == "test-model"
        assert parsed["aggregate"]["count"] == 1

    def test_result_warnings_default_empty(self):
        r = self._make_result()
        assert r.warnings == []

    def test_result_dict_all_fields(self):
        r = self._make_result()
        d = result_to_dict(r)
        expected_keys = {
            "model",
            "backend",
            "quant",
            "workload",
            "runs",
            "context_length",
            "individual_runs",
            "aggregate",
            "environment",
            "timestamp",
            "warnings",
        }
        assert expected_keys == set(d.keys())
