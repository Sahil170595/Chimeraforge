"""Tests for the SGLang bench adapter.

The planner has offered SGLang since 0.23.0 and told the user to "run `measure`
to replace the estimate with a measurement" -- but the bench registry held only
ollama/vllm/tgi, so that instruction could not be followed. These tests pin the
adapter against a mocked SGLang server (real SSE parsing through httpx's mock
transport, not a stubbed client) and pin the end-to-end promise: a measured
SGLang row flips planner provenance to `measured` and silences the
"no measured rows" warning.

The metric definition is the load-bearing detail. The planner's throughput is a
single-stream DECODE rate; the vLLM adapter reports completion tokens over wall
clock, which includes prefill. SGLang streams, so it can report the decode rate
the planner actually predicts, and a test holds it to that.
"""

from __future__ import annotations

import json

import httpx
import pytest

from chimeraforge.bench.backends import BACKEND_REGISTRY, get_backend
from chimeraforge.bench.backends.sglang import DEFAULT_SGLANG_URL, SGLangBackend
from chimeraforge.planner.provenance import PROV_MEASURED, prov_class


def _sse(chunks: list[dict]) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode("utf-8")


def _text_chunk(text: str) -> dict:
    return {"id": "x", "object": "text_completion", "choices": [{"index": 0, "text": text}]}


