from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any

import yaml

from banterhearts.api.inference.registry import ModelRegistry
from banterhearts.api.inference.service import InferenceConfig, InferenceService
from banterhearts.compilation.pipeline import run_pipeline_and_persist
from banterhearts.runtime.capabilities import CapabilityReport, detect_capabilities

try:
    from scripts.tr117.instrumentation import ResourceMonitor
except ImportError:
    ResourceMonitor = None  # Instrumentation optional

try:  # Optional heavy dep
    import torch  # type: ignore
except Exception:  # pragma: no cover - optional
    torch = None


@dataclass
class RunSpec:
    scenario: str
    prompt_set: str
    prompts: list[str]
    backend: str
    model: str
    quantization: str
    stream: bool
    mode: str


@dataclass
class RunResult:
    spec: RunSpec
    status: str
    error: str | None
    latencies_ms: list[float]
    ttft_ms: list[float]
    tokens: list[int]
    outputs: list[str]
    accuracy: float | None
    backend_used: str
    decision_reason: str | None
    capabilities: dict[str, Any]
    started_at: float
    # Resource metrics (optional, from instrumentation)
    resource_metrics: dict[str, Any] | None = None
    degraded_count: int = 0
    degraded_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": asdict(self.spec),
            "status": self.status,
            "error": self.error,
            "latencies_ms": self.latencies_ms,
            "ttft_ms": self.ttft_ms,
            "tokens": self.tokens,
            "outputs": self.outputs,
            "accuracy": self.accuracy,
            "backend_used": self.backend_used,
            "decision_reason": self.decision_reason,
            "capabilities": self.capabilities,
            "started_at": self.started_at,
            "degraded_count": self.degraded_count,
            "degraded_reasons": self.degraded_reasons,
        }


def _load_config(config_path: Path) -> dict[str, Any]:
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _resolve_prompts(cfg: dict[str, Any], prompt_set: str) -> list[str]:
    prompts = cfg.get("prompt_sets", {}).get(prompt_set)
    if not prompts:
        raise ValueError(f"prompt_set '{prompt_set}' not found in config")
    return [str(p) for p in prompts]


def _should_skip_backend(backend: str, caps: CapabilityReport) -> str | None:
    available = set(caps.available_backends)
    if backend in available:
        return None
    return f"backend_unavailable:{backend}"


def _should_skip_combo(backend: str, model: str) -> str | None:
    is_drive = len(model) >= 2 and model[1] == ":"
    is_ollama_model = (":" in model) and not is_drive
    is_path = "/" in model or "\\" in model
    if backend == "ollama" and not is_ollama_model:
        return "incompatible:ollama_requires_ollama_model"
    if backend.startswith("transformers") and is_ollama_model:
        return "incompatible:transformers_cannot_load_ollama_model"
    if backend in ("onnxruntime", "tensorrt") and is_ollama_model:
        return "incompatible:onnx/trt_need_local_model"
    if backend in ("onnxruntime", "tensorrt") and not is_path:
        return None  # registry path fallback is ok
    return None


def _apply_env_for_backend(backend: str, model: str, quantization: str) -> None:
    os.environ["BANTER_FORCE_BACKEND"] = backend
    os.environ["BANTER_QUANT_MODE"] = quantization
    if backend.startswith("transformers"):
        # Assume BANTER_TRANSFORMER_MODEL is already set to a valid local path.
        pass
    elif backend == "ollama":
        os.environ["BANTER_OLLAMA_MODEL"] = model


def _similarity(a: str, b: str) -> float:
    return float(SequenceMatcher(None, a, b).ratio())


def _get_baseline_outputs(
    service: InferenceService,
    prompts: list[str],
    model: str,
    backend: str,
) -> tuple[list[str], bool]:
    """
    Returns: (outputs, any_degraded)
    """
    _apply_env_for_backend(backend, model, "fp32")
    outputs: list[str] = []
    any_degraded = False
    for prompt in prompts:
        result = service.generate(prompt, model=model)
        outputs.append(result.response)
        if result.degraded:
            any_degraded = True
    return outputs, any_degraded


