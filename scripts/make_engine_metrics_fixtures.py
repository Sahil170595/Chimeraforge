"""Regenerate the two-scrape /metrics fixtures with the real Prometheus client.

The first vLLM fixture was typed by hand and wrote the prefix-cache counters
without the ``_total`` suffix prometheus_client appends to every Counter, so the
reader matched the fixture and missed every real endpoint. These are produced by
prometheus_client itself, using the metric names, types and label names declared
in each engine's source at a pinned tag:

- vLLM v0.30.0: vllm/v1/metrics/loggers.py, vllm/v1/metrics/perf.py
- SGLang v0.5.20: python/sglang/srt/observability/metrics_collector.py

Each engine gets a scrape at t0 and one 60 s later (t1), with traffic chosen so the
window's answers are exact (see WINDOW below and tests/test_workload_engine_metrics.py).

    pip install prometheus_client   # dev-only; not a runtime dependency
    python scripts/make_engine_metrics_fixtures.py
"""

from __future__ import annotations

import os
import pathlib

# Deterministic output: no *_created timestamp series.
os.environ["PROMETHEUS_DISABLE_CREATED_SERIES"] = "True"

from prometheus_client import (  # noqa: E402
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

HERE = pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures"
WINDOW_S = 60.0
H100_FP16_TFLOPS = 989.0  # hardware.json, NVIDIA H100 page (dense FP16)
H100_BW_GBPS = 3352.0


def _flops(mfu: float) -> float:
    return mfu * H100_FP16_TFLOPS * 1e12 * WINDOW_S


def _bytes(fraction: float) -> float:
    return fraction * H100_BW_GBPS * 1e9 * WINDOW_S


def vllm() -> None:
    reg = CollectorRegistry()
    m = "meta-llama/Llama-3.1-8B-Instruct"
    success = Counter(
        "vllm:request_success", "ok", ["model_name", "engine", "finished_reason"], registry=reg
    )
    prompt = Histogram(
        "vllm:request_prompt_tokens",
        "p",
        ["model_name", "engine"],
        buckets=[128, 256, 512, 1024, 2048],
        registry=reg,
    )
    gen = Histogram(
        "vllm:request_generation_tokens",
        "g",
        ["model_name", "engine"],
        buckets=[64, 128, 256, 512],
        registry=reg,
    )
    e2e = Histogram(
        "vllm:e2e_request_latency_seconds",
        "e",
        ["model_name", "engine"],
        buckets=[0.5, 1.5, 2.5, 5.0, 10.0],
        registry=reg,
    )
    queries = Counter("vllm:prefix_cache_queries", "q", ["model_name", "engine"], registry=reg)
    hits = Counter("vllm:prefix_cache_hits", "h", ["model_name", "engine"], registry=reg)
    kv = Gauge("vllm:kv_cache_usage_perc", "kv", ["model_name", "engine"], registry=reg)
    running = Gauge("vllm:num_requests_running", "r", ["model_name", "engine"], registry=reg)
    waiting = Gauge("vllm:num_requests_waiting", "w", ["model_name", "engine"], registry=reg)
    flops = Counter(
        "vllm:estimated_flops_per_gpu_total", "f", ["model_name", "engine"], registry=reg
    )
    rbytes = Counter(
        "vllm:estimated_read_bytes_per_gpu_total", "rb", ["model_name", "engine"], registry=reg
    )
    wbytes = Counter(
        "vllm:estimated_write_bytes_per_gpu_total", "wb", ["model_name", "engine"], registry=reg
    )

    # t0: an engine that has been up a while (engine 0 served it all).
    success.labels(m, "0", "stop").inc(900)
    success.labels(m, "0", "length").inc(100)
    for _ in range(1000):
        prompt.labels(m, "0").observe(400)
        gen.labels(m, "0").observe(100)
        e2e.labels(m, "0").observe(2.0)
    queries.labels(m, "0").inc(400000)
    hits.labels(m, "0").inc(100000)
    for eng in ("0", "1"):
        flops.labels(m, eng).inc(1e15)
        rbytes.labels(m, eng).inc(1e14)
        wbytes.labels(m, eng).inc(1e13)
    kv.labels(m, "0").set(0.10)
    kv.labels(m, "1").set(0.12)
    running.labels(m, "0").set(4)
    waiting.labels(m, "0").set(0)
    (HERE / "vllm_window_t0.txt").write_bytes(generate_latest(reg))

    # The 60 s window: 120 requests, 512 in / 128 out each, half 1 s and half 3 s,
    # 40% of 61440 queried prompt tokens cached; engine 0 at MFU 0.20 / MBU 0.55,
    # engine 1 at MFU 0.40 / MBU 0.65.
    success.labels(m, "0", "stop").inc(100)
    success.labels(m, "0", "length").inc(20)
    for i in range(120):
        prompt.labels(m, "0").observe(512)
        gen.labels(m, "0").observe(128)
        e2e.labels(m, "0").observe(1.0 if i % 2 else 3.0)
    queries.labels(m, "0").inc(61440)
    hits.labels(m, "0").inc(24576)
    flops.labels(m, "0").inc(_flops(0.20))
    flops.labels(m, "1").inc(_flops(0.40))
    rbytes.labels(m, "0").inc(_bytes(0.50))
    wbytes.labels(m, "0").inc(_bytes(0.05))
    rbytes.labels(m, "1").inc(_bytes(0.60))
    wbytes.labels(m, "1").inc(_bytes(0.05))
    kv.labels(m, "0").set(0.37)
    kv.labels(m, "1").set(0.52)
    running.labels(m, "0").set(14)
    waiting.labels(m, "0").set(3)
    (HERE / "vllm_window_t1.txt").write_bytes(generate_latest(reg))


def sglang() -> None:
    reg = CollectorRegistry()
    labels = ["model_name"]
    m = "Qwen/Qwen3-8B"
    nreq = Counter("sglang:num_requests_total", "n", [*labels, "is_streaming"], registry=reg)
    prompt = Histogram(
        "sglang:prompt_tokens_histogram", "p", labels, buckets=[256, 1024, 4096], registry=reg
    )
    gen = Histogram(
        "sglang:generation_tokens_histogram", "g", labels, buckets=[128, 256, 1024], registry=reg
    )
    e2e = Histogram(
        "sglang:e2e_request_latency_seconds",
        "e",
        [*labels, "is_streaming"],
        buckets=[1.0, 2.0, 4.0, 8.0],
        registry=reg,
    )
    token_usage = Gauge("sglang:token_usage", "t", labels, registry=reg)
    full_usage = Gauge("sglang:full_token_usage", "t", labels, registry=reg)
    swa_usage = Gauge("sglang:swa_token_usage", "t", labels, registry=reg)
    mamba_usage = Gauge("sglang:mamba_usage", "t", labels, registry=reg)
    running = Gauge("sglang:num_running_reqs", "r", labels, registry=reg)
    queue = Gauge("sglang:num_queue_reqs", "q", labels, registry=reg)
    hit_rate = Gauge("sglang:cache_hit_rate", "c", labels, registry=reg)
    flops = Counter("sglang:estimated_flops_per_gpu_total", "f", labels, registry=reg)
    rbytes = Counter("sglang:estimated_read_bytes_per_gpu_total", "rb", labels, registry=reg)
    wbytes = Counter("sglang:estimated_write_bytes_per_gpu_total", "wb", labels, registry=reg)

    nreq.labels(m, "true").inc(500)
    for _ in range(500):
        prompt.labels(m).observe(300)
        gen.labels(m).observe(80)
        e2e.labels(m, "true").observe(1.5)
    flops.labels(m).inc(5e14)
    rbytes.labels(m).inc(5e13)
    wbytes.labels(m).inc(1e12)
    for g, v in ((token_usage, 0.2), (full_usage, 0.2), (swa_usage, 0.0), (mamba_usage, 0.0)):
        g.labels(m).set(v)
    running.labels(m).set(5)
    queue.labels(m).set(0)
    hit_rate.labels(m).set(0.30)
    (HERE / "sglang_window_t0.txt").write_bytes(generate_latest(reg))

    # 90 requests in 60 s (1.5 req/s), 1024 in / 256 out, half 2 s and half 6 s;
    # MFU 0.25, MBU 0.72 (0.70 read + 0.02 write).
    nreq.labels(m, "true").inc(60)
    nreq.labels(m, "false").inc(30)
    for i in range(90):
        prompt.labels(m).observe(1024)
        gen.labels(m).observe(256)
        e2e.labels(m, "true" if i < 60 else "false").observe(2.0 if i % 2 else 6.0)
    flops.labels(m).inc(_flops(0.25))
    rbytes.labels(m).inc(_bytes(0.70))
    wbytes.labels(m).inc(_bytes(0.02))
    for g, v in ((token_usage, 0.62), (full_usage, 0.62), (swa_usage, 0.0), (mamba_usage, 0.0)):
        g.labels(m).set(v)
    running.labels(m).set(22)
    queue.labels(m).set(5)
    hit_rate.labels(m).set(0.385)
    (HERE / "sglang_window_t1.txt").write_bytes(generate_latest(reg))


if __name__ == "__main__":
    vllm()
    sglang()
    print("wrote vllm_window_t0/t1.txt and sglang_window_t0/t1.txt")
