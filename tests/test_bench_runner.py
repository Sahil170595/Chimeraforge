"""Tests for bench runner, save_results, sweeps, server mode, error resilience, and CV warnings."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import (
    BenchmarkResult,
    EnvironmentInfo,
    RunMetrics,
    aggregate_runs,
)
from chimeraforge.bench.runner import (
    run_benchmark,
    run_context_sweep,
    run_quant_sweep,
    save_results,
)


# -- Runner (mocked backend) ------------------------------------------------


class TestRunner:
    def _mock_backend(self) -> AsyncMock:
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(
            return_value=RunMetrics(
                tokens_generated=50,
                throughput_tps=25.0,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )
        )
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


# -- Runner sweeps (mocked) -------------------------------------------------


class TestRunnerSweeps:
    def _mock_backend(self) -> AsyncMock:
        backend = AsyncMock(spec=Backend)
        backend.name = "mock"
        backend.health_check = AsyncMock(return_value=(True, "OK"))
        backend.check_model = AsyncMock(return_value=(True, ""))
        backend.get_version = AsyncMock(return_value="1.0.0")
        backend.generate = AsyncMock(
            return_value=RunMetrics(
                tokens_generated=50,
                throughput_tps=25.0,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )
        )
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
        backend.generate = AsyncMock(
            return_value=RunMetrics(
                tokens_generated=50,
                throughput_tps=25.0,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )
        )

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
        backend.generate = AsyncMock(
            return_value=RunMetrics(
                tokens_generated=50,
                throughput_tps=25.0,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                prompt_eval_duration_ms=100.0,
                eval_duration_ms=1900.0,
            )
        )

        with patch("chimeraforge.bench.runner.get_backend", return_value=backend):
            result = await run_benchmark(
                model="test-model",
                backend_name="mock",
                runs=5,
            )

        cv_warnings = [w for w in result.warnings if "CV" in w]
        assert len(cv_warnings) == 0
