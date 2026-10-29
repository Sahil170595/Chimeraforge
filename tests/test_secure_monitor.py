"""Real CPU TLS/authentication, with complete native source populations."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path

import pytest

from chimeraforge import api
from chimeraforge.monitor import MonitorRequest, run_monitor
from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
from test_fleet_monitor import native_fleet as native_fleet, request

_spec = importlib.util.spec_from_file_location(
    "ci_secure_monitor", Path(__file__).resolve().parents[1] / "scripts/ci_secure_monitor.py"
)
assert _spec and _spec.loader
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)


@pytest.fixture
def certs(tmp_path):
    return fixture.certificates(tmp_path / "tls")


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize("mtls", [False, True])
def test_standalone_saved_and_whole_fleet_real_tls(native_fleet, certs, backend, mtls):
    saved, indices = native_fleet
    original = saved.to_dict()
    token = "PrivateWireToken_78"
    with fixture.server(certs, backend=backend, token=token, mtls=mtls) as (url, calls):
        kwargs = {"ca_bundle": certs["ca"], "bearer_token": token}
        if mtls:
            kwargs.update(client_cert=certs["client"], client_key=certs["client_key"])
        connection = MonitorConnection(url, **kwargs)
        monitor = MonitorRequest(backend, url, "ci/manual-fleet", ttft_slo=500, interval=0.01)
        standalone = run_monitor(monitor, connection=connection)
        assert standalone.exit_code == 0
        calls.clear()
        bound = api.monitor_plan(
            saved, monitor, candidate_index=indices[backend], connection=connection
        )
        assert bound.exit_code == 0 and bound.plan_binding["identity"]["state"] == "matched", (
            bound.to_dict()
        )
        required = (
            ["version", "v1/models", "server_info?config_format=json"]
            if backend == "vllm"
            else ["server_info", "model_info"]
        )
        assert all(sum(row["route"] == route for row in calls) == 2 for route in required)
        calls.clear()
        urls = [url + f"/r{i}/metrics" for i in range(1, 4)]
        value = request(urls)
        result = asyncio.run(
            api.monitor_fleet(
                saved,
                value,
                candidate_index=indices[backend],
                connections={f"replica-{i}": connection for i in range(1, 4)},
            )
        )
        assert result.exit_code == 0, result.to_dict()
        assert len(result.slots) == 3 and all(
            len(slot.windows) == 1 and len(slot.observations) == 2 for slot in result.slots
        )
        assert result.cleanup["closed_pools"] == result.cleanup["owned_pools"] == 6
        assert result.cleanup["state"] == "completed"
        assert all(
            sum(row["route"] == route and row["replica"] == f"r{i}" for row in calls) == 2
            for i in range(1, 4)
            for route in required
        )
        assert all(row["authorized"] and row["client_certificate"] == mtls for row in calls)
        assert token not in json.dumps(asdict(result)) + repr(connection)
    assert saved.to_dict() == original


@pytest.mark.parametrize("fault", ["ca", "hostname", "missing-client", "wrong-client"])
def test_real_tls_failures_never_reach_http_headers(native_fleet, certs, fault):
    from chimeraforge.monitor import MonitorError

    with fixture.server(certs, mtls="client" in fault, wrong_host=fault == "hostname") as (
        url,
        calls,
    ):
        options = {"ca_bundle": certs["wrong_ca"] if fault == "ca" else certs["ca"]}
        if fault == "wrong-client":
            options.update(client_cert=certs["wrong_client"], client_key=certs["wrong_client_key"])
        connection = MonitorConnection(url, **options)
        with pytest.raises(MonitorError, match="secure metrics observation unavailable"):
            run_monitor(
                MonitorRequest("vllm", url, "ci/manual-fleet", ttft_slo=500, interval=0.01),
                connection=connection,
            )
        saved, indices = native_fleet
        urls = [url + f"/r{i}/metrics" for i in range(1, 4)]
        report = asyncio.run(
            api.monitor_fleet(
                saved,
                request(urls),
                candidate_index=indices["vllm"],
                connections={f"replica-{i}": connection for i in range(1, 4)},
            )
        )
        assert report.exit_code == 4 and len(report.slots) == 3
        assert report.cleanup["resources_closed"] and report.cleanup["closed_pools"] == 6
        assert calls == []


@pytest.mark.parametrize("mode", ["missing", "wrong", "metadata-only"])
def test_authentication_covers_metadata_and_metrics(native_fleet, certs, mode):
    saved, indices = native_fleet
    with fixture.server(certs, token="CorrectToken_78", deny_metadata=mode == "metadata-only") as (
        url,
        calls,
    ):
        connection = MonitorConnection(
            url,
            ca_bundle=certs["ca"],
            bearer_token="CorrectToken_78"
            if mode == "metadata-only"
            else "WrongToken_78"
            if mode == "wrong"
            else None,
        )
        urls = [url + f"/r{i}/metrics" for i in range(1, 4)]
        report = asyncio.run(
            api.monitor_fleet(
                saved,
                request(urls),
                candidate_index=indices["vllm"],
                connections={f"replica-{i}": connection for i in range(1, 4)},
            )
        )
        assert report.exit_code == 4 and len(report.slots) == 3
        assert report.cleanup["state"] == "completed"
        if mode == "metadata-only":
            assert all(
                slot.slo == "pass" and slot.binding["identity"]["state"] == "unavailable"
                for slot in report.slots
            )
            assert all(
                sum(row["route"] == "version" and row["replica"] == f"r{i}" for row in calls) == 2
                for i in range(1, 4)
            )
        assert any(not row["authorized"] for row in calls)


def test_distinct_origins_do_not_borrow_another_replica_credential(native_fleet, certs):
    saved, indices = native_fleet
    with ExitStack() as stack:
        servers = [stack.enter_context(fixture.server(certs, token=f"Token_{i}")) for i in range(3)]
        urls = [url + "/metrics" for url, _ in servers]
        connections = {
            f"replica-{i + 1}": MonitorConnection(
                url, ca_bundle=certs["ca"], bearer_token=f"Token_{i}"
            )
            for i, url in enumerate(urls)
        }
        good = asyncio.run(
            api.monitor_fleet(
                saved, request(urls), candidate_index=indices["vllm"], connections=connections
            )
        )
        assert good.exit_code == 0
        for _, calls in servers:
            calls.clear()
        connections["replica-2"] = MonitorConnection(urls[1], ca_bundle=certs["ca"])
        missing = asyncio.run(
            api.monitor_fleet(
                saved, request(urls), candidate_index=indices["vllm"], connections=connections
            )
        )
        assert missing.exit_code == 4 and [slot.state for slot in missing.slots] == [
            "complete",
            "error",
            "complete",
        ]
        assert not any(row["authorized"] for row in servers[1][1])
        assert all(row["authorized"] for number in (0, 2) for row in servers[number][1])


@pytest.mark.parametrize("mode", ["empty-http", "unknown-id", "null-value", "wrong-origin"])
def test_whole_mapping_is_admitted_before_contact(native_fleet, certs, mode):
    saved, indices = native_fleet
    with fixture.server(certs) as (url, calls):
        urls = [url + f"/r{i}/metrics" for i in range(1, 4)]
        connections = {}
        if mode == "empty-http":
            urls[2] = urls[2].replace("https:", "http:")
        elif mode == "unknown-id":
            connections["foreign"] = MonitorConnection(url, ca_bundle=certs["ca"])
        elif mode == "null-value":
            connections["replica-3"] = None
        else:
            connections["replica-3"] = MonitorConnection(
                "https://other.test", ca_bundle=certs["ca"]
            )
        with pytest.raises(MonitorConnectionError):
            asyncio.run(
                api.monitor_fleet(
                    saved, request(urls), candidate_index=indices["vllm"], connections=connections
                )
            )
        assert calls == []


def test_redirect_does_not_contact_cross_origin_target(certs):
    from chimeraforge.monitor import MonitorError

    with (
        fixture.server(certs) as (target, received),
        fixture.server(certs, token="PrivateRedirectToken", redirect=target + "/metrics") as (
            url,
            calls,
        ),
    ):
        connection = MonitorConnection(
            url, ca_bundle=certs["ca"], bearer_token="PrivateRedirectToken"
        )
        with pytest.raises(MonitorError):
            run_monitor(
                MonitorRequest("vllm", url, "ci/manual-fleet", ttft_slo=500, interval=0.01),
                connection=connection,
            )
        assert len(calls) == 1 and calls[0]["authorized"] and received == []


def test_tls_admission_refuses_encrypted_and_unsafe_files_without_private_errors(
    certs, tmp_path, caplog
):
    paths = [
        (certs["client"], None),
        (None, certs["client_key"]),
        (certs["client"], certs["encrypted_key"]),
        (certs["client"], certs["wrong_client_key"]),
    ]
    for cert, key in paths:
        with pytest.raises(MonitorConnectionError):
            MonitorConnection(
                "https://example.test", ca_bundle=certs["ca"], client_cert=cert, client_key=key
            )
    bad = tmp_path / "PrivatePathCanary_78"
    bad.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(MonitorConnectionError) as caught:
        MonitorConnection("https://example.test", ca_bundle=bad)
    assert str(bad) not in str(caught.value) + caplog.text


def test_geometry_and_metadata_errors_do_not_log_private_messages(
    certs, native_fleet, monkeypatch, caplog
):
    import logging
    from chimeraforge.bench import serving
    from chimeraforge.planner.resolver import ResolverError

    secret = "PrivateExceptionCanary_78"

    def fail(*args):
        raise ResolverError(secret)

    monkeypatch.setattr(serving, "spec_from_hf", fail)
    caplog.set_level(logging.DEBUG, logger="chimeraforge")
    import httpx

    def reply(request):
        data = (
            {"vllm_config": {"model_config": {"hf_config": {"secret": secret}}}}
            if request.url.path == "/server_info"
            else {}
        )
        return httpx.Response(200, json=data)

    async def observe():
        connection = MonitorConnection("https://example.test", ca_bundle=certs["ca"])
        from chimeraforge.bench.backends.vllm import VLLMBackend

        backend = VLLMBackend(
            "https://example.test", connection=connection, transport=httpx.MockTransport(reply)
        )
        try:
            return await serving.observe_backend(backend, "ci/manual-fleet")
        finally:
            await backend.close()

    result = asyncio.run(observe())
    assert "geometry unavailable" in caplog.text
    assert secret not in caplog.text + json.dumps(result)


def test_opted_api_ignores_only_documented_proxy_ca_keylog_environment(
    certs, monkeypatch, tmp_path
):
    import os

    with (
        fixture.server(certs, token="EnvToken_78") as (url, calls),
        fixture.proxy_sentinel() as (proxy, proxy_calls),
    ):
        keylog = tmp_path / "implicit-keylog"
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            monkeypatch.setenv(name, proxy)
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing-file"))
        monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "missing-directory"))
        monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
        before = dict(os.environ)
        connection = MonitorConnection(url, ca_bundle=certs["ca"], bearer_token="EnvToken_78")
        result = run_monitor(
            MonitorRequest("vllm", url, "ci/manual-fleet", ttft_slo=500, interval=0.01),
            connection=connection,
        )
        assert result.exit_code == 0 and len(calls) == 2
        assert proxy_calls == [] and not keylog.exists() and dict(os.environ) == before


def test_explicit_empty_mapping_opts_all_slots_into_verified_anonymous_tls(
    native_fleet, certs, monkeypatch
):
    import certifi

    monkeypatch.setattr(certifi, "where", lambda: str(certs["ca"]))
    saved, indices = native_fleet
    with fixture.server(certs) as (url, calls):
        result = asyncio.run(
            api.monitor_fleet(
                saved,
                request([url + f"/r{i}/metrics" for i in range(1, 4)]),
                candidate_index=indices["vllm"],
                connections={},
            )
        )
        assert result.exit_code == 0 and len(result.slots) == 3 and calls


@pytest.mark.parametrize("known", ["mismatch", "breach"])
def test_secure_mixed_auth_failure_keeps_native_known_failure_priority(native_fleet, certs, known):
    from dataclasses import replace

    saved, indices = native_fleet
    with ExitStack() as stack:
        scenes = [
            stack.enter_context(
                fixture.server(
                    certs,
                    token=f"Token_{i}",
                    quant="Q8_0" if known == "mismatch" and i == 0 else "float16",
                    slow=known == "breach" and i == 0,
                )
            )
            for i in range(3)
        ]
        urls = [url for url, _ in scenes]
        connections = {
            f"replica-{i + 1}": MonitorConnection(
                url, ca_bundle=certs["ca"], bearer_token="bad" if i == 1 else f"Token_{i}"
            )
            for i, url in enumerate(urls)
        }
        value = request(urls)
        if known == "breach":
            value = replace(value, ttft_slo=50)
        result = asyncio.run(
            api.monitor_fleet(
                saved, value, candidate_index=indices["vllm"], connections=connections
            )
        )
        if known == "breach":
            assert result.slots[0].slo == "breach"
        assert result.exit_code == (5 if known == "mismatch" else 3), result.to_dict()
        assert len(result.slots) == 3 and result.slots[1].state == "error"
        assert result.cleanup["state"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["stop", "second-cancel", "deadline"])
async def test_secure_owned_pools_clients_streams_and_tasks_close(
    native_fleet, certs, monkeypatch, kind
):
    import httpx
    from dataclasses import replace
    from chimeraforge import fleet_monitor

    saved, indices = native_fleet
    pools, clients = [], []
    before = asyncio.all_tasks()
    original_init = httpx.AsyncClient.__init__
    original_pool = fleet_monitor.OwnedPool
    gate, closing = asyncio.Event(), asyncio.Event()

    def client_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        clients.append(self)

    def pool(*args, **kwargs):
        value = original_pool(*args, **kwargs)
        pools.append(value)
        return value

    original_cleanup = fleet_monitor._cleanup

    async def cleanup(*args):
        if kind == "second-cancel":
            # Handshake before cooperative worker/client drain reaches the pool-close phase.
            closing.set()
            await gate.wait()
        return await original_cleanup(*args)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", client_init)
    monkeypatch.setattr(fleet_monitor, "OwnedPool", pool)
    monkeypatch.setattr(fleet_monitor, "_cleanup", cleanup)
    with fixture.server(certs, token="CleanupToken_78", mtls=True) as (url, calls):
        connection = MonitorConnection(
            url,
            ca_bundle=certs["ca"],
            bearer_token="CleanupToken_78",
            client_cert=certs["client"],
            client_key=certs["client_key"],
        )
        value = replace(
            request([url + f"/r{i}/metrics" for i in range(1, 4)]),
            interval=10,
            observation_seconds=30,
            cleanup_seconds=5,
        )
        stop = asyncio.Event()
        task = asyncio.create_task(
            api.monitor_fleet(
                saved,
                value,
                candidate_index=indices["vllm"],
                connections={f"replica-{i}": connection for i in range(1, 4)},
                stop_event=stop,
            )
        )

        async def observed():
            while sum(row["route"] == "server_info?config_format=json" for row in calls) < 3:
                await asyncio.sleep(0.01)

        try:
            await asyncio.wait_for(observed(), timeout=10)
            if kind == "second-cancel":
                assert task.cancel()
                await asyncio.wait_for(closing.wait(), timeout=5)
                assert not task.done()
                assert task.cancel()
                gate.set()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                if kind == "stop":
                    stop.set()
                else:
                    assert len(pools) == 6
                    pools[0].budget.deadline = asyncio.get_running_loop().time() - 1
                result = await task
                assert (
                    result.exit_code == 4
                    and len(result.slots) == 3
                    and result.cleanup["state"] == "completed"
                ), result.to_dict()
        finally:
            gate.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert len(pools) == len(clients) == 6
        assert all(value.closed and not value.streams for value in pools)
        assert all(value.is_closed for value in clients)
        assert asyncio.all_tasks() == before


@pytest.mark.asyncio
async def test_real_tls_fixture_readiness_failure_still_closes_all_owners(
    native_fleet, certs, monkeypatch
):
    import httpx
    from chimeraforge import fleet_monitor

    clients, pools, injected = [], [], []
    before = asyncio.all_tasks()
    original_init, original_pool = httpx.AsyncClient.__init__, fleet_monitor.OwnedPool
    original_wait = asyncio.wait_for

    def client_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        clients.append(self)

    def pool(*args, **kwargs):
        value = original_pool(*args, **kwargs)
        pools.append(value)
        return value

    async def fail_after_readiness(awaitable, timeout):
        code = getattr(awaitable, "cr_code", None)
        readiness = code is not None and code.co_name == "observed" and code.co_filename == __file__
        result = await original_wait(awaitable, timeout)
        if readiness:
            injected.append(True)
            raise RuntimeError("controlled fixture readiness failure")
        return result

    monkeypatch.setattr(httpx.AsyncClient, "__init__", client_init)
    monkeypatch.setattr(fleet_monitor, "OwnedPool", pool)
    monkeypatch.setattr(asyncio, "wait_for", fail_after_readiness)
    try:
        with pytest.raises(RuntimeError, match="controlled fixture readiness failure"):
            await test_secure_owned_pools_clients_streams_and_tasks_close(
                native_fleet, certs, monkeypatch, "stop"
            )
        assert injected == [True]
        assert len(clients) == len(pools) == 6
        assert all(value.is_closed for value in clients)
        assert all(value.closed and not value.streams for value in pools)
        assert asyncio.all_tasks() == before
    finally:
        pending = asyncio.all_tasks() - before
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


def test_cli_private_admission_and_per_id_errors_never_contact(
    certs, native_fleet, tmp_path, monkeypatch
):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, indices = native_fleet
    path = tmp_path / "saved.json"
    saved.save(path)
    with fixture.server(certs) as (url, calls):
        common = [
            "monitor",
            "--backend",
            "vllm",
            "--url",
            url,
            "--model",
            "ci/manual-fleet",
            "--ttft-slo",
            "500",
            "--json",
        ]
        for extras in (
            ["--bearer-env", "PrivateMissingEnv_78"],
            ["--client-cert", str(certs["client"])],
            [
                "--client-cert",
                str(certs["client"]),
                "--client-key",
                str(certs["encrypted_key"]),
                "--ca-bundle",
                str(certs["ca"]),
            ],
            ["--ca-bundle", str(tmp_path / "PrivateMissingPath_78")],
        ):
            result = CliRunner().invoke(app, common + extras)
            assert result.exit_code == 1
            text = result.stdout + result.stderr
            assert "PrivateMissing" not in text and str(certs["encrypted_key"]) not in text
        fleet = [
            "monitor-fleet",
            "--from-plan",
            str(path),
            "--candidate-index",
            str(indices["vllm"]),
            "--json",
        ]
        for i in range(1, 4):
            fleet += ["--endpoint", f"r{i}={url}/r{i}"]
        for extras in (
            ["--bearer-env", "unknown=PRIVATE_NAME"],
            ["--bearer-env", "r1=PRIVATE_NAME", "--bearer-env", "r1=PRIVATE_OTHER"],
            ["--client-key", "r3=" + str(certs["client_key"])],
            ["--secure"],
        ):
            result = CliRunner().invoke(app, fleet + extras)
            assert result.exit_code == 1
            assert "PRIVATE_" not in result.stdout + result.stderr
        assert calls == []


def test_positive_cli_and_prometheus_keep_runtime_settings_private(certs, caplog, monkeypatch):
    from typer.testing import CliRunner
    from chimeraforge.cli import app
    from chimeraforge.monitor import prometheus_text

    token, env_name = "PrivatePositiveToken_78", "PrivatePositiveEnv_78"
    monkeypatch.setenv(env_name, token)
    with fixture.server(certs, token=token, mtls=True) as (url, calls):
        result = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                "ci/manual-fleet",
                "--ttft-slo",
                "500",
                "--interval",
                ".01",
                "--json",
                "--bearer-env",
                env_name,
                "--ca-bundle",
                str(certs["ca"]),
                "--client-cert",
                str(certs["client"]),
                "--client-key",
                str(certs["client_key"]),
            ],
        )
        assert result.exit_code == 0, result.output
        connection = MonitorConnection.from_env(
            url,
            bearer_env=env_name,
            ca_bundle=certs["ca"],
            client_cert=certs["client"],
            client_key=certs["client_key"],
        )
        report = run_monitor(
            MonitorRequest("vllm", url, "ci/manual-fleet", ttft_slo=500, interval=0.01),
            connection=connection,
        )
        public = (
            result.stdout
            + result.stderr
            + json.dumps(asdict(report))
            + prometheus_text(report)
            + caplog.text
            + repr(connection)
        )
        assert all(
            value not in public
            for value in (token, env_name, *(str(path) for path in certs.values()))
        )
        assert len(calls) == 4 and all(
            row["authorized"] and row["client_certificate"] for row in calls
        )


def test_secure_metadata_and_closure_errors_remain_categorical(
    certs, native_fleet, monkeypatch, caplog
):
    import httpx
    from chimeraforge import monitor, plan_monitor
    from chimeraforge.bench.backends.vllm import VLLMBackend
    from test_monitor_slo import pair

    secret = "PrivateNativeExceptionMessage_78"
    snapshots = iter(text.replace("org/model", "ci/manual-fleet") for text in pair())
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))

    def fail(request):
        raise httpx.ConnectError(secret)

    class FailingClose(VLLMBackend):
        async def close(self):
            await super().close()
            raise RuntimeError(secret)

    backends = []

    def adapter(*args, **kwargs):
        backend = FailingClose(
            base_url=kwargs["base_url"],
            connection=kwargs["connection"],
            transport=httpx.MockTransport(fail),
        )
        backends.append(backend)
        return backend

    monkeypatch.setattr(plan_monitor, "get_backend", adapter)
    saved, indices = native_fleet
    connection = MonitorConnection("https://example.test", ca_bundle=certs["ca"])
    result = api.monitor_plan(
        saved,
        MonitorRequest(
            "vllm", "https://example.test", "ci/manual-fleet", ttft_slo=500, interval=0.01
        ),
        candidate_index=indices["vllm"],
        connection=connection,
    )
    assert result.exit_code == 4
    assert secret not in json.dumps(result.to_dict()) + caplog.text
    assert "cleanup failed" in caplog.text and all(
        backend._client.is_closed for backend in backends
    )


@pytest.mark.parametrize("scope", ["standalone", "saved", "fleet"])
@pytest.mark.parametrize("role", ["ca", "client", "client_key"])
def test_cli_output_cannot_replace_any_tls_input_before_contact(
    certs, native_fleet, tmp_path, scope, role
):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, indices = native_fleet
    plan_path = tmp_path / "saved.json"
    saved.save(plan_path)
    inputs = {path: path.read_bytes() for path in (*certs.values(), plan_path)}
    with fixture.server(certs, mtls=True) as (url, calls):
        if scope == "fleet":
            arguments = [
                "monitor-fleet",
                "--from-plan",
                str(plan_path),
                "--candidate-index",
                str(indices["vllm"]),
                "--ttft-slo",
                "500",
                "--interval",
                ".01",
                "--json",
            ]
            for i in range(1, 4):
                arguments += [
                    "--endpoint",
                    f"r{i}={url}/r{i}/metrics",
                    "--ca-bundle",
                    f"r{i}={certs['ca']}",
                    "--client-cert",
                    f"r{i}={certs['client']}",
                    "--client-key",
                    f"r{i}={certs['client_key']}",
                ]
        else:
            arguments = [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                "ci/manual-fleet",
                "--ttft-slo",
                "500",
                "--interval",
                ".01",
                "--json",
                "--ca-bundle",
                str(certs["ca"]),
                "--client-cert",
                str(certs["client"]),
                "--client-key",
                str(certs["client_key"]),
            ]
            if scope == "saved":
                arguments += [
                    "--from-plan",
                    str(plan_path),
                    "--candidate-index",
                    str(indices["vllm"]),
                ]
        result = CliRunner().invoke(app, arguments + ["--prometheus", str(certs[role])])
        assert all(path.read_bytes() == raw for path, raw in inputs.items()), (
            "TLS/source input was replaced by observation output"
        )
        assert calls == [], "alias was not refused before contact"
        assert result.exit_code == 1, result.output
        assert all(str(path) not in result.stdout + result.stderr for path in certs.values())


@pytest.mark.parametrize("scope", ["saved", "fleet"])
@pytest.mark.parametrize("hardlink", [False, True])
def test_saved_source_output_aliases_are_refused_with_native_file_identity(
    native_fleet, tmp_path, scope, hardlink
):
    import os
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, indices = native_fleet
    source, output = tmp_path / "source.json", tmp_path / "output.json"
    saved.save(source)
    original = source.read_bytes()
    if hardlink:
        os.link(source, output)
    else:
        output = source.parent / "." / source.name
    common = [
        "--from-plan",
        str(source),
        "--candidate-index",
        str(indices["vllm"]),
        "--prometheus",
        str(output),
        "--json",
    ]
    if scope == "saved":
        arguments = [
            "monitor",
            "--backend",
            "vllm",
            "--url",
            "https://must-not-contact.invalid",
            "--model",
            "ci/manual-fleet",
            "--secure",
            *common,
        ]
    else:
        arguments = ["monitor-fleet", "--secure", *common]
        for i in range(1, 4):
            arguments += ["--endpoint", f"r{i}=https://must-not-contact.invalid/r{i}/metrics"]
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 1, result.output
    assert source.read_bytes() == original and output.read_bytes() == original


@pytest.mark.parametrize("scope", ["standalone", "fleet"])
def test_private_guard_oserror_is_categorical_before_connection_construction(
    certs, native_fleet, tmp_path, monkeypatch, scope
):
    from typer.testing import CliRunner
    from chimeraforge.cli import app
    from chimeraforge import plan_study

    secret = "PrivateGuardPathCanary_78"

    def failure(*args):
        raise OSError(secret)

    def construct(*args, **kwargs):
        pytest.fail("output admission must precede connection preparation")

    monkeypatch.setattr(plan_study, "protect_output", failure)
    monkeypatch.setattr(MonitorConnection, "from_env", construct)
    if scope == "standalone":
        arguments = [
            "monitor",
            "--backend",
            "vllm",
            "--url",
            "https://example.test",
            "--model",
            "ci/manual-fleet",
            "--ttft-slo",
            "500",
            "--ca-bundle",
            str(certs["ca"]),
        ]
    else:
        saved, indices = native_fleet
        source = tmp_path / "saved.json"
        saved.save(source)
        arguments = [
            "monitor-fleet",
            "--from-plan",
            str(source),
            "--candidate-index",
            str(indices["vllm"]),
            "--ca-bundle",
            f"r1={certs['ca']}",
        ]
        for i in range(1, 4):
            arguments += ["--endpoint", f"r{i}=https://example.test/r{i}/metrics"]
    result = CliRunner().invoke(
        app, arguments + ["--prometheus", str(tmp_path / "out.prom"), "--json"]
    )
    assert result.exit_code == 1, result.output
    assert secret not in result.stdout + result.stderr
