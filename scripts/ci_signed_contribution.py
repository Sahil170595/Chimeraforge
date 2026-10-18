"""Installed signed exchange acceptance with explicitly synthetic HTTP replay facts."""

from __future__ import annotations

import base64
import copy
from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import statistics
import threading

SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PRIVATE_GATE_INPUT = "PRIVATE_SIGNED_GATE_INPUT_071"


def _seal(data: dict) -> dict:
    from chimeraforge.planner.replay import digest

    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    return data


def gate_fixtures() -> tuple[dict, dict, dict]:
    from ci_regression_gate import CPU_GATE_RULES, protocol_receipt

    rows = [protocol_receipt(1.0), protocol_receipt(0.9)]
    for row in rows:
        row["measurement"]["warnings"].append(PRIVATE_GATE_INPUT)
        row["execution"]["request"]["options"]["private"] = PRIVATE_GATE_INPUT
        _seal(row)
    return rows[0], rows[1], {"rules": dict(CPU_GATE_RULES), "fixed_controls": {"device": "cpu"}}


def native_expectation(left: dict, right: dict, version: str, runs: int) -> dict:
    """Independently derive this two-rule CPU decision from original native facts."""
    from chimeraforge.bench.gate import FACTS, _fact
    from chimeraforge.bench.gate_inputs import MAX_TOKEN_COUNT
    from chimeraforge.bench.metrics import BENCHMARK_WALL_BASIS
    from chimeraforge.bench.serving import _ollama_name, safe_observation
    from ci_regression_gate import CPU_GATE_RULES, _cpu_cache

    values, bases, workloads, caches, signatures = {}, {}, {}, {}, []
    observed: dict[str, list[dict]] = {}
    blocked = set()
    fixed = {"device": "cpu", "backend": "ollama", "version": version}
    for arm, native in (("baseline", left), ("candidate", right)):
        execution, measurement = native["execution"], native["measurement"]
        rows, request = measurement["individual_runs"], execution["request"]
        if execution["failed_count"] or execution["successful_count"] != runs or len(rows) != runs:
            blocked.add("incomplete_population")
        before, after = [
            safe_observation(execution[phase]) for phase in ("serving_before", "serving_after")
        ]
        observed[arm] = []
        for phase in (before, after):
            facts = {name: _fact(phase, name) for name in sorted(FACTS)}
            if facts["backend"] == "ollama" and isinstance(facts["model"], str):
                facts["model"] = _ollama_name(facts["model"])
            observed[arm].append(facts)
        caches[arm] = _cpu_cache(rows, before, after)
        if caches[arm]["state"] != "known":
            blocked.add("cache_unavailable_or_contradictory")
        cap_keys = [
            key
            for key in ("num_predict", "max_tokens", "max_new_tokens")
            if key in request["options"]
        ]
        assert len(cap_keys) == 1
        cap = request["options"][cap_keys[0]]
        lengths = sorted(
            [(row.get("prompt_tokens"), row["tokens_generated"]) for row in rows], key=str
        )
        if any(prompt is None or prompt <= 0 or output <= 0 for prompt, output in lengths):
            blocked.add("actual_lengths_unavailable")
        assert all(row["tokens_generated"] <= cap for row in rows)
        workloads[arm] = {
            **{
                key: request.get(key)
                for key in (
                    "prompt_sha256",
                    "prompt_characters",
                    "workload",
                    "concurrency",
                    "arrival_rate",
                    "requested_count",
                )
            },
            "options_sha256": hashlib.sha256(
                json.dumps(
                    request["options"], sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest(),
            "context_length": measurement["context_length"],
            "cap_option": cap_keys[0],
            "output_cap": cap,
            "actual_lengths": lengths,
        }
        elapsed = execution["elapsed_seconds"]
        wall_known = (
            math.isfinite(elapsed)
            and elapsed > 0
            and execution["elapsed_seconds_basis"] == BENCHMARK_WALL_BASIS
            and all(row["tokens_generated"] > 0 for row in rows)
        )
        prefill_known = before.get("backend") == after.get("backend") == "ollama" and all(
            row["ttft_basis"] == "server-prefill-duration" and row["ttft_ms"] > 0 for row in rows
        )
        values[arm] = {
            "completed_token_rate_tps": sum(row["tokens_generated"] for row in rows) / elapsed
            if wall_known
            else None,
            "ttft_ms": statistics.mean(row["ttft_ms"] for row in rows) if prefill_known else None,
        }
        bases[arm] = {
            "completed_token_rate_tps": BENCHMARK_WALL_BASIS if wall_known else None,
            "ttft_ms": "server-prefill-duration" if prefill_known else None,
        }
        signatures.append(
            {
                "rows": sorted(rows, key=lambda row: json.dumps(row, sort_keys=True)),
                "workload": workloads[arm],
                "observed": observed[arm],
                "elapsed": elapsed,
                "counts": [
                    execution[k] for k in ("requested_count", "successful_count", "failed_count")
                ],
            }
        )
    for name in sorted(FACTS):
        population = [phase[name] for arm in observed.values() for phase in arm]
        known = [value for value in population if value is not None]
        if (
            any(value != known[0] for value in known[1:])
            or name in fixed
            and any(value != fixed[name] for value in population)
        ):
            blocked.add("condition:" + name)
    if workloads["baseline"] != workloads["candidate"]:
        blocked.add("committed_workload_or_lengths")
    for current, other in (
        (caches["baseline"], caches["candidate"]),
        (caches["candidate"], caches["baseline"]),
    ):
        residual = sorted(
            (Counter(current["known_counts"]) - Counter(other["known_counts"])).elements()
        )
        capacities = sorted(
            0 if other["disabled_observed"] else MAX_TOKEN_COUNT if value is None else value
            for value in other["unknown_prompt_capacities"]
        )
        if len(residual) > len(capacities) or any(
            value > cap
            for value, cap in zip(residual, capacities[len(capacities) - len(residual) :])
        ):
            blocked.add("cache_population")
    if signatures[0] == signatures[1]:
        blocked.add("duplicate_population")
    fractions: dict[str, float | None] = {}
    for name in CPU_GATE_RULES:
        baseline, candidate = values["baseline"][name], values["candidate"][name]
        if (
            baseline is None
            or candidate is None
            or bases["baseline"][name] != bases["candidate"][name]
        ):
            blocked.add("metric:" + name)
            fractions[name] = None
        else:
            fractions[name] = (
                (baseline - candidate)
                if name == "completed_token_rate_tps"
                else (candidate - baseline)
            ) / baseline
    breach = any(
        value is not None and value > CPU_GATE_RULES[name] for name, value in fractions.items()
    )
    code = 3 if blocked else 1 if breach else 0
    return {
        "exit_code": code,
        "values": values,
        "bases": bases,
        "fractions": fractions,
        "blocked": sorted(blocked),
    }


def _operation_summary(data: dict) -> dict:
    return {
        "exit_code": data.get("exit_code", 0),
        "status": data.get("status", "signed"),
        "kind": data["kind"],
        "id": data.get("id", data.get("contribution", {}).get("id")),
        "signature_state": data.get("signature", {}).get("state"),
        "trust_state": data.get("trust", {}).get("state"),
        "private_binding_state": data.get("private_binding", {}).get("state"),
        "successful_count": data.get("execution", {}).get("successful_count"),
    }


def _json_report(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def _keys(cwd: Path, prefix: str, seed: bytes = SEED) -> tuple[Path, Path]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private, public = cwd / (prefix + ".key"), cwd / (prefix + ".pub")
    private.write_bytes(seed)
    public.write_bytes(Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw())
    return private, public


def _sign(cwd: Path, env: dict, source: Path, key: Path, output: Path) -> dict:
    from ci_installed_acceptance import run_cli

    artifact = _json_report(
        run_cli(
            [
                "contribute",
                "sign",
                str(source),
                "--private-key",
                str(key),
                "--out",
                str(output),
                "--json",
            ],
            cwd,
            env,
        )
    )
    assert json.loads(output.read_bytes()) == artifact
    return artifact


def _gate(
    cwd: Path,
    env: dict,
    baseline: Path,
    candidate: Path,
    keys: list[Path],
    policy: Path,
    output: Path,
    code: int,
) -> dict:
    from ci_installed_acceptance import run_cli

    args = [
        "contribute",
        "gate",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--policy",
        str(policy),
        "--out",
        str(output),
        "--json",
    ]
    for key in keys:
        args.extend(["--trusted-key", str(key)])
    report = _json_report(run_cli(args, cwd, env, code))
    assert json.loads(output.read_bytes()) == report
    return report


def validate_gate(
    report: dict,
    code: int,
    native: tuple[dict, dict],
    artifacts: tuple[Path, Path],
    *,
    auth: tuple[tuple[str, str], tuple[str, str]] = (
        ("valid", "trusted_key"),
        ("valid", "trusted_key"),
    ),
    policy: dict | None = None,
) -> dict:
    from dataclasses import asdict
    from chimeraforge.bench.gate import RegressionPolicy
    from chimeraforge.signed_payload import hash_json
    from chimeraforge.bench.gate_inputs import SERIALIZATION_ROUNDOFF
    from ci_regression_gate import CPU_GATE_RULES

    assert (
        report["schema_version"] == 1 and report["kind"] == "chimeraforge.signed-contribution-gate"
    )
    assert report["fingerprint"] == hash_json(
        {k: v for k, v in report.items() if k != "fingerprint"}
    )
    assert report["exit_code"] == code
    expected_policy = policy or {"rules": CPU_GATE_RULES, "fixed_controls": {"device": "cpu"}}
    assert report["policy"] == asdict(RegressionPolicy(**expected_policy))
    assert report["status"] == (
        "authentication_failed"
        if any(state == "invalid" for state, _ in auth)
        else {0: "conditional_pass", 1: "regression", 3: "inconclusive"}[code]
    )
    assert PRIVATE_GATE_INPUT not in json.dumps(report)
    assert report["assurance"]["embedded_key_is_trust"] is False
    assert report["assurance"]["independent_executions_verified"] is False
    assert report["assurance"]["measurement_truth"] == "unverified"
    assert report["assurance"]["original_hardware"] == "unverified"
    assert report["assurance"]["served_weights"] == "unverified"
    for arm, path, states in zip(("baseline", "candidate"), artifacts, auth):
        raw = path.read_bytes()
        artifact = json.loads(raw)
        assert len(report[arm]) == 1
        received = report[arm][0]
        assert received["index"] == 0
        assert received["envelope_sha256"] == hashlib.sha256(raw).hexdigest()
        assert (
            received["envelope_size_bytes"] == len(raw)
            and received["artifact_id"] == artifact["id"]
        )
        assert (
            received["payload_sha256"]
            == hashlib.sha256(base64.b64decode(artifact["payload_base64"])).hexdigest()
        )
        assert (
            received["public_key_sha256"]
            == hashlib.sha256(base64.b64decode(artifact["public_key_base64"])).hexdigest()
        )
        assert (received["signature_state"], received["trust_state"]) == states
    assert len(report["comparisons"]) == 1
    pair = report["comparisons"][0]
    assert pair["index"] == 0
    trusted = all(states == ("valid", "trusted_key") for states in auth)
    assert report["assurance"]["authenticates_producer_keys"] is trusted
    if not trusted:
        assert pair["metrics"] == {}
    else:
        expected = native_expectation(
            *native,
            native[0]["execution"]["serving_after"]["version"],
            native[0]["execution"]["requested_count"],
        )
        assert code == expected["exit_code"]
        assert bool(report["blockers"]) is bool(expected["blocked"])
        assert set(pair["metrics"]) == set(CPU_GATE_RULES)
        for name, metric in pair["metrics"].items():
            for arm in ("baseline", "candidate"):
                assert metric[arm] == expected["values"][arm][name]
                assert metric[arm + "_basis"] == expected["bases"][arm][name]
            fraction = expected["fractions"][name]
            assert metric["max_regression_fraction"] == CPU_GATE_RULES[name]
            assert (
                metric["regression_fraction"] is None
                if fraction is None
                else math.isclose(
                    metric["regression_fraction"],
                    fraction,
                    rel_tol=SERIALIZATION_ROUNDOFF,
                    abs_tol=SERIALIZATION_ROUNDOFF,
                )
            )
    return {
        "exit_code": code,
        "status": report["status"],
        "counts": {
            "baseline": len(report["baseline"]),
            "candidate": len(report["candidate"]),
            "pairs": len(report["comparisons"]),
        },
        "authentication": [
            {"signature": row["signature_state"], "trust": row["trust_state"]}
            for arm in ("baseline", "candidate")
            for row in report[arm]
        ],
        "fingerprint": report["fingerprint"],
    }


def _crypto_gate_probe(
    cwd: Path, env: dict, baseline: Path, candidate: Path, key: Path, policy: Path, native: dict
) -> dict:
    from chimeraforge.contrib import build_contribution

    legacy = copy.deepcopy(native["measurement"])
    legacy.update(
        quant="Q4_K_M",
        timestamp="2026-10-18T00:00:00+00:00",
        environment={
            "gpu_name": "synthetic-client",
            "gpu_memory_gb": 1,
            "gpu_driver": None,
            "cuda_version": None,
            "os": "synthetic",
            "platform": "synthetic",
            "backend_name": "ollama",
            "backend_version": "synthetic-protocol",
            "chimeraforge_version": "synthetic",
        },
    )
    unsigned = cwd / "signed-gate-unsigned-v1.json"
    unsigned.write_text(json.dumps(build_contribution(legacy)))
    code = """import builtins,json,sys
original = builtins.__import__
def blocked(name,*args,**kwargs):
    if name == 'cryptography' or name.startswith('cryptography.'):
        raise ImportError('blocked optional extra')
    return original(name,*args,**kwargs)
builtins.__import__ = blocked
from chimeraforge import api
from chimeraforge.contrib import verify_contribution
verify_contribution(json.load(open(sys.argv[5])))
result = api.gate_signed_contributions(
    [sys.argv[1]],[sys.argv[2]],trusted_keys=(sys.argv[3],),policy=sys.argv[4]
)
assert result.exit_code == 3
print(json.dumps({'v1':'PASS','gate_exit':result.exit_code}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            code,
            str(baseline),
            str(candidate),
            str(key),
            str(policy),
            str(unsigned),
        ],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = _json_report(result.stdout)
    assert report == {"v1": "PASS", "gate_exit": 3}
    return report


def _contradictory_artifact(artifact: dict, field: str) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from chimeraforge.signed_contribution import message, artifact_id

    payload = json.loads(base64.b64decode(artifact["payload_base64"]))
    if field == "prefill_alias":
        payload["measurement"]["individual_runs"][0]["prompt_eval_duration_ms"] = 20
    else:
        payload["request"]["output_token_cap"] = 1
    raw = json.dumps(payload).encode()
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    public = key.public_key().public_bytes_raw()
    signature = key.sign(message(public, raw))
    return {
        **artifact,
        "payload_base64": base64.b64encode(raw).decode(),
        "signature_base64": base64.b64encode(signature).decode(),
        "id": artifact_id(public, raw, signature),
    }


def accept_gate(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
    from dataclasses import asdict
    from ci_installed_acceptance import assert_installed_origin, run_cli

    assert_installed_origin(chimeraforge.__file__, checkout)
    left, right, policy = gate_fixtures()
    private, public = _keys(cwd, "signed-gate")
    plan = cwd / "signed-gate-policy.json"
    plan.write_text(json.dumps(policy))
    paths = (cwd / "signed-gate-baseline-native.json", cwd / "signed-gate-candidate-native.json")
    artifacts = (cwd / "signed-gate-baseline.json", cwd / "signed-gate-candidate.json")
    for path, native, artifact in zip(paths, (left, right), artifacts):
        path.write_bytes((json.dumps(native, indent=3) + "\n\n").encode())
        _sign(cwd, env, path, private, artifact)
    originals = {path: path.read_bytes() for path in (*paths, *artifacts, private, public, plan)}
    output = cwd / "signed-gate-result.json"
    passed = _gate(cwd, env, *artifacts, [public], plan, output, 0)
    summary = {"pass": validate_gate(passed, 0, (left, right), artifacts)}
    untrusted = _gate(cwd, env, *artifacts, [], plan, output, 3)
    summary["untrusted"] = validate_gate(
        untrusted,
        3,
        (left, right),
        artifacts,
        auth=(("valid", "untrusted_key"), ("valid", "untrusted_key")),
    )
    changed = json.loads(artifacts[1].read_bytes())
    raw = bytearray(base64.b64decode(changed["signature_base64"]))
    raw[0] ^= 1
    changed["signature_base64"] = base64.b64encode(raw).decode()
    invalid = cwd / "signed-gate-invalid.json"
    invalid.write_text(json.dumps(changed))
    report = _gate(cwd, env, artifacts[0], invalid, [], plan, output, 1)
    summary["invalid"] = validate_gate(
        report,
        1,
        (left, right),
        (artifacts[0], invalid),
        auth=(("valid", "untrusted_key"), ("invalid", "unverified")),
    )
    for name in ("regression", "partial", "semantic_copy", "options_mismatch"):
        native = copy.deepcopy(left if name == "semantic_copy" else right)
        key, trusted = private, [public]
        if name == "regression":
            native["execution"]["elapsed_seconds"] = 2.0
        elif name == "partial":
            native["measurement"]["individual_runs"].pop()
            native["measurement"]["aggregate"] = asdict(
                aggregate_runs(
                    [RunMetrics(**row) for row in native["measurement"]["individual_runs"]]
                )
            )
            native["execution"].update(
                successful_count=2,
                failed_count=1,
                individual_runs=copy.deepcopy(native["measurement"]["individual_runs"]),
            )
        elif name == "semantic_copy":
            key, other = _keys(cwd, "signed-gate-other", bytes([7]) * 32)
            trusted.append(other)
            native["created_at"] = native["measurement"]["timestamp"] = "relabeled-synthetic"
            for sample in native["measurement"]["individual_runs"]:
                for field in (
                    "throughput_tps",
                    "ttft_ms",
                    "total_duration_ms",
                    "prompt_eval_duration_ms",
                    "eval_duration_ms",
                ):
                    sample[field] = float(sample[field])
        else:
            native["execution"]["request"]["options"]["ignored-map-entry"] = 0
        source, target = cwd / (name + "-native.json"), cwd / (name + "-signed.json")
        source.write_text(json.dumps(_seal(native)))
        _sign(cwd, env, source, key, target)
        code = 1 if name == "regression" else 3
        report = _gate(cwd, env, artifacts[0], target, trusted, plan, output, code)
        summary[name] = validate_gate(report, code, (left, native), (artifacts[0], target))
        if name == "semantic_copy":
            assert report["baseline"][0]["artifact_id"] != report["candidate"][0]["artifact_id"]
            assert (
                report["baseline"][0]["evidence_sha256"]
                == report["candidate"][0]["evidence_sha256"]
            )
    malformed = cwd / "signed-gate-malformed.json"
    malformed.write_text(
        json.dumps({**json.loads(artifacts[1].read_bytes()), PRIVATE_GATE_INPUT: True})
    )
    bad = [
        "contribute",
        "gate",
        "--baseline",
        str(artifacts[0]),
        "--candidate",
        str(malformed),
        "--policy",
        str(plan),
        "--trusted-key",
        str(public),
        "--json",
    ]
    error = _json_report(run_cli(bad, cwd, env, 2))
    assert error["error"] and PRIVATE_GATE_INPUT not in json.dumps(error)
    for field in ("prefill_alias", "output_cap"):
        malformed.write_text(
            json.dumps(_contradictory_artifact(json.loads(artifacts[1].read_bytes()), field))
        )
        error = _json_report(run_cli(bad, cwd, env, 2))
        assert error["error"] and PRIVATE_GATE_INPUT not in json.dumps(error)
    for path in (*artifacts, public, plan):
        error = _json_report(
            run_cli(
                [
                    "contribute",
                    "gate",
                    "--baseline",
                    str(artifacts[0]),
                    "--candidate",
                    str(artifacts[1]),
                    "--trusted-key",
                    str(public),
                    "--policy",
                    str(plan),
                    "--out",
                    str(path),
                    "--json",
                ],
                cwd,
                env,
                2,
            )
        )
        assert error["error"] and path.read_bytes() == originals[path]
    alias = cwd / "signed-gate-outside-alias.json"
    os.link(artifacts[0], alias)
    try:
        error = _json_report(
            run_cli(
                [
                    "contribute",
                    "gate",
                    "--baseline",
                    str(artifacts[0]),
                    "--candidate",
                    str(artifacts[1]),
                    "--trusted-key",
                    str(public),
                    "--policy",
                    str(plan),
                    "--out",
                    str(alias),
                    "--json",
                ],
                cwd,
                env,
                2,
            )
        )
        assert error["error"] and alias.read_bytes() == originals[artifacts[0]]
    finally:
        alias.unlink()
    summary["without_crypto"] = _crypto_gate_probe(cwd, env, *artifacts, public, plan, left)
    assert all(path.read_bytes() == raw for path, raw in originals.items())
    return {
        **summary,
        "input_aliases_refused": True,
        "source_bytes_unchanged": True,
        "scope": (
            "synthetic installed signature/native-gate protocol; "
            "measurement truth and independent execution unverified"
        ),
    }


def accept_cpu_gate(
    cwd: Path, env: dict, baseline: Path, candidate: Path, version: str, runs: int
) -> dict:
    from ci_regression_gate import CPU_GATE_RULES

    originals = [path.read_bytes() for path in (baseline, candidate)]
    native = (json.loads(originals[0]), json.loads(originals[1]))
    expected = native_expectation(*native, version, runs)
    private, public = _keys(cwd, "cpu-signed-gate")
    artifacts = (cwd / "cpu-signed-baseline.json", cwd / "cpu-signed-candidate.json")
    for source, target in zip((baseline, candidate), artifacts):
        _sign(cwd, env, source, private, target)
    policy = cwd / "cpu-signed-gate-policy.json"
    chosen = {
        "rules": CPU_GATE_RULES,
        "fixed_controls": {"device": "cpu", "backend": "ollama", "version": version},
    }
    policy.write_text(json.dumps(chosen))
    report = _gate(
        cwd, env, *artifacts, [public], policy, cwd / "cpu-signed-gate.json", expected["exit_code"]
    )
    summary = validate_gate(report, expected["exit_code"], native, artifacts, policy=chosen)
    assert originals == [path.read_bytes() for path in (baseline, candidate)]
    return {
        **summary,
        "extra_inference_requests": 0,
        "evidence_class": (
            "two existing actual CPU receipts; "
            "no GPU, measurement-truth or performance-floor qualification"
        ),
    }


class Protocol(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *args: object) -> None:
        pass

    def send(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/":
            raw = b"Ollama is running"
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif self.path == "/api/version":
            self.send({"version": "synthetic-protocol"})
        elif self.path in ("/api/tags", "/api/ps"):
            self.send(
                {
                    "models": [
                        {
                            "name": "synthetic-protocol:latest",
                            "digest": "a" * 64,
                            "context_length": 2048,
                            "size": 1,
                            "size_vram": 0,
                        }
                    ]
                }
            )
        else:
            self.send({})

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        if self.path == "/api/generate":
            assert body["prompt"] == "hello" and body["options"] == {
                "num_predict": 4,
                "num_ctx": 2048,
            }
            type(self).calls += 1
            self.send(
                {
                    "response": "SYNTHETIC PRIVATE COMPLETION",
                    "done": True,
                    "eval_count": 4,
                    "eval_duration": 100000000,
                    "prompt_eval_count": 8,
                    "prompt_eval_cached_count": 0,
                    "prompt_eval_duration": 2000000,
                    "total_duration": 102000000,
                }
            )
        else:
            self.send({"details": {"quantization_level": "Q4_K_M"}, "model_info": {}})


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from chimeraforge.contrib import build_contribution
    from chimeraforge.planner.replay import digest
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from ci_regression_gate import protocol_receipt

    assert_installed_origin(chimeraforge.__file__, checkout)
    native = protocol_receipt(1.0)
    native["execution"]["request"]["prompt_sha256"] = hashlib.sha256(b"hello").hexdigest()
    native["fingerprint"] = digest({k: v for k, v in native.items() if k != "fingerprint"})
    source, private_key, trusted_key, workload, artifact = [
        cwd / name
        for name in (
            "signed-native.json",
            "synthetic-key.pem",
            "synthetic-public.pem",
            "private-signed.json",
            "signed-contribution.json",
        )
    ]
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    source.write_text(json.dumps(native))
    private_key.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    trusted_key.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    workload.write_text(
        json.dumps({"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}})
    )
    signed = json.loads(
        run_cli(
            [
                "contribute",
                "sign",
                str(source),
                "--private-key",
                str(private_key),
                "--out",
                str(artifact),
                "--json",
            ],
            cwd,
            env,
        )
    )
    assert signed == json.loads(artifact.read_bytes()) and signed["schema_version"] == 2
    verify_args = ["contribute", "verify", str(artifact), "--format", "v2", "--json"]
    untrusted = json.loads(run_cli(verify_args, cwd, env, 3))
    verified = json.loads(run_cli([*verify_args, "--trusted-key", str(trusted_key)], cwd, env))
    assert untrusted["signature"]["state"] == verified["signature"]["state"] == "valid"
    assert (
        verified["trust"]["state"] == "trusted_key"
        and not untrusted["trust"]["embedded_key_is_trust"]
    )
    Protocol.calls = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), Protocol)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        replay_args = [
            "contribute",
            "replay",
            str(artifact),
            "--format",
            "v2",
            "--private-workload",
            str(workload),
            "--trusted-key",
            str(trusted_key),
            "--base-url",
            f"http://127.0.0.1:{server.server_port}",
            "--json",
        ]
        workload.write_text(
            json.dumps({"prompt": "wrong", "options": {"num_predict": 4, "num_ctx": 2048}})
        )
        mismatch = json.loads(run_cli(replay_args, cwd, env, 1))
        assert mismatch["private_binding"]["state"] == "mismatch" and Protocol.calls == 0
        workload.write_text(
            json.dumps({"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}})
        )
        replayed = json.loads(run_cli(replay_args, cwd, env))
        assert Protocol.calls == replayed["execution"]["successful_count"] == 3
        assert replayed["replay_equivalence"]["original_wire_options"] == "unverified"
        assert replayed["execution"]["count_state"] == "observed"
        assert "SYNTHETIC PRIVATE COMPLETION" not in json.dumps(replayed)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        assert not thread.is_alive()
    legacy_measurement = copy.deepcopy(native["measurement"])
    legacy_measurement["quant"] = "Q4_K_M"
    legacy_measurement["timestamp"] = "2026-10-12T00:00:00+00:00"
    legacy_measurement["environment"] = {
        "gpu_name": "synthetic-client",
        "gpu_memory_gb": 1,
        "gpu_driver": None,
        "cuda_version": None,
        "os": "synthetic",
        "platform": "synthetic",
        "backend_name": "ollama",
        "backend_version": "synthetic-protocol",
        "chimeraforge_version": chimeraforge.__version__,
    }
    legacy = cwd / "unsigned-core-fixture.json"
    legacy.write_text(json.dumps(build_contribution(legacy_measurement)))
    core_code = (
        "import builtins,json,sys; original=builtins.__import__; "
        "exec('def blocked(name,*args,**kwargs):\\n "
        'if name=="cryptography" or name.startswith("cryptography."): '
        'raise ImportError("blocked optional extra")\\n '
        "return original(name,*args,**kwargs)\\n'); builtins.__import__=blocked; "
        "from chimeraforge import api; from chimeraforge.contrib import verify_contribution; "
        "verify_contribution(json.load(open(sys.argv[2]))); "
        "result=api.verify_signed_contribution(sys.argv[1],trusted_keys=(sys.argv[3],)); "
        "assert result.exit_code==3; print(json.dumps({'v1':'PASS','v2_exit':result.exit_code}))"
    )
    probe = subprocess.run(
        [sys.executable, "-I", "-B", "-c", core_code, str(artifact), str(legacy), str(trusted_key)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    assert json.loads(probe.stdout) == {"v1": "PASS", "v2_exit": 3}
    return {
        "scope": "explicitly synthetic installed HTTP/signature protocol, no model/hardware proof",
        "signed": _operation_summary(signed),
        "verified": _operation_summary(verified),
        "untrusted": _operation_summary(untrusted),
        "private_mismatch": _operation_summary(mismatch),
        "replay": _operation_summary(replayed),
        "core_without_optional_crypto": json.loads(probe.stdout),
        "fixture_server_closed": True,
    }