def _compute_accuracy(
    baseline: list[str], candidates: list[str]
) -> tuple[float | None, list[float]]:
    if not baseline or not candidates or len(baseline) != len(candidates):
        return None, []
    sims = [_similarity(b, c) for b, c in zip(baseline, candidates, strict=False)]
    return float(statistics.mean(sims)), sims


def _run_prompts(
    service: InferenceService,
    spec: RunSpec,
    repetitions: int,
    baseline_cache: dict[tuple[str, str], list[str]],
    baseline_backend: str,
    accuracy_threshold: float,
) -> RunResult:
    latencies_ms: list[float] = []
    ttft_ms: list[float] = []
    tokens: list[int] = []
    outputs: list[str] = []
    decision_reason: str | None = None
    started_at = time.time()
    degraded_count = 0
    degraded_reasons: list[str] = []

    baseline_key = (spec.model, spec.prompt_set)
    baseline_data = baseline_cache.get(baseline_key)

    if baseline_data is None:
        try:
            baseline_outputs, baseline_degraded = _get_baseline_outputs(
                service, spec.prompts, spec.model, baseline_backend
            )
            baseline_data = (baseline_outputs, baseline_degraded)
            baseline_cache[baseline_key] = baseline_data
        except Exception as exc:  # pragma: no cover - runtime dependency
            return RunResult(
                spec=spec,
                status="baseline_error",
                error=str(exc),
                latencies_ms=[],
                ttft_ms=[],
                tokens=[],
                outputs=[],
                accuracy=None,
                backend_used=spec.backend,
                decision_reason=None,
                capabilities=service.capabilities.to_dict(),
                started_at=started_at,
                degraded_count=0,
                degraded_reasons=[],
            )

    for _ in range(repetitions):
        for prompt in spec.prompts:
            _apply_env_for_backend(spec.backend, spec.model, spec.quantization)
            decision = service._select_backend(prompt)  # type: ignore[attr-defined]
            decision_reason = decision.reason
            try:
                if spec.mode == "dual":
                    # Simulate two agents and take max latency as critical path.
                    result_a = service.generate(prompt, model=spec.model)
                    result_b = service.generate(prompt, model=spec.model)
                    latency_ms = max(result_a.latency_ms, result_b.latency_ms)
                    latencies_ms.append(latency_ms)
                    ttft_ms.append(latency_ms)
                    tokens.append(result_a.tokens_generated + result_b.tokens_generated)
                    outputs.extend([result_a.response, result_b.response])
                    if result_a.degraded:
                        degraded_count += 1
                        if result_a.degraded_reason:
                            degraded_reasons.append(result_a.degraded_reason)
                    if result_b.degraded:
                        degraded_count += 1
                        if result_b.degraded_reason:
                            degraded_reasons.append(result_b.degraded_reason)
                else:
                    result = service.generate(prompt, model=spec.model)
                    latency_ms = result.latency_ms
                    latencies_ms.append(latency_ms)
                    ttft_ms.append(latency_ms)
                    tokens.append(result.tokens_generated)
                    outputs.append(result.response)
                    if result.degraded:
                        degraded_count += 1
                        if result.degraded_reason:
                            degraded_reasons.append(result.degraded_reason)
            except Exception as exc:  # pragma: no cover - runtime safety
                return RunResult(
                    spec=spec,
                    status="error",
                    error=str(exc),
                    latencies_ms=latencies_ms,
                    ttft_ms=ttft_ms,
                    tokens=tokens,
                    outputs=outputs,
                    accuracy=None,
                    backend_used=spec.backend,
                    decision_reason=decision_reason,
                    capabilities=service.capabilities.to_dict(),
                    started_at=started_at,
                    degraded_count=degraded_count,
                    degraded_reasons=degraded_reasons,
                )

    baseline_outputs, baseline_degraded = baseline_data
    expanded_baseline = baseline_outputs * (2 if spec.mode == "dual" else 1)
    accuracy, _ = _compute_accuracy(expanded_baseline, outputs)

    # Determine status
    if degraded_count > 0:
        status = "degraded"
        error = (
            f"{degraded_count} degraded response(s): {', '.join(set(degraded_reasons))}"
        )
    elif baseline_degraded:
        # Skip accuracy check if baseline is degraded
        status = "ok" if degraded_count == 0 else "degraded"
        error = "baseline_degraded: accuracy check skipped" if status == "ok" else error
    elif accuracy is not None and accuracy < accuracy_threshold:
        status = "fail_accuracy"
        error = (
            f"accuracy {accuracy:.3f} below threshold {accuracy_threshold:.3f} "
            f"baseline_backend={baseline_backend}"
        )
    else:
        status = "ok"
        error = None

    return RunResult(
        spec=spec,
        status=status,
        error=error,
        latencies_ms=latencies_ms,
        ttft_ms=ttft_ms,
        tokens=tokens,
        outputs=outputs,
        accuracy=accuracy,
        backend_used=spec.backend,
        decision_reason=decision_reason,
        capabilities=service.capabilities.to_dict(),
        started_at=started_at,
        degraded_count=degraded_count,
        degraded_reasons=degraded_reasons,
    )


