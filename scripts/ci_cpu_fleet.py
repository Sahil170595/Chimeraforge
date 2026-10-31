"""Installed original-fleet replay on three owned native CPU Ollama members.

The pinned v0.35.1 api/types.go defines the native version, digest and generation
fields. The initialized ordinary shared store follows native OLLAMA_MODELS and
NOPRUNE semantics; this does not establish read-only or general multiwriter safety.
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import json
import math
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import httpx
import psutil

from ci_cpu_runtime_observation import cpu_server_environment, read_runtime_observation
from ci_cpu_serving import (
    MODEL_NAME,
    MODEL_REVISION,
    MODEL_SHA256,
    OLLAMA_SHA256,
    OLLAMA_VERSION,
    verify_sha256,
    wait_until_ready,
)
from ci_installed_acceptance import run_cli

MEMBERS = 3
REQUESTS = 6
CONCURRENCY = 3
TOKEN_CAP = 4
CONTEXT = 1024
THREADS = 2
SEED = 42
LATENCY_BOUND_MS = 1_000_000
BASELINE_RATE = 0.000001
FLEET_CAPACITY_FACTOR = 2.2
MAX_PLANNER_RATE = 100_000
GROUP_GRACE_SECONDS = 10
GROUP_KILL_SECONDS = 10
GROUP_POLL_SECONDS = 0.05


def _group_members(group: int) -> list[int]:
    members = []
    for process in psutil.process_iter(["pid", "status"]):
        try:
            if os.getpgid(process.pid) == group and process.status() != psutil.STATUS_ZOMBIE:
                members.append(process.pid)
        except (ProcessLookupError, psutil.NoSuchProcess):
            continue
    return members


def close_groups(servers: list[subprocess.Popen], ports: list[int]) -> dict:
    """Attempt every owned group's termination despite inspection or signal errors."""
    groups = [server.pid for server in servers]
    absent, escalated = [], []
    errors: dict[str, str] = {}

    def inspect(group: int) -> list[int] | None:
        try:
            return _group_members(group)
        except (OSError, psutil.Error) as exc:
            errors[f"inspect:{group}"] = type(exc).__name__
            return None

    def terminate(group: int, value: signal.Signals) -> None:
        try:
            os.killpg(group, value)
        except ProcessLookupError:
            absent.append(group)
        except OSError as exc:
            errors[f"signal:{group}:{value.name}"] = type(exc).__name__

    # Inspection uncertainty cannot prevent signaling any recorded owned group.
    observed = {str(group): inspect(group) for group in groups}
    for group in groups:
        terminate(group, signal.SIGTERM)
    deadline = time.monotonic() + GROUP_GRACE_SECONDS
    while any(inspect(group) != [] for group in groups) and time.monotonic() < deadline:
        time.sleep(GROUP_POLL_SECONDS)
    for group in groups:
        if inspect(group) != []:
            escalated.append(group)
            terminate(group, signal.SIGKILL)
    deadline = time.monotonic() + GROUP_KILL_SECONDS
    for server in servers:
        try:
            server.wait(timeout=max(0.001, deadline - time.monotonic()))
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors[f"reap:{server.pid}"] = type(exc).__name__
    while any(inspect(group) != [] for group in groups) and time.monotonic() < deadline:
        time.sleep(GROUP_POLL_SECONDS)
    remaining = {str(group): inspect(group) for group in groups}
    listeners = []
    for port in ports:
        try:
            with socket.socket() as connection:
                connection.settimeout(1)
                result = connection.connect_ex(("127.0.0.1", port))
                if result == 0:
                    listeners.append(port)
                elif result != errno.ECONNREFUSED:
                    errors[f"listener:{port}"] = f"connect_ex:{result}"
        except OSError as exc:
            errors[f"listener:{port}"] = type(exc).__name__
    return {
        "state": "completed"
        if not (errors or any(value != [] for value in remaining.values()) or listeners)
        else "incomplete",
        "owned_groups": groups,
        "observed_members_at_cleanup": observed,
        "absent_at_signal": absent,
        "escalated": escalated,
        "live_members": remaining,
        "listeners": listeners,
        "errors": errors,
        "leaders_reaped": all(server.poll() is not None for server in servers),
    }


