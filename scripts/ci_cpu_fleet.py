"""Early hosted feasibility for three native CPU Ollama members, not fleet performance.

The pinned v0.35.1 api/types.go defines the native version, digest and generation
fields. The initialized ordinary shared store follows native OLLAMA_MODELS and
NOPRUNE semantics; this does not establish read-only or general multiwriter safety.
"""

from __future__ import annotations

import argparse
import asyncio
import errno
import hashlib
import json
import math
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import psutil

from ci_cpu_runtime_observation import cpu_server_environment, read_runtime_observation
from ci_cpu_serving import (
    MODEL_NAME,
    MODEL_REVISION,
    MODEL_SHA256,
    MODEL_URL,
    OLLAMA_SHA256,
    OLLAMA_URL,
    OLLAMA_VERSION,
    OPERATION_TIMEOUT_SECONDS,
    download,
    verify_sha256,
    wait_until_ready,
)
from ci_installed_acceptance import assert_installed_origin, run_cli

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
FEATURE_BASE = "0b94ad236cc705998627d59619ec7ed63f7b7de6"


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


async def _generate(
    urls: list[str], workload: list[dict], saved: dict, candidate_index: int, evidence: dict
) -> None:
    from chimeraforge.bench.backends.ollama import OllamaBackend
    from chimeraforge.bench.serving import observe_backend
    from chimeraforge.bench.serving_binding import serving_binding

    semaphore = asyncio.Semaphore(CONCURRENCY)
    active = peak = 0
    clients, owned = [], []
    backends = [OllamaBackend(base_url=url) for url in urls]
    evidence.update(
        {
            "global_concurrency": CONCURRENCY,
            "rows": [
                {
                    "request_id": row["request_id"],
                    "endpoint_id": f"replica-{i % MEMBERS + 1}",
                    "state": "not_started",
                }
                for i, row in enumerate(workload)
            ],
        }
    )
    failure = None

    async def observe() -> list[dict]:
        tasks = [asyncio.create_task(observe_backend(backend, MODEL_NAME)) for backend in backends]
        owned.extend(tasks)
        return await asyncio.gather(*tasks)

    async def request(index: int) -> None:
        nonlocal active, peak
        member = index % MEMBERS
        row = evidence["rows"][index]
        async with semaphore:
            active += 1
            peak = max(peak, active)
            row["state"] = "attempted"
            try:
                response = await clients[member].post(
                    "/api/generate",
                    json={
                        "model": MODEL_NAME,
                        "prompt": workload[index]["prompt"],
                        "stream": False,
                        "options": {
                            "num_gpu": 0,
                            "num_thread": THREADS,
                            "num_ctx": CONTEXT,
                            "num_predict": TOKEN_CAP,
                            "seed": SEED,
                            "temperature": 0,
                        },
                    },
                )
                response.raise_for_status()
                value = response.json()
                assert value["done"] is True and 0 < value["eval_count"] <= TOKEN_CAP
                assert value["eval_duration"] > 0
                row.update(
                    {
                        "state": "completed",
                        "tokens": value["eval_count"],
                        "eval_duration_ns": value["eval_duration"],
                    }
                )
            except BaseException as exc:
                row.update(
                    {
                        "state": "cancelled"
                        if isinstance(exc, asyncio.CancelledError)
                        else "failed",
                        "error_class": type(exc).__name__,
                    }
                )
                raise
            finally:
                active -= 1

    try:
        for url in urls:
            clients.append(httpx.AsyncClient(base_url=url, timeout=120, trust_env=False))
        evidence["serving_before"] = await observe()
        tasks = [asyncio.create_task(request(i)) for i in range(REQUESTS)]
        owned.extend(tasks)
        await asyncio.gather(*tasks)
        evidence["serving_after"] = await observe()
        evidence["native_endpoint_bindings"] = [
            serving_binding(saved, saved["result"]["candidates"][candidate_index], left, right)
            for left, right in zip(evidence["serving_before"], evidence["serving_after"])
        ]
        assert all(
            value["hardware"]["state"] == "mismatch"
            for value in evidence["native_endpoint_bindings"]
        ), evidence["native_endpoint_bindings"]
        evidence["binding_scope"] = (
            "existing endpoint_topology; no N3 rewrite/declared_member feature yet"
        )
        evidence["known_cpu_vs_modeled_gpu_mismatch_retained"] = True
        assert peak == CONCURRENCY
    except BaseException as exc:
        failure = exc
        evidence["primary_error_class"] = type(exc).__name__
    finally:
        for task in owned:
            if not task.done():
                task.cancel()
        await asyncio.gather(*owned, return_exceptions=True)
        outcomes = await asyncio.gather(
            *(client.aclose() for client in clients),
            *(backend.close() for backend in backends),
            return_exceptions=True,
        )
        errors = [type(value).__name__ for value in outcomes if isinstance(value, BaseException)]
        evidence.update(
            {
                "peak": peak,
                "active_after_join": active,
                "clients_closed": all(client.is_closed for client in clients),
                "tasks_joined": all(task.done() for task in owned),
                "close_errors": errors,
            }
        )
        if errors:
            failure = failure or RuntimeError("native async clients failed to close")
    if failure is not None:
        raise failure


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--expect-version", required=True)
    args = parser.parse_args(argv)
    assert sys.platform == "linux" and platform.machine() == "x86_64"
    import chimeraforge

    assert_installed_origin(chimeraforge.__file__, args.checkout)
    assert chimeraforge.__version__ == args.expect_version
    delta = subprocess.check_output(
        ["git", "diff", "--name-only", FEATURE_BASE, "HEAD"], cwd=args.checkout, text=True
    ).splitlines()
    assert set(delta) == {
        "scripts/ci_cpu_fleet.py",
        ".github/workflows/cf079-native-feasibility.yml",
    }
    receipt = {
        "kind": "native-three-member-feasibility",
        "version": args.expect_version,
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.checkout, text=True
        ).strip(),
        "scope": "CPU protocol feasibility only; no implemented fleet replay or GPU/capacity proof",
        "asset": {
            "runtime": OLLAMA_VERSION,
            "runtime_sha256": OLLAMA_SHA256,
            "model_revision": MODEL_REVISION,
            "model_sha256": MODEL_SHA256,
        },
    }
    with tempfile.TemporaryDirectory(prefix="cf079-native-") as temporary:
        work = Path(temporary)
        runtime = work / "runtime"
        runtime.mkdir()
        archive, model = work / "runtime.tar.zst", work / "model.gguf"
        download(OLLAMA_URL, archive, OLLAMA_SHA256)
        download(MODEL_URL, model, MODEL_SHA256)
        subprocess.run(
            ["tar", "--zstd", "-xf", str(archive), "-C", str(runtime)],
            check=True,
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
        archive.unlink()
        binary, store = runtime / "bin/ollama", work / "models"
        modelfile = work / "Modelfile"
        modelfile.write_text(
            f"FROM {model}\nPARAMETER num_gpu 0\nPARAMETER num_thread {THREADS}\n"
            f"PARAMETER num_ctx {CONTEXT}\nPARAMETER num_predict {TOKEN_CAP}\n"
            f"PARAMETER seed {SEED}\nPARAMETER temperature 0\n",
            encoding="utf-8",
        )
        servers, clients, logs, ports, environments = [], [], [], [], []
        failure = None
        try:
            for index in range(MEMBERS):
                with socket.socket() as available:
                    available.bind(("127.0.0.1", 0))
                    port = available.getsockname()[1]
                assert port not in ports
                home = work / f"member-{index + 1}"
                home.mkdir()
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                env.update(
                    {
                        "HOME": str(home),
                        "OLLAMA_HOST": f"127.0.0.1:{port}",
                        "OLLAMA_MODELS": str(store),
                        "OLLAMA_NOPRUNE": "1",
                        "OLLAMA_NO_CLOUD": "1",
                        "OLLAMA_NUM_PARALLEL": "1",
                        "OLLAMA_MAX_LOADED_MODELS": "1",
                        "CHIMERAFORGE_CACHE": str(home / "cache"),
                        "NO_COLOR": "1",
                    }
                )
                env = cpu_server_environment(env)
                log = (work / f"server-{index + 1}.log").open("w", encoding="utf-8")
                logs.append(log)
                server = subprocess.Popen(
                    [str(binary), "serve"],
                    env=env,
                    cwd=work,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                servers.append(server)
                ports.append(port)
                client = httpx.Client(
                    base_url=f"http://127.0.0.1:{port}", timeout=120, trust_env=False
                )
                clients.append(client)
                environments.append(env)
                wait_until_ready(client, server)
                if index == 0:
                    subprocess.run(
                        [str(binary), "create", MODEL_NAME, "-f", str(modelfile)],
                        env=env,
                        cwd=work,
                        check=True,
                        capture_output=True,
                        timeout=180,
                    )
                shown = client.post("/api/show", json={"model": MODEL_NAME})
                shown.raise_for_status()
                assert shown.json()["model_info"]
            assert len(set(server.pid for server in servers)) == MEMBERS
            versions = [
                client.get("/api/version").raise_for_status().json()["version"]
                for client in clients
            ]
            assert versions == [OLLAMA_VERSION] * MEMBERS
            identity = _store_identity(store)
            tags = [
                client.get("/api/tags").raise_for_status().json()["models"] for client in clients
            ]
            digests = [
                next(row["digest"] for row in rows if row["name"] == MODEL_NAME) for rows in tags
            ]
            assert digests == [identity["manifest_sha256"]] * MEMBERS
            urls = [str(client.base_url) for client in clients]
            source, candidate_index, planned = original_plan(work, environments[0], urls[0])
            original = source.read_bytes()
            workload = [
                {
                    "request_id": f"probe-{i + 1}",
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
            workload_source, routes_source = work / "workload.json", work / "routes.json"
            workload_raw, routes_raw = json.dumps(workload).encode(), json.dumps(routes).encode()
            workload_source.write_bytes(workload_raw)
            routes_source.write_bytes(routes_raw)
            receipt.update(
                {
                    "declared_members": MEMBERS,
                    "ports": ports,
                    "processes": [
                        {
                            "pid": server.pid,
                            "create_time": psutil.Process(server.pid).create_time(),
                            "pgid": os.getpgid(server.pid),
                        }
                        for server in servers
                    ],
                    "versions": versions,
                    "store": identity,
                    "native_model_digests": digests,
                    "original_plan": planned,
                    "candidate_index": candidate_index,
                    "source_sha256": hashlib.sha256(original).hexdigest(),
                    "workload_sha256": hashlib.sha256(workload_raw).hexdigest(),
                    "routes_sha256": hashlib.sha256(routes_raw).hexdigest(),
                    "routes": routes,
                    "generation": {},
                }
            )
            asyncio.run(
                _generate(
                    urls, workload, json.loads(original), candidate_index, receipt["generation"]
                )
            )
            receipt["cpu_observations"] = []
            for index, (client, log) in enumerate(zip(clients, logs)):
                error, running = None, None
                try:
                    running = client.get("/api/ps").raise_for_status().json()["models"]
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    error = type(exc).__name__
                log.flush()
                observation = read_runtime_observation(work / f"server-{index + 1}.log")
                receipt["cpu_observations"].append(
                    {"loaded": running, "startup": observation, "error_class": error}
                )
            assert source.read_bytes() == original and _store_identity(store) == identity
            assert (
                workload_source.read_bytes() == workload_raw
                and routes_source.read_bytes() == routes_raw
            )
            receipt["source_unchanged"] = True
            receipt["post_generation_integrity"] = {
                "plan": True,
                "workload": True,
                "routes": True,
                "referenced_store": True,
            }
            for value in receipt["cpu_observations"]:
                value["criterion"] = observed_cpu_controls(value)
            receipt["result"] = "NATIVE_THREE_MEMBER_FEASIBLE"
        except BaseException as exc:
            receipt["result"] = "FAILED"
            receipt["error_class"] = type(exc).__name__
            failure = exc
        finally:
            close_errors = []
            for client in clients:
                try:
                    client.close()
                except Exception as exc:
                    close_errors.append(type(exc).__name__)
            try:
                receipt["cleanup"] = close_groups(servers, ports)
                if receipt["cleanup"]["state"] != "completed":
                    failure = failure or RuntimeError("native owned cleanup incomplete")
            except BaseException as exc:
                receipt["cleanup"] = {"state": "failed", "error_class": type(exc).__name__}
                failure = failure or exc
            finally:
                receipt["client_close_errors"] = close_errors
                receipt["daemon_observations"] = [
                    read_runtime_observation(work / f"server-{i + 1}.log") for i in range(len(logs))
                ]
                for log in logs:
                    log.close()
                if close_errors:
                    failure = failure or RuntimeError("native clients failed to close")
                if failure is not None:
                    receipt["result"] = "FAILED"
                print(json.dumps(receipt, indent=2), flush=True)
        if failure is not None:
            raise failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