def _usage_chunk(prompt: int, completion: int) -> dict:
    return {
        "id": "x",
        "object": "text_completion",
        "choices": [],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


class _Clock:
    """Deterministic perf_counter: each call returns the next scripted instant."""

    def __init__(self, ticks: list[float]) -> None:
        self._ticks = list(ticks)

    def __call__(self) -> float:
        return self._ticks.pop(0)


def _backend(handler, clock=None) -> SGLangBackend:
    return SGLangBackend(
        base_url="http://sglang.test:30000",
        transport=httpx.MockTransport(handler),
        clock=clock,
    )


class TestRegistration:
    def test_sglang_is_benchable(self):
        assert BACKEND_REGISTRY["sglang"] is SGLangBackend

    def test_default_port_is_sglangs(self):
        b = get_backend("sglang")
        assert b.base_url == DEFAULT_SGLANG_URL
        assert DEFAULT_SGLANG_URL.endswith(":30000")

    def test_url_override(self):
        assert get_backend("sglang", base_url="http://h:1/").base_url == "http://h:1"


class TestHealthAndModel:
    @pytest.mark.asyncio
    async def test_healthy(self):
        def handler(req):
            if req.url.path == "/server_info":
                return httpx.Response(200, json={"version": "0.5.20"})
            return httpx.Response(200, text="")

        ok, msg = await _backend(handler).health_check()
        assert ok and "SGLang 0.5.20" in msg

    @pytest.mark.asyncio
    async def test_not_running_is_reported(self):
        def refuse(req):
            raise httpx.ConnectError("refused", request=req)

        ok, msg = await _backend(refuse).health_check()
        assert not ok and "not running" in msg

    @pytest.mark.asyncio
    async def test_unhealthy_status_is_reported(self):
        ok, msg = await _backend(lambda req: httpx.Response(503)).health_check()
        assert not ok and "503" in msg

    @pytest.mark.asyncio
    async def test_model_listed(self):
        body = {"object": "list", "data": [{"id": "Qwen/Qwen2.5-7B-Instruct"}]}
        b = _backend(lambda req: httpx.Response(200, json=body))
        assert (await b.check_model("Qwen/Qwen2.5-7B-Instruct")) == (True, "")

    @pytest.mark.asyncio
    async def test_model_missing_names_what_is_served(self):
        body = {"object": "list", "data": [{"id": "served-model"}]}
        ok, msg = await _backend(lambda req: httpx.Response(200, json=body)).check_model("other")
        assert not ok and "served-model" in msg


class TestGenerate:
    @pytest.mark.asyncio
    async def test_decode_rate_excludes_prefill(self):
        """5 tokens: first at t=0.1 (TTFT 100 ms), last at t=0.5, done at t=0.6.

        Decode rate is (5 - 1) tokens over the 0.4 s between first and last token
        = 10.0 tok/s. The wall-clock rate vLLM's adapter would report is 5/0.6 =
        8.3 -- it folds prefill into a number the planner reads as decode.
        """
        body = _sse([_text_chunk(t) for t in "abcde"] + [_usage_chunk(12, 5)])
        clock = _Clock([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        m = await _backend(lambda req: httpx.Response(200, content=body), clock).generate(
            "m", "hello"
        )
        assert m.tokens_generated == 5
        assert m.ttft_ms == pytest.approx(100.0)
        assert m.throughput_tps == pytest.approx(10.0)
        assert m.eval_duration_ms == pytest.approx(400.0)
        assert m.total_duration_ms == pytest.approx(600.0)
        assert m.prompt_eval_duration_ms == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_token_count_comes_from_usage_not_chunk_count(self):
        """A chunk can carry several tokens; counting chunks would under-report."""
        body = _sse([_text_chunk("ab"), _text_chunk("cd"), _usage_chunk(3, 9)])
        clock = _Clock([0.0, 0.1, 0.5, 0.6])
        m = await _backend(lambda req: httpx.Response(200, content=body), clock).generate("m", "p")
        assert m.tokens_generated == 9
        assert m.throughput_tps == pytest.approx(8 / 0.4)

    @pytest.mark.asyncio
    async def test_request_asks_for_usage_and_streams(self):
        seen = {}

        def handler(req):
            seen.update(json.loads(req.content))
            seen["path"] = req.url.path
            return httpx.Response(
                200, content=_sse([_text_chunk("a"), _text_chunk("b"), _usage_chunk(1, 2)])
            )

        await _backend(handler, _Clock([0, 1, 2, 3])).generate(
            "m", "p", {"max_tokens": 64, "num_ctx": 4096}
        )
        assert seen["path"] == "/v1/completions"
        assert seen["stream"] is True
        assert seen["stream_options"] == {"include_usage": True}
        assert seen["max_tokens"] == 64
        # Ollama's context option is not an SGLang sampling parameter; sending it
        # would be ignored at best and rejected at worst.
        assert "num_ctx" not in seen

    @pytest.mark.asyncio
    async def test_missing_usage_is_a_failed_run_not_a_guess(self):
        body = _sse([_text_chunk("a"), _text_chunk("b")])
        with pytest.raises(RuntimeError, match="usage"):
            await _backend(
                lambda req: httpx.Response(200, content=body), _Clock([0, 1, 2, 3])
            ).generate("m", "p")

    @pytest.mark.asyncio
    async def test_single_token_has_no_decode_interval(self):
        body = _sse([_text_chunk("a"), _usage_chunk(1, 1)])
        with pytest.raises(RuntimeError, match="decode"):
            await _backend(
                lambda req: httpx.Response(200, content=body), _Clock([0, 1, 2])
            ).generate("m", "p")

    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        with pytest.raises(httpx.HTTPStatusError):
            await _backend(lambda req: httpx.Response(400, json={"error": "bad"})).generate(
                "m", "p"
            )


class TestVersion:
    @pytest.mark.asyncio
    async def test_reads_server_version(self):
        def handler(req):
            if req.url.path == "/server_info":
                return httpx.Response(200, json={"version": "0.5.18", "tp_size": 1})
            return httpx.Response(404)

        assert await _backend(handler).get_version() == "0.5.18"

    @pytest.mark.asyncio
    async def test_unreachable_version_is_none(self):
        assert await _backend(lambda req: httpx.Response(404)).get_version() is None


class TestMeasuredSGLangRowIsUsed:
    """The promise the 0.23.0 changelog made: `measure` replaces the estimate."""

    def test_a_folded_sglang_row_flips_provenance_and_silences_the_warning(
        self, tmp_path, monkeypatch
    ):
        from chimeraforge.bench.metrics import (
            BenchmarkResult,
            RunMetrics,
            aggregate_runs,
            collect_environment,
        )
        from chimeraforge.measure import fold_into_corpus
        from chimeraforge.planner.models import load_models
        from chimeraforge.planner.resolver import measured_corpus_path
        from chimeraforge.planner.service import run_plan

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        runs = [
            RunMetrics(
                tokens_generated=128,
                throughput_tps=140.0,
                ttft_ms=20.0,
                total_duration_ms=700.0,
                prompt_eval_duration_ms=20.0,
                eval_duration_ms=670.0,
            )
            for _ in range(5)
        ]
        result = BenchmarkResult(
            model="llama3.2-1b",
            backend="sglang",
            quant="FP16",
            workload="single",
            runs=5,
            context_length=2048,
            individual_runs=runs,
            aggregate=aggregate_runs(runs),
            environment=collect_environment("sglang"),
            timestamp="2026-09-25T00:00:00+00:00",
        )
        corpus = measured_corpus_path()
        fold_into_corpus(result, None, None, corpus)
        assert load_models(corpus).throughput.has_measured_rows("sglang")

        plan = run_plan(
            models=["llama3.2-1b"],
            hardware="RTX 4080 12GB",
            request_rate=0.1,
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            models_path=str(corpus),
            allow_network=False,
        )
        sg = {c.quant: c for c in plan.candidates if c.backend == "sglang"}
        assert prov_class(sg["FP16"].provenance["throughput"]) == PROV_MEASURED
        assert sg["FP16"].throughput_tps == 140.0  # reference GPU, unscaled
        assert not any("no measured rows" in w for c in sg.values() for w in c.warnings)
        # Only the cell that was measured flips: FP8 on SGLang was not benchmarked
        # and must not inherit the FP16 row's label.
        assert prov_class(sg["FP8"].provenance["throughput"]) != PROV_MEASURED