def _store_identity(store: Path) -> dict:
    """Read native manifests and hash every admitted referenced blob, not cache files."""
    manifests = sorted((store / "manifests").rglob("*"))
    manifests = [path for path in manifests if path.is_file()]
    assert len(manifests) == 1, "expected one initialized native model manifest"
    raw = manifests[0].read_bytes()
    manifest = json.loads(raw)
    refs = [manifest["config"], *manifest["layers"]]
    blobs = {}
    for ref in refs:
        digest = ref["digest"]
        assert digest.startswith("sha256:") and len(digest) == len("sha256:") + 64
        path = store / "blobs" / digest.replace(":", "-")
        actual = digest.split(":", 1)[1]
        verify_sha256(path, actual)
        assert path.stat().st_size == ref["size"]
        blobs[digest] = {"sha256": actual, "bytes": path.stat().st_size}
    assert MODEL_SHA256 in {row["sha256"] for row in blobs.values()}
    return {"manifest_sha256": hashlib.sha256(raw).hexdigest(), "blobs": blobs}


def original_plan(work: Path, env: dict, url: str) -> tuple[Path, int, dict]:
    """Run two genuine native plans; never manufacture an N3 candidate from N1."""
    common = [
        "plan",
        "--model",
        f"ollama:{MODEL_NAME}",
        "--ollama-url",
        url,
        "--hardware",
        "RTX 4080 12GB",
        "--budget",
        "100000",
        "--quality-target",
        "0",
        "--context-length",
        str(CONTEXT),
        "--prompt-tokens",
        "8",
        "--avg-tokens",
        str(TOKEN_CAP),
        "--latency-slo",
        str(LATENCY_BOUND_MS),
        "--json",
    ]
    baseline = work / "original-n1.json"
    run_cli([*common, "--request-rate", str(BASELINE_RATE), "--save", str(baseline)], work, env)
    saved = json.loads(baseline.read_bytes())
    row = next(
        row
        for row in saved["result"]["candidates"]
        if row["backend"] == "ollama" and row["quant"] == "Q4_K_M"
    )
    assert row["n_agents"] == 1 and row["p95_latency_ms"] > 0, row
    rate = FLEET_CAPACITY_FACTOR * 1000 / row["p95_latency_ms"]
    assert math.isfinite(rate) and 0 < rate <= MAX_PLANNER_RATE
    source = work / "original-n3.json"
    run_cli([*common, "--request-rate", str(rate), "--save", str(source)], work, env)
    saved = json.loads(source.read_bytes())
    index = next(
        i
        for i, candidate in enumerate(saved["result"]["candidates"])
        if candidate["backend"] == "ollama" and candidate["quant"] == "Q4_K_M"
    )
    chosen = saved["result"]["candidates"][index]
    assert chosen["n_agents"] == MEMBERS, {"chosen": chosen, "derived_rate": rate}
    assert chosen["tensor_parallel"] == chosen["pipeline_parallel"] == 1
    assert chosen["decode_tokens_per_req"] == TOKEN_CAP
    return (
        source,
        index,
        {
            "candidate": chosen,
            "derived_request_rate": rate,
            "basis": "2.2 times low-rate native N1 p95-derived capacity",
            "fingerprint": saved["fingerprint"],
        },
    )


def observed_cpu_controls(value: dict) -> dict:
    """Check native protocol facts while preserving absent offload evidence."""
    assert value.get("error_class") is None
    running, observation = value["loaded"], value["startup"]
    assert running and all(
        type(row["size_vram"]) is int and row["size_vram"] == 0 for row in running
    )
    assert observation["log_state"] == "read"
    assert not any(
        observation[name]
        for name in (
            "log_truncated",
            "decode_errors",
            "partial_line",
            "overlong_lines",
            "record_limit_exceeded",
            "unbound_startup_lines",
        )
    )
    assert observation["records"]
    for row in observation["records"]:
        assert row["ngl_state"] == "known" and row["ngl"] == 0 and row["model_loaded"] is True
        assert row["buffer_bytes"]["cpu"] > 0 and row["buffer_bytes"]["gpu"] == 0
        assert row["buffer_bytes"]["amx"] == 0
        assert not (
            row["unknown_startup_lines"]
            or row["invalid_startup_lines"]
            or row["buffer_limit_exceeded"]
        )
        if row["offload_state"] == "missing":
            assert row["offloaded_layers"] is None and row["total_layers"] is None
        else:
            assert row["offload_state"] == "known" and row["offloaded_layers"] == 0
    return {
        "criterion": "observed_cpu_protocol_controls",
        "physical_placement": "unverified",
        "offload_log_states": [row["offload_state"] for row in observation["records"]],
    }


