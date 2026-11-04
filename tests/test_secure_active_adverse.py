"""Adverse native TLS/authentication and precontact admission controls."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.runner import run_benchmark
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.cli import app
from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
from test_ci_acceptance import load_script
from test_secure_active import active_plan as active_plan
from test_secure_monitor import certs as certs


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize(
    "fault",
    ["wrong-ca", "wrong-host", "wrong-token", "missing-client", "redirect", "malformed-sse"],
)
async def test_real_native_secure_failure_and_owned_cleanup(
    certs, backend, fault, monkeypatch, caplog
):
    wire = load_script("ci_secure_active")
    clients = []
    native_init = httpx.AsyncClient.__init__

    def observed(client, *args, **kwargs):
        native_init(client, *args, **kwargs)
        clients.append(client)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", observed)
    caplog.set_level(logging.DEBUG)
    token = "FictionalFailure82"
    with wire.server(certs, backend=backend) as (other_url, other_calls):
        with wire.server(
            certs,
            backend=backend,
            token=token,
            wrong_host=fault == "wrong-host",
            mtls=fault == "missing-client",
            redirect=other_url if fault == "redirect" else None,
            malformed=fault == "malformed-sse",
            echo=token,
        ) as (url, calls):
            connection = MonitorConnection(
                url,
                ca_bundle=certs["wrong_ca"] if fault == "wrong-ca" else certs["ca"],
                bearer_token="wrong" if fault == "wrong-token" else token,
            )
            report = await api.replay_trace(
                [TraceRequest("one", "fixture", 4, 0)],
                model=wire.MODEL,
                backend=backend,
                base_url=url,
                connection=connection,
            )
            data = report.to_dict()
            assert data["exit_code"] == 1 and data["execution"]["completed"] == 0, data
            assert other_calls == [], "redirects cannot contact a second origin"
            if fault != "malformed-sse":
                assert not any(row["method"] == "POST" for row in calls)
            else:
                assert any(row["method"] == "POST" for row in calls)
            assert token not in json.dumps(data) + caplog.text
            assert clients and all(client.is_closed for client in clients)
            assert all(client._transport._pool.connections == [] for client in clients)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_secure_active_ignores_opted_proxy_ca_and_keylog_environment(
    certs, tmp_path, backend, monkeypatch
):
    wire = load_script("ci_secure_active")
    monitor = load_script("ci_secure_monitor")
    keylog = tmp_path / "FictionalKeylog82"
    with monitor.proxy_sentinel() as (proxy, contacts):
        values = {
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "ALL_PROXY": proxy,
            "NO_PROXY": "",
            "SSL_CERT_FILE": str(tmp_path / "missing.pem"),
            "SSL_CERT_DIR": str(tmp_path / "missing"),
            "SSLKEYLOGFILE": str(keylog),
        }
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        with wire.server(certs, backend=backend) as (url, calls):
            connection = MonitorConnection(url, ca_bundle=certs["ca"])
            result = await run_benchmark(
                wire.MODEL,
                backend,
                runs=1,
                options={"max_tokens": 4},
                base_url=url,
                connection=connection,
            )
            assert result.aggregate.count == 1
            assert calls and all(row["authorized"] for row in calls)
        assert contacts == [] and not keylog.exists()
        import os

        assert {name: os.environ[name] for name in values} == values


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,invalid",
    [
        (mode, invalid)
        for mode in ("trace", "saved-trace", "saved-bench")
        for invalid in ("type", "origin", "ollama", "tgi")
        if (mode, invalid) != ("saved-trace", "tgi")
    ],
)
async def test_all_public_secure_admission_refuses_before_contact(
    active_plan, certs, mode, invalid
):
    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    rows = [TraceRequest("one", "fixture", 4, 0)]
    with wire.server(certs, backend="vllm") as (url, calls):
        connection = MonitorConnection(
            "https://example.test" if invalid == "origin" else url, ca_bundle=certs["ca"]
        )
        options = {"base_url": url, "connection": object() if invalid == "type" else connection}
        if invalid in {"ollama", "tgi"}:
            options["backend"] = invalid
        if mode == "saved-trace" and invalid in {"ollama", "tgi"}:
            from chimeraforge.bench.serving_binding import BACKEND_WRAPPERS

            candidates = saved.to_dict()["result"]["candidates"]
            selected = next(
                (
                    i
                    for i, row in enumerate(candidates)
                    if BACKEND_WRAPPERS.get(row["backend"], row["backend"]) == invalid
                ),
                None,
            )
            assert selected is not None, (
                "the native plan must actually contain the unsupported alias"
            )
            options.pop("backend")
        else:
            selected = indices["vllm"]
        with pytest.raises((api.PlanError, MonitorConnectionError, ValueError)):
            if mode == "trace":
                await api.replay_trace(
                    rows, model=wire.MODEL, backend=options.pop("backend", "vllm"), **options
                )
            elif mode == "saved-trace":
                await api.replay_plan_trace(
                    saved, rows, candidate_index=selected, model=wire.MODEL, **options
                )
            else:
                await api.benchmark_plan(
                    saved, candidate_index=indices["vllm"], model=wire.MODEL, runs=1, **options
                )
        assert calls == []


@pytest.mark.parametrize("role", ["ca", "client", "client_key", "workload", "plan", "hardlink"])
def test_known_trace_outputs_refuse_all_held_and_tls_inputs_before_contact(
    active_plan, certs, tmp_path, role
):
    wire = load_script("ci_secure_active")
    source, workload = tmp_path / "plan.json", tmp_path / "workload.json"
    saved, indices = active_plan
    saved.save(source)
    workload.write_text(
        json.dumps(
            [
                {
                    "request_id": "one",
                    "prompt": "fixture",
                    "max_output_tokens": 4,
                    "arrival_offset_s": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    inputs = {**certs, "workload": workload, "plan": source}
    output = inputs[role] if role != "hardlink" else tmp_path / "alias.json"
    if role == "hardlink":
        output.hardlink_to(certs["ca"])
    before = {name: path.read_bytes() for name, path in inputs.items()}
    with wire.server(certs, backend="vllm") as (url, calls):
        result = CliRunner().invoke(
            app,
            [
                "trace",
                str(workload),
                "--from-plan",
                str(source),
                "--candidate-index",
                str(indices["vllm"]),
                "--model",
                wire.MODEL,
                "--base-url",
                url,
                "--secure",
                "--ca-bundle",
                str(certs["ca"]),
                "--client-cert",
                str(certs["client"]),
                "--client-key",
                str(certs["client_key"]),
                "--out",
                str(output),
                "--json",
            ],
        )
        assert result.exit_code == 2, result.output
        assert calls == []
    assert {name: path.read_bytes() for name, path in inputs.items()} == before


@pytest.mark.parametrize("fault", ["encrypted", "malformed", "partial"])
def test_cli_client_key_admission_is_noninteractive_and_zero_contact(certs, tmp_path, fault):
    wire = load_script("ci_secure_active")
    key = (
        certs["encrypted_key"] if fault == "encrypted" else tmp_path / "FictionalMalformedKey82.pem"
    )
    if fault != "encrypted":
        key.write_text("FictionalPrivateKeyCanary82", encoding="ascii")
    with wire.server(certs, backend="vllm") as (url, calls):
        args = [
            "bench",
            "--model",
            wire.MODEL,
            "--backend",
            "vllm",
            "--base-url",
            url,
            "--secure",
            "--ca-bundle",
            str(certs["ca"]),
            "--client-cert",
            str(certs["client"]),
            "--json",
        ]
        if fault != "partial":
            args.extend(["--client-key", str(key)])
        result = CliRunner().invoke(app, args, input="\n")
        assert result.exit_code == 1 and calls == []
        assert "password" not in (result.stdout + result.stderr).lower()
        assert (
            str(key) not in result.stdout + result.stderr
            and "FictionalPrivateKeyCanary82" not in result.output
        )


@pytest.mark.parametrize("mode", ["bench", "saved-bench"])
@pytest.mark.parametrize("role", ["ca", "client", "client_key"])
def test_known_bench_directory_alias_refuses_before_contact(
    active_plan, certs, tmp_path, mode, role
):
    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    source = tmp_path / "saved.json"
    saved.save(source)
    before = {name: path.read_bytes() for name, path in certs.items()}
    with wire.server(certs, backend="vllm") as (url, calls):
        args = [
            "bench",
            "--model",
            wire.MODEL,
            "--base-url",
            url,
            "--secure",
            "--ca-bundle",
            str(certs["ca"]),
            "--client-cert",
            str(certs["client"]),
            "--client-key",
            str(certs["client_key"]),
            "--output-dir",
            str(certs[role]),
            "--json",
        ]
        args += (
            ["--plan", str(source), "--candidate-index", str(indices["vllm"])]
            if mode == "saved-bench"
            else ["--backend", "vllm"]
        )
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 1, result.output
        assert calls == []
    assert before == {name: path.read_bytes() for name, path in certs.items()}


def test_secure_native_guard_failure_has_no_private_exception_chain(certs, tmp_path, monkeypatch):
    import importlib

    command = importlib.import_module("chimeraforge.plan_study")
    wire = load_script("ci_secure_active")
    workload = tmp_path / "workload.json"
    workload.write_text(
        json.dumps(
            [
                {
                    "request_id": "one",
                    "prompt": "fixture",
                    "max_output_tokens": 4,
                    "arrival_offset_s": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    secret = "FictionalPrivatePath82"

    def broken(*args):
        raise api.PlanError(secret)

    monkeypatch.setattr(command, "protect_output", broken)
    with wire.server(certs, backend="vllm") as (url, calls):
        result = CliRunner().invoke(
            app,
            [
                "trace",
                str(workload),
                "--model",
                wire.MODEL,
                "--backend",
                "vllm",
                "--base-url",
                url,
                "--secure",
                "--ca-bundle",
                str(certs["ca"]),
                "--out",
                str(tmp_path / "out.json"),
                "--json",
            ],
        )
        assert result.exit_code == 2 and calls == []
        import traceback

        assert secret not in result.output + "".join(traceback.format_exception(*result.exc_info))


@pytest.mark.asyncio
async def test_secure_receipt_late_save_categorically_handles_native_oserror(
    certs, monkeypatch, tmp_path
):
    from chimeraforge.api import PlanArtifact

    wire = load_script("ci_secure_active")
    with wire.server(certs, backend="vllm") as (url, _):
        connection = MonitorConnection(url, ca_bundle=certs["ca"])
        receipt = await api.replay_trace(
            [TraceRequest("one", "fixture", 4, 0)],
            model=wire.MODEL,
            backend="vllm",
            base_url=url,
            connection=connection,
        )
    secret = "FictionalPrivateFilesystem82"

    def broken(*args):
        raise OSError(secret)

    monkeypatch.setattr(PlanArtifact, "save", broken)
    with pytest.raises(api.PlanError) as error:
        receipt.save(tmp_path / "out.json")
    assert error.value.__suppress_context__ and secret not in str(error.value)


@pytest.mark.asyncio
async def test_saved_benchmark_guard_holds_actual_relative_input_before_await(
    active_plan, certs, tmp_path, monkeypatch
):
    from chimeraforge.bench import runner

    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    original_dir, other_dir = tmp_path / "original", tmp_path / "later"
    original_dir.mkdir()
    other_dir.mkdir()
    source = original_dir / "plan.json"
    saved.save(source)
    before = source.read_bytes()
    native = runner.run_benchmark

    async def change_cwd(*args, **kwargs):
        result = await native(*args, **kwargs)
        monkeypatch.chdir(other_dir)
        return result

    monkeypatch.setattr(runner, "run_benchmark", change_cwd)
    monkeypatch.chdir(original_dir)
    with wire.server(certs, backend="vllm") as (url, _):
        receipt = await api.benchmark_plan(
            "plan.json",
            candidate_index=indices["vllm"],
            model=wire.MODEL,
            base_url=url,
            runs=1,
            connection=MonitorConnection(url, ca_bundle=certs["ca"]),
        )
    with pytest.raises(api.PlanError):
        receipt.save(source)
    assert source.read_bytes() == before
