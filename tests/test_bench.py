"""ChimeraForge Benchmarking Engine -- unit tests.

Tests the metrics dataclasses, statistical helpers, workload profiles,
prompts, backend registry, Ollama adapter (mocked HTTP), runner
orchestration, result serialization, and CLI integration.

Run:
    pytest tests/test_bench.py -v
"""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chimeraforge.bench.backends import BACKEND_REGISTRY, get_backend
from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.backends.ollama import OllamaBackend
from chimeraforge.bench.metrics import (
    AggregateMetrics,
    BenchmarkResult,
    EnvironmentInfo,
    RunMetrics,
    StatSummary,
    aggregate_runs,
    collect_environment,
    now_iso,
    result_to_dict,
    result_to_json,
    summarize,
)
from chimeraforge.bench.profiles import PROFILES, WorkloadProfile, get_profile
from chimeraforge.bench.prompts import (
    DEFAULT_PROMPT,
    PROMPT_LONG,
    PROMPT_MEDIUM,
    PROMPT_SHORT,
)
from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends.vllm import VLLMBackend
from chimeraforge.bench.runner import run_benchmark, run_quant_sweep, run_context_sweep, save_results


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
            os="TestOS", platform="TestPlatform", python_version="3.10.0",
            chimeraforge_version="0.2.0", gpu_name=None, gpu_driver=None,
            cuda_version=None, backend_name="ollama", backend_version="0.6.1",
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
            "model", "backend", "quant", "workload", "runs",
            "context_length", "individual_runs", "aggregate",
            "environment", "timestamp", "warnings",
        }
        assert expected_keys == set(d.keys())


# -- Backend registry --------------------------------------------------------


class TestBackendRegistry:
    def test_registry_has_all_backends(self):
        assert "ollama" in BACKEND_REGISTRY
        assert "vllm" in BACKEND_REGISTRY
        assert "tgi" in BACKEND_REGISTRY

    def test_get_backend_ollama(self):
        b = get_backend("ollama")
        assert isinstance(b, OllamaBackend)
        assert b.name == "ollama"

    def test_get_backend_with_url(self):
        b = get_backend("ollama", base_url="http://localhost:9999")
        assert b.base_url == "http://localhost:9999"

    def test_get_backend_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent")


# -- Ollama backend (mocked HTTP) -------------------------------------------


class TestOllamaBackend:
    @pytest.fixture
    def backend(self) -> OllamaBackend:
        return OllamaBackend(base_url="http://localhost:11434")

    def test_name(self, backend):
        assert backend.name == "ollama"

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.health_check()
            assert ok is True

    @pytest.mark.asyncio
    async def test_health_check_connection_refused(self, backend):
        import httpx

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.health_check()
            assert ok is False
            assert "not running" in msg

    @pytest.mark.asyncio
    async def test_check_model_success(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.check_model("llama3.2-3b")
            assert ok is True

    @pytest.mark.asyncio
    async def test_check_model_not_found(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.check_model("nonexistent")
            assert ok is False
            assert "ollama pull" in msg

    @pytest.mark.asyncio
    async def test_generate_extracts_metrics(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Neural networks are...",
            "eval_count": 50,
            "eval_duration": 2_000_000_000,  # 2s in ns
            "prompt_eval_duration": 100_000_000,  # 100ms in ns
            "total_duration": 2_500_000_000,  # 2.5s in ns
        }
        mock_response.raise_for_status = MagicMock()

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            metrics = await backend.generate("test-model", "Hello")

        assert metrics.tokens_generated == 50
        assert metrics.throughput_tps == pytest.approx(25.0, rel=0.01)
        assert metrics.ttft_ms == pytest.approx(100.0, rel=0.01)
        assert metrics.total_duration_ms == pytest.approx(2500.0, rel=0.01)
        assert metrics.eval_duration_ms == pytest.approx(2000.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_version_success(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "0.6.2"}

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await backend.get_version()
            assert version == "0.6.2"

    @pytest.mark.asyncio
    async def test_get_version_failure(self, backend):
        import httpx

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await backend.get_version()
            assert version is None


# -- Runner (mocked backend) ------------------------------------------------


class TestRunner:
    def _mock_backend(self) -> AsyncMock:
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(return_value=RunMetrics(
            tokens_generated=50,
            throughput_tps=25.0,
            ttft_ms=100.0,
            total_duration_ms=2000.0,
            prompt_eval_duration_ms=100.0,
            eval_duration_ms=1900.0,
        ))
        return backend

    @pytest.mark.asyncio
    async def test_run_benchmark_single(self):
        mock_be = self._mock_backend()

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                workload="single",
                runs=3,
            )

        assert result.runs == 3
        assert len(result.individual_runs) == 3
        assert result.aggregate.count == 3
        assert mock_be.generate.call_count == 3

    @pytest.mark.asyncio
    async def test_run_benchmark_batch(self):
        mock_be = self._mock_backend()

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                workload="batch",
                runs=8,
            )

        assert result.runs == 8
        assert len(result.individual_runs) == 8
        assert result.workload == "batch"

    @pytest.mark.asyncio
    async def test_run_benchmark_health_check_failure(self):
        mock_be = self._mock_backend()
        mock_be.health_check = AsyncMock(return_value=(False, "Backend down"))

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            with pytest.raises(RuntimeError, match="Backend down"):
                await run_benchmark(
                    model="test-model",
                    backend_name="mock",
                    runs=1,
                )

    @pytest.mark.asyncio
    async def test_run_benchmark_model_check_failure(self):
        mock_be = self._mock_backend()
        mock_be.check_model = AsyncMock(return_value=(False, "Model not found"))

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            with pytest.raises(RuntimeError, match="Model not found"):
                await run_benchmark(
                    model="bad-model",
                    backend_name="mock",
                    runs=1,
                )

    @pytest.mark.asyncio
    async def test_run_benchmark_aggregation_correct(self):
        call_count = 0

        async def varied_generate(model, prompt, options=None):
            nonlocal call_count
            call_count += 1
            return RunMetrics(
                tokens_generated=50,
                throughput_tps=20.0 + call_count,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )

        mock_be = self._mock_backend()
        mock_be.generate = varied_generate

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                workload="single",
                runs=3,
            )

        assert result.aggregate.throughput_tps.min == 21.0
        assert result.aggregate.throughput_tps.max == 23.0

    @pytest.mark.asyncio
    async def test_run_benchmark_with_progress_callback(self):
        mock_be = self._mock_backend()
        progress_calls = []

        def on_progress(completed, total):
            progress_calls.append((completed, total))

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            await run_benchmark(
                model="test-model",
                backend_name="mock",
                runs=3,
                on_progress=on_progress,
            )

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)

    @pytest.mark.asyncio
    async def test_run_benchmark_result_fields(self):
        mock_be = self._mock_backend()

        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                quant="Q4_K_M",
                workload="single",
                runs=2,
                context_length=4096,
            )

        assert result.model == "test-model"
        assert result.backend == "mock"
        assert result.quant == "Q4_K_M"
        assert result.context_length == 4096
        assert result.environment.backend_name == "mock"
        assert result.timestamp != ""