def replay_controls(report: dict) -> dict:
    """Derive observed client-interval occupancy; never infer server/GPU capacity."""
    rows = report["native_trace"]["requests"]
    assert len(rows) == REQUESTS
    events = []
    for row in rows:
        count = row["native"]["tokens_generated"]
        assert row["state"] == "completed" and type(count) is int and 0 < count <= TOKEN_CAP
        assert row["output_cap_state"] == "within_cap"
        start, end = row["times"]["start_s"], row["times"]["terminal_s"]
        assert type(start) in (int, float) and type(end) in (int, float)
        assert math.isfinite(start) and math.isfinite(end) and 0 <= start < end
        events.extend(((start, 1), (end, -1)))
    active = peak = 0
    for _, change in sorted(events):
        active += change
        assert active >= 0
        peak = max(peak, active)
    assert active == 0 and 0 < peak <= CONCURRENCY
    return {
        "positive_within_cap_rows": len(rows),
        "peak_client_generation_intervals": peak,
        "concurrency_limit": CONCURRENCY,
        "physical_server_inflight": "unverified",
    }


def accept(work: Path, binary: Path, store: Path, parent_env: dict) -> dict:
    """Reuse initialized native assets/import once; own three new CPU process groups."""
    from chimeraforge import api

    directory = work / "fleet-native"
    directory.mkdir()
    receipt = {
        "kind": "installed-original-fleet-native",
        "scope": (
            "real CPU protocol and original-plan integration; no GPU, physical independence, "
            "speed, SLO or capacity qualification"
        ),
        "asset": {
            "runtime": OLLAMA_VERSION,
            "runtime_sha256": OLLAMA_SHA256,
            "model_revision": MODEL_REVISION,
            "model_sha256": MODEL_SHA256,
        },
    }
    servers, clients, logs, ports, environments = [], [], [], [], []
    failure = None
    try:
        identity = _store_identity(store)
        for index in range(MEMBERS):
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            assert port not in ports
            home = directory / f"member-{index + 1}"
            home.mkdir()
            env = dict(
                parent_env,
                HOME=str(home),
                OLLAMA_HOST=f"127.0.0.1:{port}",
                OLLAMA_MODELS=str(store),
                OLLAMA_NOPRUNE="1",
                OLLAMA_NO_CLOUD="1",
                OLLAMA_NUM_PARALLEL="1",
                OLLAMA_MAX_LOADED_MODELS="1",
                CHIMERAFORGE_CACHE=str(home / "cache"),
                NO_COLOR="1",
            )
            env = cpu_server_environment(env)
            log = (directory / f"server-{index + 1}.log").open("w", encoding="utf-8")
            logs.append(log)
            server = subprocess.Popen(
                [str(binary), "serve"],
                env=env,
                cwd=directory,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            servers.append(server)
            ports.append(port)
            client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120, trust_env=False)
            clients.append(client)
            environments.append(env)
            wait_until_ready(client, server)
            shown = client.post("/api/show", json={"model": MODEL_NAME})
            shown.raise_for_status()
            assert shown.json()["model_info"]
        versions = [
            client.get("/api/version").raise_for_status().json()["version"] for client in clients
        ]
        assert versions == [OLLAMA_VERSION] * MEMBERS
        digests = [
            next(
                row["digest"]
                for row in client.get("/api/tags").raise_for_status().json()["models"]
                if row["name"] == MODEL_NAME
            )
            for client in clients
        ]
        assert digests == [identity["manifest_sha256"]] * MEMBERS
        urls = [str(client.base_url) for client in clients]
        source, index, planned = original_plan(directory, environments[0], urls[0])
        workload = [
            {
                "request_id": f"native-{i}",
                "prompt": "List two primary colors.",
                "max_output_tokens": TOKEN_CAP,
                "arrival_offset_s": 0,
            }
            for i in range(REQUESTS)
        ]
        routes = [
            {"request_id": row["request_id"], "endpoint_id": f"replica-{i % MEMBERS + 1}"}
            for i, row in enumerate(workload)
        ]
        request_path, route_path = directory / "workload.json", directory / "routes.json"
        request_path.write_text(json.dumps(workload), encoding="utf-8")
        route_path.write_text(json.dumps(routes), encoding="utf-8")
        held = {path: path.read_bytes() for path in (source, request_path, route_path)}
        endpoints = tuple(api.FleetEndpoint(f"replica-{i + 1}", url) for i, url in enumerate(urls))
        receipt.update(
            {
                "versions": versions,
                "original_plan": planned,
                "store": identity,
                "native_model_digests": digests,
                "ports": ports,
                "processes": [
                    {
                        "pid": server.pid,
                        "create_time": psutil.Process(server.pid).create_time(),
                        "pgid": os.getpgid(server.pid),
                    }
                    for server in servers
                ],
                "source_sha256": hashlib.sha256(held[source]).hexdigest(),
                "workload_sha256": hashlib.sha256(held[request_path]).hexdigest(),
                "routes_sha256": hashlib.sha256(held[route_path]).hexdigest(),
                "interfaces": [],
            }
        )
        direct = asyncio.run(
            api.replay_fleet_trace(
                source,
                request_path,
                endpoints,
                route_path,
                candidate_index=index,
                concurrency=CONCURRENCY,
                request_timeout=120,
                trace_timeout=180,
            )
        ).to_dict()
        receipt["interfaces"].append({"interface": "api", "report": direct})
        args = [
            "trace-fleet",
            str(request_path),
            "--from-plan",
            str(source),
            "--routes",
            str(route_path),
            "--candidate-index",
            str(index),
            "--concurrency",
            str(CONCURRENCY),
            "--request-timeout",
            "120",
            "--trace-timeout",
            "180",
            "--json",
        ]
        for endpoint in endpoints:
            args += ["--endpoint", f"{endpoint.id}={endpoint.url}"]
        cli = json.loads(run_cli(args, directory, environments[0], 1))
        receipt["interfaces"].append({"interface": "cli", "report": cli})
        for interface in receipt["interfaces"]:
            report = interface["report"]
            interface["generation_controls"] = replay_controls(report)
            assert api.load_fleet_trace(report).to_dict() == report
            assert report["native_trace"]["execution"]["completed"] == REQUESTS
            assert report["native_trace"]["execution"]["concurrency"] == CONCURRENCY
            assert report["plan"]["snapshot"] == json.loads(held[source])
            assert report["plan"]["snapshot"]["result"]["candidates"][index]["n_agents"] == MEMBERS
            assert [row["row_indices"] for row in report["slots"]] == [[0, 3], [1, 4], [2, 5]]
            assert report["exit_code"] == 1 and report["configuration_status"] == "mismatch"
            assert report["cleanup"]["state"] == "completed"
            assert all(
                slot["binding"]["summary"]["hardware"]["state"] == "mismatch"
                for slot in report["slots"]
            )
            assert all(
                slot["serving_after"]["device"] == "cpu"
                and slot["serving_after"]["loaded_gpu_bytes"] == 0
                for slot in report["slots"]
            )
        receipt["cpu_observations"] = []
        from ci_fleet_trace_gate import accept_native as accept_native_gate

        receipt["fleet_trace_gate"] = accept_native_gate(directory, environments[0], direct, cli)
        from ci_fleet_trace_campaign import accept_native as accept_native_campaign

        receipt["fleet_trace_campaign"] = accept_native_campaign(
            directory, environments[0], source, request_path, route_path, endpoints, index
        )
        for index, (client, log) in enumerate(zip(clients, logs)):
            error, loaded = None, None
            try:
                loaded = client.get("/api/ps").raise_for_status().json()["models"]
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                error = type(exc).__name__
            log.flush()
            receipt["cpu_observations"].append(
                {
                    "loaded": loaded,
                    "error_class": error,
                    "startup": read_runtime_observation(directory / f"server-{index + 1}.log"),
                }
            )
        assert all(path.read_bytes() == raw for path, raw in held.items())
        assert _store_identity(store) == identity
        receipt["post_generation_integrity"] = {
            "plan": True,
            "workload": True,
            "routes": True,
            "referenced_store": True,
        }
        for value in receipt["cpu_observations"]:
            value["criterion"] = observed_cpu_controls(value)
        receipt["result"] = "INSTALLED_ORIGINAL_FLEET_CPU_INTEGRATION"
    except BaseException as exc:
        receipt["result"], receipt["error_class"] = "FAILED", type(exc).__name__
        failure = exc
    finally:
        errors = []
        for client in clients:
            try:
                client.close()
            except Exception as exc:
                errors.append(type(exc).__name__)
        try:
            receipt["cleanup"] = close_groups(servers, ports)
            if receipt["cleanup"]["state"] != "completed":
                failure = failure or RuntimeError("native owned cleanup incomplete")
        except BaseException as exc:
            receipt["cleanup"] = {"state": "failed", "error_class": type(exc).__name__}
            failure = failure or exc
        finally:
            receipt["client_close_errors"] = errors
            for log in logs:
                log.close()
            if errors:
                failure = failure or RuntimeError("native clients failed to close")
            if failure is not None:
                receipt["result"] = "FAILED"
            print(json.dumps({"original_fleet_native": receipt}, indent=2), flush=True)
    if failure is not None:
        raise failure
    return receipt
