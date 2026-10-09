"""Qualify installed CLI integration on CPU with a pinned real Ollama runtime/model.

This is bounded functional acceptance, not a GPU performance or planner-accuracy
benchmark. Runtime/model pins come from the GitHub release asset and HF LFS APIs
captured 2026-10-04. No token-rate threshold is meaningful on shared hosted CPUs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from ci_installed_acceptance import assert_installed_origin, run_cli

OLLAMA_VERSION = "0.35.1"
OLLAMA_URL = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-linux-amd64.tar.zst"
OLLAMA_SHA256 = "9fcd79ac4575b2bd31b992eee18b1000c8ad126b451627c8f8cd091714cfbb10"
MODEL_REVISION = "09816acd5d99df7be770d85ea30822623dab342c"
MODEL_URL = (
    "https://huggingface.co/bartowski/SmolLM2-135M-Instruct-GGUF/resolve/"
    f"{MODEL_REVISION}/SmolLM2-135M-Instruct-Q4_K_M.gguf"
)
MODEL_SHA256 = "2e8040ceae7815abe0dcb3540b9995eaa1fa0d2ca9e797d0a635ae4433c68c2d"
MODEL_NAME = "ci-smollm2-135m:q4_k_m"
MAX_OUTPUT_TOKENS = 16
BENCH_RUNS = 3
STARTUP_TIMEOUT_SECONDS = 90
DOWNLOAD_TIMEOUT_SECONDS = 600
OPERATION_TIMEOUT_SECONDS = 180
STREAM_REQUESTS = 3


def verify_sha256(path: Path, expected: str) -> None:
    """Refuse bytes that do not match the immutable provenance pin."""
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError(f"SHA256 mismatch for {path.name}: {digest.hexdigest()} != {expected}")


def download(url: str, path: Path, sha256: str) -> None:
    """Bound downloads and retry transport failures without bypassing integrity."""
    subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--retry",
            "3",
            "--max-time",
            str(DOWNLOAD_TIMEOUT_SECONDS),
            "--output",
            str(path),
            url,
        ],
        check=True,
        timeout=DOWNLOAD_TIMEOUT_SECONDS * 2,
    )
    verify_sha256(path, sha256)


def validate_benchmark(result: dict, expected_runs: int) -> None:
    """A successful command must contain complete, positive, finite measurements."""
    assert result["model"] == MODEL_NAME and result["backend"] == "ollama"
    assert result["environment"]["backend_version"] == OLLAMA_VERSION
    runs = result["individual_runs"]
    assert len(runs) == result["runs"] == result["aggregate"]["count"] == expected_runs
    for run in runs:
        assert 0 < run["tokens_generated"] <= MAX_OUTPUT_TOKENS
        for field in ("throughput_tps", "total_duration_ms", "eval_duration_ms"):
            assert math.isfinite(run[field]) and run[field] > 0, (field, run)
        assert math.isfinite(run["ttft_ms"]) and run["ttft_ms"] >= 0
        assert math.isclose(
            run["throughput_tps"],
            run["tokens_generated"] / (run["eval_duration_ms"] / 1000),
            rel_tol=1e-12,
        )
    assert result["aggregate"]["tokens_generated"] == sum(r["tokens_generated"] for r in runs)
    assert not any("failed" in warning.lower() for warning in result["warnings"])


def wait_until_ready(client: httpx.Client, server: subprocess.Popen) -> None:
    """A version response must identify the pinned runtime before any acceptance."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error = "server has not answered"
    while time.monotonic() < deadline:
        assert server.poll() is None, f"Ollama exited during startup: {server.returncode}"
        try:
            response = client.get("/api/version")
            response.raise_for_status()
            assert response.json()["version"] == OLLAMA_VERSION, response.text
            return
        except (httpx.HTTPError, ValueError) as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"Ollama not ready within {STARTUP_TIMEOUT_SECONDS}s: {last_error}")