def _persist_run(out_dir: Path, result: RunResult) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(result.started_at * 1000)
    out_file = out_dir / f"run_{ts}.json"
    out_file.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return out_file


def _summarize(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0}
    return {
        "mean": float(statistics.mean(latencies_ms)),
        "p50": float(statistics.median(latencies_ms)),
        "p95": float(statistics.quantiles(latencies_ms, n=100, method="inclusive")[94]),
    }


def _dependency_report() -> dict[str, bool]:
    optional = {
        "onnxruntime": False,
        "tensorrt": False,
        "pycuda.driver": False,
        "matplotlib": False,
        "torch": False,
    }
    for module in list(optional.keys()):
        try:
            __import__(module)
            optional[module] = True
        except Exception:
            optional[module] = False
    return optional


def _ensure_optional_deps(report: dict[str, bool]) -> None:
    to_install = []
    if not report.get("onnxruntime", False):
        to_install.append("onnxruntime")
    if not report.get("matplotlib", False):
        to_install.append("matplotlib")
    if not report.get("torch", False):
        to_install.append("torch")
    # tensorrt and pycuda are environment-specific; emit guidance only.
    if to_install:
        cmd = [os.getenv("PYTHON", "python"), "-m", "pip", "install", *to_install]
        print(f"Attempting to install missing deps: {' '.join(to_install)}")
        try:
            subprocess.run(cmd, check=False)
        except Exception as exc:  # pragma: no cover
            print(f"Dependency install failed: {exc}")


