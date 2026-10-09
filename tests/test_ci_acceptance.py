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


def test_regression_gate_installed_consumer_protocol_through_real_cli(tmp_path, monkeypatch):
    """Source-only harness proof; hosted installed consumers retain their origin guard."""
    import json
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    script = load_script("ci_regression_gate")
    parent = load_script("ci_installed_acceptance")
    monkeypatch.setattr(parent, "assert_installed_origin", lambda *args: None)

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == expected_code, result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)
        return result.output

    monkeypatch.setattr(parent, "run_cli", source_cli)
    result = script.accept(tmp_path, {}, tmp_path / "checkout")
    assert result["installed_cli_outcomes"] == [0, 1, 2, 3]
    assert result["evidence_class"].startswith("synthetic protocol")
    report = json.loads((tmp_path / "regression-gate.json").read_text())
    report["pairs"][0]["metrics"].clear()
    from chimeraforge.planner.replay import digest

    report["fingerprint"] = digest(
        {key: value for key, value in report.items() if key != "fingerprint"}
    )
    with pytest.raises(AssertionError):
        script.validate(report, 0, (2, 2))


def cpu_gate_fixture(
    tmp_path,
    *,
    cached=(0, 0, 0),
    candidate_cached=None,
    disabled=None,
    candidate_elapsed=0.9,
    candidate_ttft=2.0,
    changed_model=False,
    prompt_lengths=(8, 8, 8),
    candidate_output=4,
):
    """Synthetic oracle fixture; no serving or independent-execution claim."""
    import json
    from chimeraforge import api
    from chimeraforge.planner.replay import digest
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
    from dataclasses import asdict

    script = load_script("ci_regression_gate")
    rows = [
        script.protocol_receipt(1.0),
        script.protocol_receipt(candidate_elapsed, candidate_ttft),
    ]
    candidate_cached = cached if candidate_cached is None else candidate_cached
    paths, originals = [], []
    for index, (row, counts) in enumerate(zip(rows, (cached, candidate_cached))):
        for phase in ("serving_before", "serving_after"):
            observation = row["execution"][phase]
            observation["version"] = "0.35.1"
            observation["prefix_cache"] = disabled
            if changed_model and index:
                observation["model_digest"] = "c" * 64
        for sample, count, prompt in zip(
            row["measurement"]["individual_runs"], counts, prompt_lengths
        ):
            sample["cached_prompt_tokens"] = count
            sample["prompt_tokens"] = prompt
            if index:
                sample["tokens_generated"] = candidate_output
                sample["throughput_tps"] = candidate_output / (sample["eval_duration_ms"] / 1000)
        row["measurement"]["aggregate"] = asdict(
            aggregate_runs(
                [RunMetrics(**sample) for sample in row["measurement"]["individual_runs"]]
            )
        )
        row["fingerprint"] = digest(
            {key: value for key, value in row.items() if key != "fingerprint"}
        )
        raw = json.dumps(row).encode()
        path = tmp_path / f"native-{index}.json"
        path.write_bytes(raw)
        paths.append(path)
        originals.append(raw)
    policy = api.RegressionPolicy(
        rules={"completed_token_rate_tps": 0.05, "ttft_ms": 0.1},
        fixed_controls={"device": "cpu", "backend": "ollama", "version": "0.35.1"},
    )
    report = api.gate_benchmarks([paths[0]], [paths[1]], policy=policy).to_dict()
    return script, tuple(originals), report