def stream_requests(client: httpx.Client, cwd: Path) -> Path:
    """Record actual token counts/timestamps; incomplete streams cannot become logs."""
    logs = []
    for index in range(STREAM_REQUESTS):
        started = time.time()
        chunks = []
        with client.stream(
            "POST",
            "/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": f"Name a color and explain it in a short sentence. {index}",
                "stream": True,
                "options": {"num_predict": MAX_OUTPUT_TOKENS},
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunks.append(json.loads(line))
        assert chunks and chunks[-1].get("done") is True, "stream ended without final metrics"
        assert any(chunk.get("response") for chunk in chunks), "stream generated no text"
        final = chunks[-1]
        assert 0 < final["eval_count"] <= MAX_OUTPUT_TOKENS and final["eval_duration"] > 0
        assert final["prompt_eval_count"] > 0
        logs.append(
            {
                "timestamp": started,
                "prompt_tokens": final["prompt_eval_count"],
                "completion_tokens": final["eval_count"],
            }
        )
    # Close a real stream early, then prove the runtime still serves subsequent requests.
    with client.stream(
        "POST",
        "/api/generate",
        json={
            "model": MODEL_NAME,
            "prompt": "Continue counting: one, two, three,",
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line and json.loads(line).get("response"):
                break
    recovered = client.post(
        "/api/generate",
        json={
            "model": MODEL_NAME,
            "prompt": "Name one color.",
            "stream": False,
        },
    )
    recovered.raise_for_status()
    assert recovered.json()["done"] is True and recovered.json()["eval_count"] > 0
    path = cwd / "real-request-log.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in logs), encoding="utf-8")
    return path


def validate_plan_benchmark(report: dict, saved: dict, runs: int) -> None:
    """A real CPU mismatch is useful evidence and cannot become GPU qualification."""
    assert report.get("kind") == "chimeraforge.plan-benchmark"
    assert report["plan"]["fingerprint"] == saved["fingerprint"]
    assert report["execution"]["requested_count"] == runs
    assert report["execution"]["successful_count"] == runs
    assert report["execution"]["failed_count"] == 0
    assert report["binding"]["hardware"]["state"] == "mismatch"
    assert report["binding"]["hardware"]["observed"] == {"device": "cpu"}
    assert report["binding"]["quant"]["observed"] == "Q4_K_M"
    assert report["configuration_status"] == "mismatch" and report["exit_code"] == 1
    assert report["audit"]["slo"]["state"] == "unverified"
    metric = report["audit"]["metrics"]["base_decode_tps"]
    assert metric["measured"] > 0 and metric["modeled"] > 0
    assert metric["delta"] is None and metric["state"] == "unverified"
    assert metric["raw_delta"] == metric["measured"] - metric["modeled"]
    assert report["execution"]["serving_after"]["loaded_gpu_bytes"] == 0
    for row in report["measurement"]["individual_runs"]:
        assert 0 < row["tokens_generated"] <= MAX_OUTPUT_TOKENS
        assert row["prompt_tokens"] > 0 and row["ttft_basis"] == "server-prefill-duration"


def accept_saved_plan(client: httpx.Client, cwd: Path, env: dict) -> dict:
    """Resolve the actual installed model, then benchmark an installed saved candidate."""
    source = cwd / "serving-plan.json"
    run_cli(
        [
            "plan",
            "--model",
            f"ollama:{MODEL_NAME}",
            "--ollama-url",
            str(client.base_url),
            "--hardware",
            "RTX 4080 12GB",
            "--budget",
            "100000",
            "--quality-target",
            "0",
            "--avg-tokens",
            str(MAX_OUTPUT_TOKENS),
            "--save",
            str(source),
            "--json",
        ],
        cwd,
        env,
    )
    original = source.read_bytes()
    saved = json.loads(original)
    chosen = next(
        index
        for index, row in enumerate(saved["result"]["candidates"])
        if row["backend"] == "ollama" and row["quant"] == "Q4_K_M"
    )
    directory = cwd / "plan-results"
    stdout = run_cli(
        [
            "bench",
            "--plan",
            str(source),
            "--candidate-index",
            str(chosen),
            "--runs",
            str(BENCH_RUNS),
            "--base-url",
            str(client.base_url),
            "--output-dir",
            str(directory),
            "--json",
        ],
        cwd,
        env,
        1,
    )
    report = json.loads(stdout)
    validate_plan_benchmark(report, saved, BENCH_RUNS)
    assert source.read_bytes() == original, "benchmark modified its saved plan"
    (receipt,) = directory.glob("plan-bench_*.json")
    assert json.loads(receipt.read_text(encoding="utf-8")) == report
    return {
        "saved_fingerprint": saved["fingerprint"],
        "receipt_fingerprint": report["fingerprint"],
        "observed_config": "Ollama quant/context/CPU device; TP/PP and GPU identity unavailable",
        "comparison": "native values and arithmetic delta; accuracy and SLO unverified",
    }


def validate_contribution_replay(report: dict, source: dict, runs: int) -> None:
    """Refuse trust/accuracy claims from replaying an unsigned GPU claim on CPU."""
    assert report["kind"] == "chimeraforge.contribution-replay"
    assert report["contribution"]["id"] == source["id"]
    assert report["contribution"]["attestation"]["signed"] is False
    assert report["trust"] == {
        "state": "unsigned_unverified",
        "changes_quarantine": False,
        "changes_corpus": False,
        "authenticates_producer": False,
    }
    assert report["replay_equivalence"]["state"] == "unverified"
    assert report["gpu_eligibility"]["state"] == "ineligible" and report["exit_code"] == 1
    execution = report["execution"]
    assert execution["requested_count"] == execution["successful_count"] == runs
    assert execution["failed_count"] == 0 and execution["serving_after"]["device"] == "cpu"
    samples = report["measurement"]["individual_runs"]
    assert len(samples) == runs and all(row["tokens_generated"] > 0 for row in samples)
    for name, unit in (("decode_tps", "tokens/second"), ("ttft_ms", "ms")):
        metric = report["comparison"][name]
        assert (
            metric["state"] == "unverified" and metric["delta"] is None and metric["unit"] == unit
        )
        assert metric["original_count"] == len(source["measurements"][name])
        assert metric["replayed_count"] == runs and math.isfinite(metric["replayed"])
        assert metric["raw_delta"] == metric["replayed"] - metric["original"]


def accept_contribution_replay(client: httpx.Client, cwd: Path, env: dict, cpu_bench: dict) -> dict:
    """Execute installed replay against real CPU serving; fixture GPU claims stay unsigned."""
    from chimeraforge.contrib import ContribError, build_contribution

    assert cpu_bench["environment"]["gpu_name"] is None
    try:
        build_contribution(cpu_bench)
    except ContribError as exc:
        assert "names no GPU" in str(exc), (
            "CPU export refusal came from an unrelated validation error"
        )
    else:
        raise AssertionError("CPU-only benchmark was exported as GPU evidence")
    # Explicit synthetic negative-case fixture, never an actual GPU measurement.
    declared = {
        "model": MODEL_NAME,
        "backend": "ollama",
        "quant": "Q4_K_M",
        "workload": "single",
        "runs": BENCH_RUNS,
        "context_length": 1024,
        "individual_runs": [{"throughput_tps": 1.0, "ttft_ms": 1.0} for _ in range(BENCH_RUNS)],
        "environment": {
            "gpu_name": "NVIDIA GeForce RTX 4090",
            "gpu_memory_gb": 24,
            "gpu_driver": None,
            "cuda_version": None,
            "os": "synthetic-fixture",
            "platform": "synthetic-fixture",
            "backend_name": "ollama",
            "backend_version": OLLAMA_VERSION,
            "chimeraforge_version": "0.46.0",
        },
        "timestamp": "2026-10-01T00:00:00+00:00",
    }
    contribution = build_contribution(declared)
    source, output = cwd / "unsigned-legacy-gpu-claim.json", cwd / "contribution-replay.json"
    source.write_text(json.dumps(contribution), encoding="utf-8")
    original = source.read_bytes()
    review = json.loads(run_cli(["contribute", "review", str(source), "--json"], cwd, env))
    assert (
        review["contribution"]["id"] == contribution["id"]
        and review["trust"]["changes_quarantine"] is False
    )
    report = json.loads(
        run_cli(
            [
                "contribute",
                "replay",
                str(source),
                "--prompt",
                "Reply with one short sentence.",
                "--output-tokens",
                str(MAX_OUTPUT_TOKENS),
                "--runs",
                str(BENCH_RUNS),
                "--base-url",
                str(client.base_url).rstrip("/"),
                "--out",
                str(output),
                "--json",
            ],
            cwd,
            env,
            1,
        )
    )
    validate_contribution_replay(report, contribution, BENCH_RUNS)
    assert source.read_bytes() == original and json.loads(output.read_text()) == report
    assert not (cwd / "cache/contributions").exists(), "replay changed quarantine"
    return {
        "source_id": contribution["id"],
        "receipt_fingerprint": report["fingerprint"],
        "input_evidence": "synthetic unsigned legacy GPU claim; not an actual GPU measurement",
        "execution_evidence": (
            "actual installed CPU/Ollama runner with native per-request tokens/timings"
        ),
        "gpu_eligibility": "ineligible",
        "replay_equivalence": "unverified",
        "cpu_gpu_export": "refused",
        "quarantine_and_trust": "unchanged",
    }


def accept_runtime(client: httpx.Client, cwd: Path, env: dict, version: str) -> dict:
    """Exercise the installed product using measurements made by the real backend."""
    results = cwd / "results"
    benchmark_stdout = run_cli(
        [
            "bench",
            "--model",
            MODEL_NAME,
            "--backend",
            "ollama",
            "--runs",
            str(BENCH_RUNS),
            "--base-url",
            str(client.base_url).rstrip("/"),
            "--output-dir",
            str(results),
            "--json",
        ],
        cwd,
        env,
    )
    files = list(results.glob("bench_*.json"))
    assert len(files) == 1, f"expected exactly one saved benchmark, found {files}"
    benchmark = json.loads(files[0].read_text(encoding="utf-8"))
    assert json.loads(benchmark_stdout) == benchmark, "stdout and saved JSON disagree"
    assert len(benchmark) == 1
    validate_benchmark(benchmark[0], BENCH_RUNS)
    assert benchmark[0]["environment"]["chimeraforge_version"] == version
    contribution_replay = accept_contribution_replay(client, cwd, env, benchmark[0])
    for fmt, filename, marker in (
        ("markdown", "report.md", "## Summary"),
        ("html", "report.html", "<!DOCTYPE html>"),
    ):
        destination = cwd / filename
        run_cli(
            [
                "report",
                "--results-files",
                str(files[0]),
                "--format",
                fmt,
                "--output",
                str(destination),
            ],
            cwd,
            env,
        )
        report = destination.read_text(encoding="utf-8")
        assert marker in report and MODEL_NAME in report
    log = stream_requests(client, cwd)
    profile_path = cwd / "workload.json"
    profile = json.loads(
        run_cli(
            [
                "workload",
                "--from-log",
                str(log),
                "--engine",
                "ollama",
                "--out",
                str(profile_path),
                "--json",
            ],
            cwd,
            env,
        )
    )
    assert profile["sample_count"] == STREAM_REQUESTS
    for field in ("request_rate", "prompt_tokens", "output_tokens"):
        assert profile["fields"][field]["provenance"] == "measured"
        assert profile["fields"][field]["value"] > 0
    assert "workload_cv2" not in profile["fields"], (
        "three requests cannot establish workload variance"
    )
    planned = json.loads(
        run_cli(
            [
                "plan",
                "--model-size",
                "3b",
                "--hardware",
                "RTX 4080 12GB",
                "--workload-profile",
                str(profile_path),
                "--mode",
                "batch",
                "--budget",
                "100000",
                "--no-network",
                "--json",
            ],
            cwd,
            env,
        )
    )
    assert planned and planned[0]["mode"] == "batch"
    saved_plan_benchmark = accept_saved_plan(client, cwd, env)
    error = run_cli(
        ["bench", "--model", "ci-definitely-missing-model", "--base-url", str(client.base_url)],
        cwd,
        env,
        1,
    )
    assert "Model not found" in error
    identity = run_cli(
        ["bench", "--model", MODEL_NAME, "--backend", "vllm", "--base-url", str(client.base_url)],
        cwd,
        env,
        1,
    )
    assert "ERROR" in identity, "real Ollama must not be filed as a vLLM measurement"
    malformed = run_cli(
        [
            "workload",
            "--from-metrics",
            str(client.base_url.join("api/version")),
            "--engine",
            "vllm",
            "--json",
        ],
        cwd,
        env,
        1,
    )
    assert not malformed.strip(), "malformed metrics must not emit a workload profile"
    return {
        "backend": f"ollama {OLLAMA_VERSION}",
        "model_revision": MODEL_REVISION,
        "model_sha256": MODEL_SHA256,
        "successful_bench_runs": BENCH_RUNS,
        "completed_streams": STREAM_REQUESTS,
        "interrupted_stream_recovery": "passed",
        "bench_report_workload_plan": "passed",
        "saved_plan_benchmark": saved_plan_benchmark,
        "contribution_replay": contribution_replay,
        "missing_model_identity_and_metrics_errors": "passed",
        "scope": "CPU functional integration; no performance or prediction-accuracy claim",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-version", required=True)
    parser.add_argument("--checkout", required=True, type=Path)
    args = parser.parse_args(argv)
    assert sys.platform == "linux" and platform.machine() == "x86_64", (
        "requires hosted Linux amd64 CPU runner"
    )
    import chimeraforge

    assert_installed_origin(chimeraforge.__file__, args.checkout)
    assert chimeraforge.__version__ == args.expect_version
    with tempfile.TemporaryDirectory(prefix="chimeraforge-cpu-") as temporary:
        work = Path(temporary)
        runtime = work / "runtime"
        runtime.mkdir()
        archive, model = work / "ollama.tar.zst", work / "model.gguf"
        download(OLLAMA_URL, archive, OLLAMA_SHA256)
        download(MODEL_URL, model, MODEL_SHA256)
        subprocess.run(
            ["tar", "--zstd", "-xf", str(archive), "-C", str(runtime)],
            check=True,
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
        archive.unlink()
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.update(
            {
                "OLLAMA_HOST": f"127.0.0.1:{port}",
                "OLLAMA_MODELS": str(work / "models"),
                "OLLAMA_NO_CLOUD": "1",
                "OLLAMA_NUM_PARALLEL": "1",
                "OLLAMA_MAX_LOADED_MODELS": "1",
                "CHIMERAFORGE_CACHE": str(work / "cache"),
                "NO_COLOR": "1",
            }
        )
        modelfile = work / "Modelfile"
        modelfile.write_text(
            f"FROM {model}\nPARAMETER num_gpu 0\nPARAMETER num_thread 2\nPARAMETER num_ctx 1024\n"
            f"PARAMETER num_predict {MAX_OUTPUT_TOKENS}\n"
            "PARAMETER seed 42\nPARAMETER temperature 0\n",
            encoding="utf-8",
        )
        binary = runtime / "bin/ollama"
        with (work / "server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [str(binary), "serve"],
                env=env,
                cwd=work,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                with httpx.Client(
                    base_url=f"http://127.0.0.1:{port}", timeout=OPERATION_TIMEOUT_SECONDS
                ) as client:
                    wait_until_ready(client, server)
                    subprocess.run(
                        [str(binary), "create", MODEL_NAME, "-f", str(modelfile)],
                        env=env,
                        cwd=work,
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=OPERATION_TIMEOUT_SECONDS,
                    )
                    receipt = accept_runtime(client, work, env, args.expect_version)
                    placement = client.get("/api/ps")
                    placement.raise_for_status()
                    running = placement.json()["models"]
                    assert running, f"runtime has no loaded model: {placement.text}"
                    assert all(row["size_vram"] == 0 for row in running), (
                        f"runtime unexpectedly used GPU memory: {placement.text}"
                    )
                    print(json.dumps(receipt, indent=2))
            finally:
                # The process group also owns Ollama's spawned model runner.
                import signal

                if server.poll() is None:
                    os.killpg(server.pid, signal.SIGTERM)
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(server.pid, signal.SIGKILL)
                        server.wait(timeout=10)
                if sys.exc_info()[0] is not None:
                    log.flush()
                    print(
                        (work / "server.log").read_text(encoding="utf-8")[-8000:], file=sys.stderr
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
