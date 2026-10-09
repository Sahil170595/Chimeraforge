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


def test_mcp_http_acceptance_exercises_real_cli_and_closes_owned_process(tmp_path):
    pytest.importorskip("mcp", reason="optional [mcp] extra not installed")
    from chimeraforge import __version__

    script = load_script("ci_mcp_http")
    receipt = script.probe([sys.executable, "-m", "chimeraforge", "mcp"], cwd=tmp_path)
    assert receipt["serverInfo"]["version"] == __version__
    assert len(receipt["tools"]) == 5
    assert receipt["offline_default_plan"] == "passed"
    assert receipt["caller_network_override"] == "rejected"
    assert receipt["owned_process"] == "closed"


def test_cpu_probe_refuses_corrupt_download_before_installing(tmp_path):
    script = load_script("ci_cpu_serving")
    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"wrong artifact")
    with pytest.raises(ValueError, match="SHA256"):
        script.verify_sha256(artifact, "0" * 64)


def test_cpu_probe_refuses_plan_benchmark_presented_as_gpu_qualification():
    script = load_script("ci_cpu_serving")
    report = {
        "kind": "chimeraforge.plan-benchmark",
        "plan": {"fingerprint": "a" * 64},
        "execution": {
            "requested_count": 3,
            "successful_count": 3,
            "failed_count": 0,
            "serving_after": {"loaded_gpu_bytes": 0},
        },
        "binding": {
            "hardware": {"state": "mismatch", "observed": {"device": "cpu"}},
            "quant": {"observed": "Q4_K_M"},
        },
        "configuration_status": "mismatch",
        "exit_code": 1,
        "audit": {
            "slo": {"state": "unverified"},
            "metrics": {
                "base_decode_tps": {
                    "modeled": 50,
                    "measured": 40,
                    "raw_delta": -10,
                    "delta": None,
                    "state": "unverified",
                }
            },
        },
        "measurement": {
            "individual_runs": [
                {"tokens_generated": 4, "prompt_tokens": 8, "ttft_basis": "server-prefill-duration"}
                for _ in range(3)
            ]
        },
    }
    saved = {"fingerprint": "a" * 64}
    script.validate_plan_benchmark(report, saved, 3)
    report["audit"]["slo"]["state"] = "pass"
    with pytest.raises(AssertionError):
        script.validate_plan_benchmark(report, saved, 3)


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


@pytest.mark.parametrize("invalid", ["weight-proof", "lost-pin", "changed-checkpoint"])
def test_checkpoint_acceptance_refuses_misleading_identity_evidence(monkeypatch, tmp_path, invalid):
    import copy
    import json

    from chimeraforge.api import PlanRequest, check_plan, plan
    from chimeraforge.deploy import export_deployment

    script = load_script("ci_checkpoint_identity")
    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))
    seed = script.seed(live=False)
    artifact = plan(
        PlanRequest(
            models=[seed["repo"]],
            model_revisions={seed["repo"]: seed["commit"]},
            platform="linux",
            allow_network=False,
            quality_target=0,
            budget=100000,
        )
    )
    data, report = artifact.to_dict(), check_plan(artifact).to_dict()
    index = script.select_candidate(data)
    exported = json.loads(
        export_deployment(
            artifact, format="compose", candidate_index=index, image="test/image:1"
        ).content
    )
    script.validate(seed, data, report, exported)
    data, report, exported = copy.deepcopy((data, report, exported))
    if invalid == "weight-proof":
        data["result"]["specs"][seed["repo"]]["checkpoint"]["weight_bytes_verified"] = True
    elif invalid == "lost-pin":
        exported["services"]["inference"]["command"].remove("--revision")
    else:
        report["checkpoint_view"][seed["repo"]]["pinned_metadata"]["state"] = "changed"
    with pytest.raises(AssertionError):
        script.validate(seed, data, report, exported)