@pytest.mark.parametrize(
    "kwargs,code,states,reason",
    [
        ({}, 0, ("known", "known"), None),
        ({"candidate_elapsed": 2.0}, 1, ("known", "known"), None),
        ({"candidate_ttft": 3.0}, 1, ("known", "known"), None),
        ({"cached": (None, None, None)}, 3, ("unknown", "unknown"), "cache_evidence_unavailable"),
        ({"candidate_cached": (1, 1, 1)}, 3, ("known", "known"), "observed_cache_hits_changed"),
        (
            {"cached": (0, None, 0), "candidate_cached": (0, 0, 0)},
            3,
            ("unknown", "known"),
            "cache_evidence_unavailable",
        ),
        ({"cached": (None, None, None), "disabled": False}, 0, ("known", "known"), None),
        (
            {"cached": (1, 1, 1), "disabled": False},
            3,
            ("mismatch", "mismatch"),
            "cache_contradiction",
        ),
        ({"changed_model": True}, 3, ("known", "known"), "condition:model_digest"),
        ({"cached": (42, 42, 42), "prompt_lengths": (43, 43, 43)}, 0, ("known", "known"), None),
        (
            {"cached": (0, 8, 8), "candidate_cached": (None, 0, 8), "prompt_lengths": (1, 8, 8)},
            3,
            ("known", "unknown"),
            "observed_cache_hits_changed",
        ),
        ({"candidate_output": 3}, 3, ("known", "known"), "workload_or_actual_lengths_changed"),
    ],
)
def test_cpu_gate_oracle_derives_native_counts_and_conditional_outcome(
    tmp_path, kwargs, code, states, reason
):
    script, originals, report = cpu_gate_fixture(tmp_path, **kwargs)
    summary = script.validate_cpu(report, originals, "0.35.1", 3)
    assert summary["exit_code"] == code
    assert tuple(summary["cache"][arm]["state"] for arm in ("baseline", "candidate")) == states
    if reason:
        assert reason in summary["blockers"]
    assert summary["performance_threshold_qualification"] == "not asserted"
    assert summary["native_counts"]["baseline"]["prompt_tokens"] == list(
        kwargs.get("prompt_lengths", (8, 8, 8))
    )
    if kwargs.get("cached") == (None, None, None):
        assert summary["native_counts"]["baseline"]["cached_prompt_tokens"] == [None, None, None]


@pytest.mark.parametrize(
    "mutation",
    ["cache-state", "counter", "blocker", "metric", "outcome", "population", "input-sha"],
)
def test_cpu_gate_oracle_refuses_rehashed_false_native_evidence(tmp_path, mutation):
    import json
    from chimeraforge.planner.replay import digest

    kwargs = {"candidate_cached": (1, 1, 1)} if mutation == "blocker" else {}
    script, originals, report = cpu_gate_fixture(tmp_path, **kwargs)
    pair = report["pairs"][0]
    if mutation == "cache-state":
        pair["cache"]["baseline"]["state"] = "unknown"
    elif mutation == "counter":
        pair["cache"]["baseline"]["known_counts"] = [1, 1, 1]
    elif mutation == "blocker":
        pair["blockers"] = report["blockers"] = []
    elif mutation == "metric":
        pair["metrics"]["completed_token_rate_tps"]["regression_fraction"] = 0.5
    elif mutation == "outcome":
        report["exit_code"], report["outcome"] = 1, "regression"
    elif mutation == "population":
        row = json.loads(originals[0])
        row["measurement"]["individual_runs"].pop()
        row["execution"]["individual_runs"].pop()
        row["fingerprint"] = digest(
            {key: value for key, value in row.items() if key != "fingerprint"}
        )
        originals = (json.dumps(row).encode(), originals[1])
    else:
        report["inputs"]["baseline"][0]["sha256"] = "d" * 64
    report["fingerprint"] = digest(
        {key: value for key, value in report.items() if key != "fingerprint"}
    )
    with pytest.raises(AssertionError):
        script.validate_cpu(report, originals, "0.35.1", 3)


