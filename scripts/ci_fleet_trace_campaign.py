"""Regenerate native protocol and explicitly synthetic whole-fleet campaign controls."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree as ET

from ci_fleet_trace import MEMBERS, REQUESTS, certificates, server
from ci_fleet_trace_gate import declared_policy, synthetic

EXECUTIONS = 2
CAMPAIGN_TIMEOUT = 90


def run_raw(args: list[str], cwd: Path, env: dict, wanted: int) -> bytes:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "chimeraforge.cli", *args],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    assert result.returncode == wanted, result.stderr.decode("utf-8") + result.stdout.decode(
        "utf-8"
    )
    return result.stdout


def campaign_policy(left: dict, right: dict) -> dict:
    return {
        "schema_version": 1,
        "expected_executions": EXECUTIONS,
        "campaign_timeout_seconds": left["manifest"]["controls"]["campaign_timeout_seconds"],
        "fleet": declared_policy(
            left["executions"][0]["receipt"], right["executions"][0]["receipt"]
        ),
    }


def matching_campaign(saved: Path, durations: list[float]) -> dict:
    """Pure native builders with synthetic clocks/metadata, never generated traffic."""
    from chimeraforge.bench.fleet_campaign_types import (
        CAMPAIGN_LIMITS,
        KIND,
        MANIFEST_KIND,
        canonical_hash,
    )
    from chimeraforge import api

    children = [synthetic(saved, duration=value) for value in durations]
    first = children[0]
    manifest = {
        "schema_version": 1,
        "kind": MANIFEST_KIND,
        "prepared_at": first["created_at"],
        "tool": first["tool"],
        "plan": first["plan"],
        "workload": first["workload"],
        "ordered_descriptors": [row["descriptor"] for row in first["native_trace"]["requests"]],
        "endpoints": first["endpoints"],
        "routes": first["routes"],
        "population": {
            "executions": len(children),
            "original_replicas": MEMBERS,
            "requests_per_execution": REQUESTS,
            "total_requests": len(children) * REQUESTS,
        },
        "controls": {**first["controls"], "campaign_timeout_seconds": CAMPAIGN_TIMEOUT},
        "policy": {
            "execution": "serial",
            "retries": 0,
            "warmup_executions": 0,
            "stop_after_first_unavailable_execution": True,
        },
        "scope": (
            "Client-recorded intent; external preregistration, traffic "
            "and independence unauthenticated."
        ),
    }
    manifest["fingerprint"] = canonical_hash(manifest)
    slots = []
    for index, child in enumerate(children):
        child["native_trace"]["clock"]["origin"] = 1000 + 10 * index
        child["native_trace"]["fingerprint"] = canonical_hash(
            {k: v for k, v in child["native_trace"].items() if k != "fingerprint"}
        )
        child["fingerprint"] = canonical_hash(
            {k: v for k, v in child.items() if k != "fingerprint"}
        )
        slots.append(
            {
                "index": index,
                "manifest_fingerprint": manifest["fingerprint"],
                "state": "completed",
                "execution_complete": True,
                "reason": None,
                "error": None,
                "start_s": 1 + 10 * index,
                "end_s": 1
                + 10 * index
                + child["native_trace"]["execution"]["elapsed_seconds"]
                + 0.01,
                "receipt": child,
            }
        )
    data = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": first["created_at"],
        "tool": first["tool"],
        "manifest": manifest,
        "executions": slots,
        "execution": {
            "planned": len(slots),
            "completed": len(slots),
            "incomplete": 0,
            "failed": 0,
            "not_started": 0,
        },
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": 999,
            "elapsed_seconds": slots[-1]["end_s"] + 0.01,
        },
        "stop_reason": None,
        "state": "completed",
        "configuration_status": "unverified",
        "exit_code": 0,
        "cleanup": {
            "state": "completed",
            "owned_children": len(slots),
            "joined_children": len(slots),
            "owned_waiters": 0,
            "joined_waiters": 0,
        },
        "limits": CAMPAIGN_LIMITS,
    }
    data["fingerprint"] = canonical_hash(data)
    assert api.load_fleet_trace_campaign(data).to_dict() == data
    return data


def gate_control(cwd: Path, env: dict, left: dict, right: dict, wanted: int, label: str) -> dict:
    from chimeraforge import api

    chosen = campaign_policy(left, right)
    direct = api.gate_fleet_trace_campaigns(left, right, policy=chosen)
    assert direct.exit_code == wanted
    paths = {key: cwd / f"{label}-{key}.json" for key in ("left", "right", "policy")}
    for key, data in (("left", left), ("right", right), ("policy", chosen)):
        paths[key].write_text(json.dumps(data), encoding="utf-8")
    xml = cwd / f"{label}.xml"
    output = cwd / f"{label}-decision.json"
    raw = run_raw(
        [
            "gate",
            "--kind",
            "fleet-trace-campaign",
            "--baseline",
            str(paths["left"]),
            "--candidate",
            str(paths["right"]),
            "--policy",
            str(paths["policy"]),
            "--out",
            str(output),
            "--junit",
            str(xml),
            "--json",
        ],
        cwd,
        env,
        wanted,
    )
    assert raw == output.read_bytes() and b"\r\n" not in raw
    data = json.loads(raw)
    suite = ET.fromstring(xml.read_bytes())
    assert data["exit_code"] == wanted and int(suite.attrib["tests"]) == 5
    assert int(suite.attrib["errors"]) == (5 if wanted == 3 else 0)
    assert bool(int(suite.attrib["failures"])) == (wanted == 1)
    assert all(
        len(data["inputs"][arm]["executions"]) == EXECUTIONS for arm in ("baseline", "candidate")
    )
    return {
        "label": label,
        "api_exit": direct.exit_code,
        "cli_exit": wanted,
        "junit_cases": 5,
        "junit_errors": int(suite.attrib["errors"]),
        "junit_failures": int(suite.attrib["failures"]),
        "stdout_matches_file_bytes": True,
    }


def accept(cwd: Path, env: dict, saved: Path, checkout: Path | None = None) -> dict:
    from chimeraforge import api
    from ci_installed_acceptance import assert_installed_modules

    cwd.mkdir(parents=True, exist_ok=True)
    before = assert_installed_modules(checkout) if checkout else None
    held_source = saved.read_bytes()
    plan = json.loads(held_source)
    paths = certificates(cwd / "tls")
    held_tls = {name: path.read_bytes() for name, path in paths.items()}
    controls, aliases, admission = [], [], []
    for backend in ("vllm", "sglang"):
        index = next(
            i
            for i, row in enumerate(plan["result"]["candidates"])
            if row["backend"] == backend and row["quant"] == "FP16" and row["n_agents"] == MEMBERS
        )
        candidate = plan["result"]["candidates"][index]
        model, cap = candidate["model"], candidate["decode_tokens_per_req"]
        requests = [
            {
                "request_id": f"campaign-{i}",
                "prompt": f"private-campaign-prompt-{i}",
                "max_output_tokens": cap,
                "arrival_offset_s": 0,
            }
            for i in range(REQUESTS)
        ]
        routes = [
            {"request_id": row["request_id"], "endpoint_id": f"member-{i % MEMBERS + 1}"}
            for i, row in enumerate(requests)
        ]
        work, routing = cwd / "work.json", cwd / "routes.json"
        work.write_text(json.dumps(requests), encoding="utf-8")
        routing.write_text(json.dumps(routes), encoding="utf-8")
        held = {path: path.read_bytes() for path in (saved, work, routing)}
        for mode in ("complete", "mtls", "short", "preflight"):
            secure = mode == "mtls"
            token = "FixtureCampaignToken84"
            with server(
                model,
                backend,
                cap,
                plan["inputs"]["prompt_tokens"],
                paths=paths if secure else None,
                token=token if secure else None,
                short=mode == "short",
                preflight=mode == "preflight",
            ) as (url, calls):
                endpoints = tuple(
                    api.FleetEndpoint(f"member-{i}", url + f"/r{i}") for i in range(1, MEMBERS + 1)
                )
                connections = (
                    None
                    if not secure
                    else {
                        row.id: api.MonitorConnection(
                            row.url,
                            ca_bundle=paths["ca"],
                            client_cert=paths["client"],
                            client_key=paths["client_key"],
                            bearer_token=token,
                        )
                        for row in endpoints
                    }
                )
                if secure:
                    assert connections is not None
                    wrong = dict(connections)
                    wrong[endpoints[0].id] = api.MonitorConnection(
                        url.replace("127.0.0.1", "localhost"), ca_bundle=paths["ca"]
                    )
                    count = len(calls)
                    try:
                        asyncio.run(
                            api.replay_fleet_trace_campaign(
                                saved,
                                work,
                                endpoints,
                                routing,
                                executions=EXECUTIONS,
                                candidate_index=index,
                                connections=wrong,
                            )
                        )
                    except (api.PlanError, api.MonitorConnectionError):
                        pass
                    else:
                        raise AssertionError("wrong origin was admitted")
                    assert len(calls) == count
                    admission.append(
                        {"backend": backend, "wrong_origin_refused_before_contact": True}
                    )
                direct = asyncio.run(
                    api.replay_fleet_trace_campaign(
                        saved,
                        work,
                        endpoints,
                        routing,
                        executions=EXECUTIONS,
                        candidate_index=index,
                        concurrency=MEMBERS,
                        request_timeout=5,
                        trace_timeout=10,
                        campaign_timeout=CAMPAIGN_TIMEOUT,
                        connections=connections,
                    )
                )
                wanted = int(mode in {"short", "preflight"})
                args = [
                    "trace-fleet-campaign",
                    str(work),
                    "--from-plan",
                    str(saved),
                    "--routes",
                    str(routing),
                    "--candidate-index",
                    str(index),
                    "--executions",
                    str(EXECUTIONS),
                    "--concurrency",
                    str(MEMBERS),
                    "--request-timeout",
                    "5",
                    "--trace-timeout",
                    "10",
                    "--campaign-timeout",
                    str(CAMPAIGN_TIMEOUT),
                    "--json",
                ]
                for endpoint in endpoints:
                    args += ["--endpoint", endpoint.id + "=" + endpoint.url]
                    if secure:
                        for flag, flag_value in (
                            ("--ca-bundle", paths["ca"]),
                            ("--client-cert", paths["client"]),
                            ("--client-key", paths["client_key"]),
                            ("--bearer-env", "CF_CAMPAIGN_TOKEN84"),
                        ):
                            args += [flag, endpoint.id + "=" + str(flag_value)]
                cli_env = dict(env, CF_CAMPAIGN_TOKEN84=token)
                output = cwd / f"{backend}-{mode}.json"
                raw = run_raw([*args, "--out", str(output)], cwd, cli_env, wanted)
                assert raw == output.read_bytes() and b"\r\n" not in raw
                cli = json.loads(raw)
                for value in (direct._data, cli):
                    assert api.load_fleet_trace_campaign(value).to_dict() == value
                    assert value["exit_code"] == wanted and len(value["executions"]) == EXECUTIONS
                    assert value["manifest"]["population"]["original_replicas"] == MEMBERS
                    assert value["execution"]["completed"] == (
                        0 if mode == "preflight" else EXECUTIONS
                    )
                    for slot in value["executions"]:
                        child = slot["receipt"]
                        if child is None:
                            assert mode == "preflight" and slot["state"] == "not_started"
                            continue
                        assert (
                            child["cleanup"]["state"] == "completed"
                            and len(child["slots"]) == MEMBERS
                        )
                        assert child["native_trace"]["execution"]["planned"] == REQUESTS
                        assert [row["row_indices"] for row in child["slots"]] == [
                            [0, 3],
                            [1, 4],
                            [2, 5],
                        ]
                        if secure:
                            assert all(
                                member["serving_before"]["version"] == "controlled-protocol"
                                and member["serving_after"]["version"] == "controlled-protocol"
                                for member in child["slots"]
                            )
                    serialized = json.dumps(value)
                    assert "private-campaign-prompt" not in serialized
                    assert token not in serialized and "CF_CAMPAIGN_TOKEN84" not in serialized
                    assert all(
                        json.dumps(str(path.resolve())) not in serialized for path in paths.values()
                    )
                assert all(
                    row["authorized"] and (not secure or row["client_certificate"]) for row in calls
                )
                generated = sum(row["method"] == "POST" for row in calls)
                assert generated == (0 if mode == "preflight" else 2 * EXECUTIONS * REQUESTS)
                if secure:
                    for name in ("ca", "client", "client_key"):
                        prior_contacts = len(calls)
                        try:
                            direct.save(paths[name])
                        except api.PlanError:
                            pass
                        else:
                            raise AssertionError("TLS input overwrite accepted")
                        run_raw([*args, "--out", str(paths[name])], cwd, cli_env, 2)
                        assert (
                            len(calls) == prior_contacts
                            and paths[name].read_bytes() == held_tls[name]
                        )
                        aliases.append(
                            {
                                "backend": backend,
                                "role": name,
                                "api_refused": True,
                                "cli_exit": 2,
                                "unchanged_bytes": True,
                                "zero_added_contacts": True,
                            }
                        )
                controls.append(
                    {
                        "backend": backend,
                        "mode": mode,
                        "api_exit": direct.exit_code,
                        "cli_exit": wanted,
                        "K": EXECUTIONS,
                        "original_N": MEMBERS,
                        "M": REQUESTS,
                        "global_C": MEMBERS,
                        "completed_executions": cli["execution"]["completed"],
                        "generation_contacts": generated,
                        "raw_stdout_file_parity": True,
                        "owned_resources_closed": True,
                    }
                )
        assert all(path.read_bytes() == raw for path, raw in held.items())
    left = matching_campaign(saved, [0.1, 0.11])
    gates = [
        gate_control(cwd, env, left, matching_campaign(saved, durations), code, f"synthetic-{code}")
        for durations, code in (([0.105, 0.115], 0), ([0.2, 0.22], 1), ([0.105, 0.105], 3))
    ]
    assert saved.read_bytes() == held_source
    assert all(path.read_bytes() == held_tls[name] for name, path in paths.items())
    after = assert_installed_modules(checkout) if checkout else None
    return {
        "protocol_controls": controls,
        "synthetic_gate_controls": gates,
        "tls_alias_controls": aliases,
        "secure_admission": admission,
        "loaded_before": before,
        "loaded_after": after,
        "source_bytes_unchanged": True,
        "fixture_resources": "closed",
        "scope": (
            "CPU protocol fixtures and separately synthetic matching gates; "
            "no inference/GPU/cold/independence/performance qualification."
        ),
    }


def accept_native(
    cwd: Path,
    env: dict,
    source: Path,
    workload: Path,
    routes: Path,
    endpoints: tuple[Any, ...],
    index: int,
) -> dict:
    """Only the existing hosted native CPU job calls this with its owned daemons/store."""
    from chimeraforge import api
    from ci_cpu_fleet import CONCURRENCY, TOKEN_CAP, replay_controls

    held = {path: path.read_bytes() for path in (source, workload, routes)}
    direct = asyncio.run(
        api.replay_fleet_trace_campaign(
            source,
            workload,
            endpoints,
            routes,
            executions=EXECUTIONS,
            candidate_index=index,
            concurrency=CONCURRENCY,
            request_timeout=120,
            trace_timeout=180,
            campaign_timeout=600,
        )
    )
    args = [
        "trace-fleet-campaign",
        str(workload),
        "--from-plan",
        str(source),
        "--routes",
        str(routes),
        "--candidate-index",
        str(index),
        "--executions",
        str(EXECUTIONS),
        "--concurrency",
        str(CONCURRENCY),
        "--request-timeout",
        "120",
        "--trace-timeout",
        "180",
        "--campaign-timeout",
        "600",
        "--json",
    ]
    for endpoint in endpoints:
        args.extend(["--endpoint", endpoint.id + "=" + endpoint.url])
    output = cwd / "native-campaign.json"
    raw = run_raw([*args, "--out", str(output)], cwd, env, 1)
    assert raw == output.read_bytes()
    cli = json.loads(raw)
    interfaces = []
    for name, report in (("api", direct._data), ("cli", cli)):
        assert api.load_fleet_trace_campaign(report).to_dict() == report
        assert report["state"] == "completed" and report["execution"]["completed"] == EXECUTIONS
        assert report["exit_code"] == 1 and report["configuration_status"] == "mismatch"
        checks = []
        for slot in report["executions"]:
            child = slot["receipt"]
            assert slot["execution_complete"] is True and child["status"] == "completed"
            assert child["native_trace"]["execution"]["completed"] == REQUESTS
            assert child["exit_code"] == 1 and child["configuration_status"] == "mismatch"
            assert child["plan"]["snapshot"] == json.loads(held[source])
            assert child["cleanup"]["state"] == "completed"
            assert [member["row_indices"] for member in child["slots"]] == [[0, 3], [1, 4], [2, 5]]
            assert all(
                member["serving_after"]["device"] == "cpu"
                and member["serving_after"]["loaded_gpu_bytes"] == 0
                for member in child["slots"]
            )
            check = replay_controls(child)
            assert all(
                0 < row["native"]["tokens_generated"] <= TOKEN_CAP
                and row["output_cap_state"] == "within_cap"
                for row in child["native_trace"]["requests"]
            )
            checks.append(check)
        interfaces.append({"interface": name, "report": report, "generation_controls": checks})
    gate = gate_control(cwd, env, direct._data, cli, 3, "native-cpu-campaign")
    assert all(path.read_bytes() == data for path, data in held.items())
    return {
        "interfaces": interfaces,
        "gate": gate,
        "protocol_invocations": 2,
        "executions_per_invocation": EXECUTIONS,
        "requests_per_execution": REQUESTS,
        "actual_export_bytes": {"api": len(direct.json_bytes()), "cli": len(raw)},
        "source_workload_routes_bytes_unchanged": True,
        "scope": (
            "Actual CPU native K2 campaigns; modeled GPU mismatch retained, "
            "no GPU/cold/independence/performance qualification."
        ),
    }


def main() -> int:
    import argparse
    import tempfile
    from chimeraforge import api

    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-fleet-campaign-") as temporary:
        cwd = Path(temporary)
        source = cwd / "plan.json"
        api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                latency_slo=10000,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        ).save(source)
        result = accept(cwd, dict(os.environ), source)
    root = Path(__file__).resolve().parents[1]
    names = [
        "scripts/ci_fleet_trace_campaign.py",
        "scripts/ci_cpu_fleet.py",
        "scripts/ci_installed_acceptance.py",
        "src/chimeraforge/api.py",
        "src/chimeraforge/cli.py",
        "src/chimeraforge/bench/fleet_campaign.py",
        "src/chimeraforge/bench/fleet_campaign_types.py",
        "src/chimeraforge/bench/fleet_campaign_receipt.py",
        "src/chimeraforge/bench/fleet_campaign_gate.py",
        "src/chimeraforge/bench/fleet_campaign_output.py",
        "src/chimeraforge/bench/fleet_trace_receipt.py",
        "src/chimeraforge/bench/fleet_trace_gate.py",
        "src/chimeraforge/commands/trace_fleet_campaign.py",
        "src/chimeraforge/commands/gate.py",
    ]
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_profile": "editable source, not installed proof",
        "method": (
            "actual owned CPU HTTPS API/CLI protocols; separately synthetic native matching gates"
        ),
        "source_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names
        },
        "result": result,
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