# -- save_results ------------------------------------------------------------


class TestSaveResults:
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
            os="TestOS", platform="TestPlatform", python_version="3.10.0",
            chimeraforge_version="0.2.0", gpu_name=None, gpu_driver=None,
            cuda_version=None, backend_name="ollama", backend_version="0.6.1",
        )
        return BenchmarkResult(
            model="test-model",
            backend="ollama",
            quant=None,
            workload="single",
            runs=1,
            context_length=2048,
            individual_runs=[run],
            aggregate=agg,
            environment=env,
            timestamp="2026-01-01T00-00-00_00-00",
        )

    def test_save_creates_file(self, tmp_path):
        result = self._make_result()
        path = save_results([result], tmp_path)
        assert path.exists()
        assert path.suffix == ".json"

    def test_save_valid_json(self, tmp_path):
        result = self._make_result()
        path = save_results([result], tmp_path)
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["model"] == "test-model"

    def test_save_creates_directory(self, tmp_path):
        result = self._make_result()
        nested = tmp_path / "nested" / "dir"
        path = save_results([result], nested)
        assert path.exists()


# -- CLI integration ---------------------------------------------------------


class TestCLI:
    def test_bench_help(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner(env={"NO_COLOR": "1"})
        result = runner.invoke(app, ["bench", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--backend" in result.output
        assert "--workload" in result.output
        assert "--runs" in result.output

    def test_bench_requires_model(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench"])
        # Typer shows error for missing required option
        assert result.exit_code != 0

    def test_bench_invalid_context(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--model", "test", "--context", "abc"])
        assert result.exit_code == 1

    def test_bench_negative_runs(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--model", "test", "--runs", "0"])
        assert result.exit_code == 1

    def test_bench_negative_rate(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--model", "test", "--rate", "-1"])
        assert result.exit_code == 1


# -- Runner sweeps (mocked) -------------------------------------------------


class TestRunnerSweeps:
    def _mock_backend(self) -> AsyncMock:
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(return_value=RunMetrics(
            tokens_generated=50,
            throughput_tps=25.0,
            ttft_ms=100.0,
            total_duration_ms=2000.0,
            prompt_eval_duration_ms=100.0,
            eval_duration_ms=1900.0,
        ))
        return backend

    @pytest.mark.asyncio
    async def test_run_quant_sweep(self):
        mock_be = self._mock_backend()
        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            results = await run_quant_sweep(
                model="test-model",
                backend_name="mock",
                quants=["FP16", "Q4_K_M"],
                runs=2,
            )
        assert len(results) == 2
        assert results[0].quant == "FP16"
        assert results[1].quant == "Q4_K_M"

    @pytest.mark.asyncio
    async def test_run_context_sweep(self):
        mock_be = self._mock_backend()
        with patch("chimeraforge.bench.runner.get_backend", return_value=mock_be):
            results = await run_context_sweep(
                model="test-model",
                backend_name="mock",
                context_lengths=[512, 2048],
                runs=2,
            )
        assert len(results) == 2
        assert results[0].context_length == 512
        assert results[1].context_length == 2048


# -- Server mode (mocked) ---------------------------------------------------


class TestServerMode:
    @pytest.mark.asyncio
    async def test_run_server_workload(self):
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(return_value=RunMetrics(
            tokens_generated=50,
            throughput_tps=25.0,
            ttft_ms=100.0,
            total_duration_ms=2000.0,
            prompt_eval_duration_ms=100.0,
            eval_duration_ms=1900.0,
        ))

        with patch("chimeraforge.bench.runner.get_backend", return_value=backend):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                workload="server",
                runs=4,
                rate=10.0,  # High rate so sleeps are short
            )

        assert result.workload == "server"
        assert len(result.individual_runs) == 4


# -- Error resilience --------------------------------------------------------


class TestErrorResilience:
    @pytest.mark.asyncio
    async def test_partial_failures_in_single(self):
        """Single mode should continue after individual request failures."""
        call_count = 0

        async def flaky_generate(model, prompt, options=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Transient error")
            return RunMetrics(
                tokens_generated=50,
                throughput_tps=25.0,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )

        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = flaky_generate

        with patch("chimeraforge.bench.runner.get_backend", return_value=backend):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                workload="single",
                runs=3,
            )

        # 2 of 3 succeeded, 1 failed
        assert len(result.individual_runs) == 2
        assert len(result.warnings) >= 1

    @pytest.mark.asyncio
    async def test_all_failures_raises(self):
        """If all runs fail, should raise RuntimeError."""
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(side_effect=RuntimeError("Always fails"))

        with patch("chimeraforge.bench.runner.get_backend", return_value=backend):
            with pytest.raises(RuntimeError, match="All.*failed"):
                await run_benchmark(
                    model="test-model",
                    backend_name="mock",
                    runs=3,
                )


# -- CV warning ---------------------------------------------------------------


class TestCVWarning:
    @pytest.mark.asyncio
    async def test_high_variance_warning(self):
        """High variance should produce a CV warning."""
        call_count = 0

        async def variable_generate(model, prompt, options=None):
            nonlocal call_count
            call_count += 1
            tps = 10.0 if call_count % 2 == 0 else 50.0
            return RunMetrics(
                tokens_generated=50,
                throughput_tps=tps,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )

        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = variable_generate

        with patch("chimeraforge.bench.runner.get_backend", return_value=backend):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                runs=4,
            )

        cv_warnings = [w for w in result.warnings if "CV" in w]
        assert len(cv_warnings) >= 1

    @pytest.mark.asyncio
    async def test_stable_no_warning(self):
        """Low variance should not produce a CV warning."""
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(return_value=RunMetrics(
            tokens_generated=50,
            throughput_tps=25.0,
            ttft_ms=100.0,
            total_duration_ms=2000.0,
            prompt_eval_duration_ms=100.0,
            eval_duration_ms=1900.0,
        ))

        with patch("chimeraforge.bench.runner.get_backend", return_value=backend):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                runs=5,
            )

        cv_warnings = [w for w in result.warnings if "CV" in w]
        assert len(cv_warnings) == 0


# -- VLLMBackend basic -------------------------------------------------------


class TestVLLMBackend:
    def test_name(self):
        b = VLLMBackend()
        assert b.name == "vllm"

    def test_default_url(self):
        b = VLLMBackend()
        assert b.base_url == "http://localhost:8000"

    def test_custom_url(self):
        b = VLLMBackend(base_url="http://gpu-server:9000/")
        assert b.base_url == "http://gpu-server:9000"


# -- TGIBackend basic --------------------------------------------------------


class TestTGIBackend:
    def test_name(self):
        b = TGIBackend()
        assert b.name == "tgi"

    def test_default_url(self):
        b = TGIBackend()
        assert b.base_url == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_check_model_exact_match(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model_id": "meta-llama/Llama-3.2-3B"}

        b = TGIBackend()
        with patch("chimeraforge.bench.backends.tgi.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            # Bypass client caching for this test
            b._client = mock_client

            ok, _ = await b.check_model("meta-llama/Llama-3.2-3B")
            assert ok is True

    @pytest.mark.asyncio
    async def test_check_model_rejects_substring(self):
        """Single char should not match via loose substring."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model_id": "meta-llama/Llama-3.2-3B"}

        b = TGIBackend()
        with patch("chimeraforge.bench.backends.tgi.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            b._client = mock_client

            ok, _ = await b.check_model("a")
            assert ok is False


# -- Ollama eval_duration=0 edge case ----------------------------------------


class TestOllamaEdgeCases:
    @pytest.mark.asyncio
    async def test_missing_eval_duration_returns_zero_throughput(self):
        """eval_duration=0 should produce 0 throughput, not billions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "test",
            "eval_count": 50,
            # eval_duration missing -> defaults to 0
            "prompt_eval_duration": 100_000_000,
            "total_duration": 2_000_000_000,
        }
        mock_response.raise_for_status = MagicMock()

        b = OllamaBackend()
        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            b._client = mock_client

            metrics = await b.generate("test", "hello")

        assert metrics.throughput_tps == 0.0
        assert metrics.tokens_generated == 50