def _prepare_quant_artifacts(
    model_name: str, quant_mode: str
) -> tuple[str | None, str | None]:
    """
    Run a tiny PTQ/QAT compile to produce manifests for benchmarking metadata.
    Returns (summary_path, error).
    """
    if torch is None:
        return None, "torch_missing"
    try:
        tiny = torch.nn.Sequential(
            torch.nn.Linear(4, 8),
            torch.nn.ReLU(),
            torch.nn.Linear(8, 2),
        )
        example = torch.randn(1, 4)
        _manifests, _summary, summary_path = run_pipeline_and_persist(
            tiny,
            example,
            model_name=f"tr117_{model_name}_{quant_mode}",
            quantization_mode=quant_mode,
            backend_preference="auto",
        )
        return str(summary_path), None
    except Exception as exc:  # pragma: no cover - optional path
        return None, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TR117 cross-backend benchmark.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scripts/tr117/configs/matrix.yaml"),
        help="Path to matrix config.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/tr117/runs"),
        help="Where to write run artifacts.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=None,
        help="Override repetitions from config.",
    )
    parser.add_argument(
        "--ensure-optional-deps",
        action="store_true",
        help="Attempt pip install of optional deps (onnxruntime, matplotlib).",
    )
    parser.add_argument(
        "--prepare-quant",
        action="store_true",
        help="Run a tiny PTQ/QAT pipeline per model/quant mode to generate manifests.",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    repetitions = args.repetitions or int(cfg.get("repetitions", 1))
    baseline_backend = cfg.get("baseline_backend", "transformers-cpu")
    accuracy_threshold = float(cfg.get("accuracy_threshold", 0.95))
    capabilities = detect_capabilities()
    deps = _dependency_report()
    if args.ensure_optional_deps:
        _ensure_optional_deps(deps)
        deps = _dependency_report()
    print(f"Capabilities: {capabilities.available_backends}")
    print(f"Dependency check: {deps}")
    scenarios = cfg.get("scenarios", [])
    backends = cfg.get("backends", [])
    models = cfg.get("models", [])
    quant_modes = cfg.get("quantization", {}).get("modes", ["fp32"])

    registry = ModelRegistry()
    service = InferenceService(registry=registry, config=InferenceConfig())
    baseline_cache: dict[tuple[str, str], tuple[list[str], bool]] = {}
    quant_manifests: dict[tuple[str, str], tuple[str | None, str | None]] = {}

    if args.prepare_quant:
        for model_entry in models:
            model_name = model_entry["name"]
            for quant in quant_modes:
                if quant in ("fp32", "fp16"):
                    continue
                key = (model_name, quant)
                summary_path, err = _prepare_quant_artifacts(model_name, quant)
                quant_manifests[key] = (summary_path, err)
                print(f"Prepared quant {key}: summary={summary_path} err={err}")

    for scenario in scenarios:
        scenario_name = scenario["name"]
        prompt_set = scenario["prompt_set"]
        stream = bool(scenario.get("stream", False))
        mode = scenario.get("mode", "single")
        prompts = _resolve_prompts(cfg, prompt_set)
        for backend in backends:
            skip_reason = _should_skip_backend(backend, capabilities)
            if skip_reason:
                out_dir = args.output_root / scenario_name / backend / "skipped"
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "skip.txt").write_text(skip_reason, encoding="utf-8")
                continue
            for model_entry in models:
                model_name = model_entry["name"]
                combo_skip = _should_skip_combo(backend, model_name)
                if combo_skip:
                    out_dir = (
                        args.output_root
                        / scenario_name
                        / backend
                        / "skipped_combo"
                        / model_name.replace("/", "_").replace(":", "_")
                    )
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / "skip.txt").write_text(combo_skip, encoding="utf-8")
                    continue
                for quant in quant_modes:
                    spec = RunSpec(
                        scenario=scenario_name,
                        prompt_set=prompt_set,
                        prompts=prompts,
                        backend=backend,
                        model=model_name,
                        quantization=quant,
                        stream=stream,
                        mode=mode,
                    )
                    result = _run_prompts(
                        service,
                        spec,
                        repetitions,
                        baseline_cache,
                        baseline_backend,
                        accuracy_threshold,
                    )
                    out_dir = (
                        args.output_root
                        / scenario_name
                        / backend
                        / quant
                        / model_name.replace("/", "_").replace(":", "_")
                    )
                    run_file = _persist_run(out_dir, result)
                    summary = _summarize(result.latencies_ms)
                    msg = (
                        f"[{result.status}] {spec.scenario} | {spec.backend} | "
                        f"{spec.model} | {spec.quantization} "
                        f"mean={summary['mean']:.2f}ms p95={summary['p95']:.2f}ms "
                        f"acc={result.accuracy if result.accuracy is not None else -1:.3f} "
                        f"-> {run_file}"
                    )
                    print(msg)


if __name__ == "__main__":
    main()
