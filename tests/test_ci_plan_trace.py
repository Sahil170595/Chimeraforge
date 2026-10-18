"""Source protocol qualification is distinct from installed-artifact and actual CPU proof."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.backends.base import Backend, GenerationObservation
from chimeraforge.bench.metrics import RunMetrics
from chimeraforge.cli import app
from chimeraforge.planner.replay import digest
from chimeraforge.planner.constants import DEFAULT_LATENCY_SLO_MS

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_cli(arguments, cwd, env, expected_code=0):
    result = CliRunner().invoke(app, arguments)
    allowed = expected_code if isinstance(expected_code, tuple) else (expected_code,)
    assert result.exit_code in allowed, result.output
    return result.stdout


def test_same_native_fixture_runs_plan_cli_and_keeps_twelve_default_cases(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    parent = script("ci_installed_acceptance")
    native = script("ci_native_stream")
    monkeypatch.setattr(parent, "assert_installed_origin", lambda *_: None)
    monkeypatch.setattr(parent, "run_cli", source_cli)
    path = tmp_path / "modeled-linux-plan.json"
    source_cli(
        [
            "plan",
            "--platform",
            "linux",
            "--avg-tokens",
            "4",
            "--prompt-tokens",
            "8",
            "--request-rate",
            "0.01",
            "--budget",
            "100000",
            "--no-network",
            "--save",
            str(path),
            "--json",
        ],
        tmp_path,
        {},
    )
    original = path.read_bytes()
    servers = []
    real_server = native.ThreadingHTTPServer

    def make_server(*args, **kwargs):
        instance = real_server(*args, **kwargs)
        servers.append(instance)
        return instance

    monkeypatch.setattr(native, "ThreadingHTTPServer", make_server)
    report = native.accept(tmp_path, {}, tmp_path / "checkout", plan_path=path)
    assert report["backends"] == ["vllm", "sglang", "tgi"]
    assert report["outcomes"] == ["single", "overcap", "abort", "incomplete"]
    assert len(servers) == 1 and servers[0].fileno() == -1
    bound = report["plan_bound_trace"]
    assert bound["complete"]["exit_code"] == 0
    assert bound["token_length_mismatch"]["exit_code"] == 1
    assert bound["token_length_mismatch"]["native_trace"]["exit_code"] == 0
    assert bound["invalid_cap_precontact"] and bound["output_alias_precontact"]
    assert bound["modeled_platform"] == "linux" and bound["engine_execution"] == "unverified"
    assert path.read_bytes() == original and report["server_cleanup"] == "completed"


class CPUBackend(Backend):
    name = "ollama"

    def __init__(self):
        self.calls = []
        self.closed = False

    async def health_check(self):
        return True, ""

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "fixture"

    async def observe_serving(self, model):
        return {"backend": "ollama", "model": model, "device": "cpu", "version": "fixture"}

    async def generate(self, model, prompt, options=None):
        return RunMetrics(2, 500, 1, 5, 1, 4, prompt_tokens=8)

    async def generate_observed(self, model, prompt, options, on_first_output):
        self.calls.append((model, prompt, options))
        on_first_output()
        return GenerationObservation(
            {"tokens_generated": 2, "prompt_tokens": 8, "eval_duration_ms": 4},
            2,
            "server-decode-duration/output-token-count",
        )

    async def close(self):
        self.closed = True


def test_cpu_plan_consumer_adds_one_short_request_without_new_server_or_weights(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    parent = script("ci_installed_acceptance")
    consumer = script("ci_cpu_trace")
    script("ci_native_stream")
    from chimeraforge.bench import trace

    backend = CPUBackend()
    monkeypatch.setattr(trace, "get_backend", lambda *args, **kwargs: backend)
    commands = []

    def run_cli(arguments, cwd, env, expected_code=0):
        commands.append(arguments)
        if arguments[0] == "plan":
            # Source-only metadata fixture; hosted CPU qualification uses the actual endpoint.
            saved = api.plan(
                api.PlanRequest(
                    allow_network=False,
                    avg_tokens=4,
                    prompt_tokens=8,
                    latency_slo=DEFAULT_LATENCY_SLO_MS,
                    quality_target=0,
                    budget=100000,
                )
            )
            saved.save(arguments[arguments.index("--save") + 1])
            return json.dumps(saved.to_dict()["result"]["candidates"])
        return source_cli(arguments, cwd, env, expected_code)

    monkeypatch.setattr(parent, "run_cli", run_cli)
    report = consumer.accept_plan(
        tmp_path, {}, "already-loaded-model", "http://local:11434", "fixture"
    )
    assert [row[0] for row in commands] == ["plan", "trace"]
    assert len(backend.calls) == 1 and backend.calls[0][2] == {"num_predict": 4}
    assert backend.closed
    assert report["receipt"]["exit_code"] == 1
    assert report["receipt"]["native_trace"]["exit_code"] == 0
    assert report["receipt"]["binding"]["summary"]["hardware"]["state"] == "mismatch"
    assert report["receipt"]["binding"]["token_lengths"]["output_tokens"]["state"] == "mismatch"
    assert report["source_bytes_unchanged"] and report["extra_weight_downloads"] == 0

    path = tmp_path / "plan-trace-cpu-plan.json"
    workload_path = tmp_path / "plan-trace-cpu-workload.json"
    saved = json.loads(path.read_bytes())
    workload = json.loads(workload_path.read_bytes())
    for mutation in (
        "gpu",
        "fingerprint",
        "native_raw_hash",
        "drop_request",
        "slo_state",
        "saved_target",
    ):
        invalid = copy.deepcopy(report["receipt"])
        if mutation == "gpu":
            invalid["native_trace"]["serving_after"]["device"] = "gpu"
        elif mutation == "fingerprint":
            invalid["plan"]["fingerprint"] = "a" * 64
        elif mutation == "native_raw_hash":
            invalid["native_trace"]["workload"]["raw_sha256"] = "a" * 64
        elif mutation == "drop_request":
            invalid["native_trace"]["requests"] = []
        elif mutation == "slo_state":
            invalid["slo"]["state"] = "not_requested"
        else:
            invalid["slo"]["targets"]["latency_ms"] = None
        invalid["native_trace"]["fingerprint"] = digest(
            {k: v for k, v in invalid["native_trace"].items() if k != "fingerprint"}
        )
        invalid["fingerprint"] = digest({k: v for k, v in invalid.items() if k != "fingerprint"})
        with pytest.raises((AssertionError, api.PlanError)):
            consumer.validate_plan(
                invalid,
                saved,
                workload,
                workload_path.read_bytes(),
                "already-loaded-model",
                "fixture",
            )