@pytest.mark.parametrize("code", [0, 1, 2, 3])
def test_cpu_native_cli_outcomes_never_admit_operational_error(tmp_path, monkeypatch, code):
    import subprocess

    script = load_script("ci_installed_acceptance")
    monkeypatch.setattr(
        script.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, code, "{}", ""),
    )
    if code == 2:
        with pytest.raises(AssertionError):
            script.run_cli(["gate"], tmp_path, {}, (0, 1, 3))
    else:
        assert script.run_cli(["gate"], tmp_path, {}, (0, 1, 3)) == "{}"


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({}, 0),
        ({"candidate_elapsed": 2.0}, 1),
        ({"cached": (None, None, None)}, 3),
        ({"candidate_cached": (1, 1, 1)}, 3),
    ],
)
def test_cpu_acceptance_consumes_native_outcome_through_real_gate_cli(
    tmp_path, monkeypatch, capsys, kwargs, code
):
    """Source CLI/oracle protocol only; benchmark generation is synthetic."""
    import json
    from typer.testing import CliRunner
    from chimeraforge.cli import app
    from chimeraforge.planner.replay import digest

    script, originals, _ = cpu_gate_fixture(tmp_path, **kwargs)
    parent = load_script("ci_installed_acceptance")
    rows = [json.loads(raw) for raw in originals]
    for row in rows:
        row["plan"]["served_model"] = "synthetic-protocol"
        row["measurement"]["warnings"] = ["synthetic-private-sentinel"]
        row["fingerprint"] = digest(
            {key: value for key, value in row.items() if key != "fingerprint"}
        )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(rows[0]))

    def source_cli(arguments, cwd, env, expected_code=0):
        if arguments[0] == "bench":
            assert expected_code == 1
            directory = Path(arguments[arguments.index("--output-dir") + 1])
            directory.mkdir()
            (directory / "plan-bench_synthetic.json").write_text(json.dumps(rows[1]))
            return json.dumps(rows[1])
        result = CliRunner().invoke(app, arguments)
        allowed = expected_code if isinstance(expected_code, tuple) else (expected_code,)
        assert result.exit_code in allowed, result.output
        return result.output

    monkeypatch.setattr(parent, "run_cli", source_cli)
    result = script.accept_cpu(
        tmp_path,
        {},
        tmp_path / "source.json",
        0,
        baseline,
        "synthetic-protocol",
        "http://127.0.0.1:1",
        "0.35.1",
        3,
    )
    assert result["exit_code"] == code and result["copied_receipt_refused"] is True
    output = capsys.readouterr().out
    diagnostic = json.loads(output)["cpu_gate_native_evidence"]
    assert diagnostic["validation"].startswith("pending")
    assert diagnostic["reported_exit_code"] == code
    assert "synthetic-private-sentinel" not in output + json.dumps(result)


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


def test_checkpoint_seed_entrypoint_imports_under_actual_isolated_python(tmp_path):
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "ci_checkpoint_identity.py"
    result = subprocess.run(
        [sys.executable, "-I", str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--seed" in result.stdout


@pytest.mark.parametrize(
    "mutation", ["source_authentication", "performance", "local_sha256", "exit_code"]
)
def test_portable_installed_consumer_refuses_incomplete_or_promoted_evidence(tmp_path, mutation):
    import copy
    import json
    from chimeraforge.api import PlanRequest, plan, create_plan_bundle, check_plan_bundle

    script = load_script("ci_plan_bundle")
    corpus, quality, path = (
        tmp_path / "models.json",
        tmp_path / "quality.json",
        tmp_path / "plan.json",
    )
    corpus.write_text(json.dumps({"vram": {"overhead_factor": 1.123}}))
    quality.write_text(
        json.dumps({"results": {"mmlu": {"acc,none": 0.83}}, "n-samples": {"mmlu": 5000}})
    )
    plan(PlanRequest(allow_network=False, models_path=str(corpus), quality_from=str(quality))).save(
        path
    )
    directory = tmp_path / "bundle"
    create_plan_bundle(path, directory)
    corpus.unlink()
    quality.unlink()
    raw = path.read_bytes()
    checked = check_plan_bundle(directory).to_dict()
    script.validate(checked, raw, directory)
    checked = copy.deepcopy(checked)
    if mutation == "source_authentication":
        checked["bundle"]["source_authentication"] = "verified"
    elif mutation == "performance":
        checked["performance"]["state"] = "passed"
    elif mutation == "local_sha256":
        checked["bundle"]["relocations"]["quality"]["local"]["sha256"] = "0" * 64
    else:
        checked["exit_code"] = 1
    with pytest.raises(AssertionError):
        script.validate(checked, raw, directory)


def test_bundle_harness_cli_commands_in_source_protocol_fixture(tmp_path, monkeypatch):
    # Exercise command wiring here; actual installed-origin proof is a separate hosted gate.
    script = load_script("ci_plan_bundle")
    installed = load_script("ci_installed_acceptance")
    monkeypatch.setattr(installed, "assert_installed_origin", lambda *_: None)
    receipt = script.produce(tmp_path / "handoff", Path(__file__).resolve().parents[1])
    assert receipt["producer_paths_absent"] is True
    assert len(receipt["plan_sha256"]) == 64


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
