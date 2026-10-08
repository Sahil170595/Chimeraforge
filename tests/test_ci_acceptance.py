"""The acceptance harness must refuse misleading or incomplete evidence."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


def test_installed_origin_rejects_checkout_and_editable_installs(tmp_path):
    script = load_script("ci_installed_acceptance")
    with pytest.raises(AssertionError, match="checkout"):
        script.assert_installed_origin(tmp_path / "src/chimeraforge/__init__.py", tmp_path)
    with pytest.raises(AssertionError, match="site-packages"):
        script.assert_installed_origin(
            tmp_path / "other/chimeraforge/__init__.py", tmp_path / "checkout"
        )
    script.assert_installed_origin(
        tmp_path / "venv/site-packages/chimeraforge/__init__.py", tmp_path / "checkout"
    )


def test_cpu_probe_refuses_corrupt_download_before_installing(tmp_path):
    script = load_script("ci_cpu_serving")
    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"wrong artifact")
    with pytest.raises(ValueError, match="SHA256"):
        script.verify_sha256(artifact, "0" * 64)


def test_cpu_probe_refuses_plan_benchmark_presented_as_gpu_qualification():
    script = load_script("ci_cpu_serving")
    with pytest.raises(AssertionError):
        script.validate_plan_benchmark({"audit": {"slo": {"state": "pass"}}}, {}, 3)


@pytest.mark.parametrize("invalid", ["zero tokens", "lost run", "wrong backend", "nonfinite"])
def test_cpu_probe_refuses_invalid_benchmark_evidence(invalid):
    from chimeraforge.bench.metrics import (
        BenchmarkResult,
        EnvironmentInfo,
        RunMetrics,
        aggregate_runs,
        result_to_dict,
    )

    script = load_script("ci_cpu_serving")
    runs = [RunMetrics(4, 20, 5, 200, 5, 195) for _ in range(3)]
    result = result_to_dict(
        BenchmarkResult(
            script.MODEL_NAME,
            "ollama",
            "Q4_K_M",
            "single",
            3,
            512,
            runs,
            aggregate_runs(runs),
            EnvironmentInfo(
                "Linux", "x86_64", "3.12", "test", None, None, None, "ollama", script.OLLAMA_VERSION
            ),
            "2026-10-04T00:00:00Z",
        )
    )
    if invalid == "zero tokens":
        result["individual_runs"][0]["tokens_generated"] = 0
    elif invalid == "lost run":
        result["individual_runs"].pop()
    elif invalid == "wrong backend":
        result["environment"]["backend_version"] = "unknown"
    else:
        result["individual_runs"][0]["throughput_tps"] = float("nan")
    with pytest.raises(AssertionError):
        script.validate_benchmark(result, 3)


def test_mutation_anchor_fails_closed_when_production_code_changes():
    script = load_script("ci_mutation_check")
    with pytest.raises(ValueError, match="exactly once"):
        script.replace_once("unrelated source", "expected anchor", "mutated anchor")
    with pytest.raises(ValueError, match="exactly once"):
        script.replace_once("anchor anchor", "anchor", "mutation")
    assert script.replace_once("one anchor only", "anchor", "mutation") == "one mutation only"
