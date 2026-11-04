"""Real TLS/authentication and startup-held exporter connection settings."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from chimeraforge import api
from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
from test_fleet_monitor import native_fleet as native_fleet, request
from test_fleet_exporter_state import changed
from test_secure_monitor import certs as certs, fixture

_spec = importlib.util.spec_from_file_location(
    "exporter_anonymous_fixture",
    Path(__file__).resolve().parents[1] / "scripts/ci_monitor_fleet.py",
)
assert _spec and _spec.loader
anonymous = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anonymous)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize("mtls", [False, True])
async def test_exporter_holds_explicit_tls_auth_and_caller_mapping(
    native_fleet, certs, backend, mtls, monkeypatch
):
    saved, indices = native_fleet
    token = "PrivateExporterToken_91"
    monkeypatch.setenv("EXPORTER_TEST_TOKEN", token)
    with fixture.server(certs, backend=backend, token=token, mtls=mtls) as (url, calls):
        options = {"ca_bundle": certs["ca"], "bearer_env": "EXPORTER_TEST_TOKEN"}
        if mtls:
            options.update(client_cert=certs["client"], client_key=certs["client_key"])
        connection = MonitorConnection.from_env(url, **options)
        mapping = {f"replica-{i}": connection for i in (1, 2, 3)}
        controls = request([url + f"/r{i}/metrics" for i in (1, 2, 3)])
        async with api.serve_fleet_exporter(
            saved,
            controls,
            candidate_index=indices[backend],
            connections=mapping,
            config=api.FleetExporterConfig(port=0, poll_seconds=0.05),
        ) as running:
            first = await changed(running)
            assert first.native_exit_code == 0
            mapping.clear()
            monkeypatch.setenv("EXPORTER_TEST_TOKEN", "ChangedPrivateToken_91")
            certs["ca"].write_text("not a certificate", encoding="ascii")
            later = await changed(running, first.sequence)
            assert later.native_exit_code == 0 and later.original_replicas == 3
            assert all(row["authorized"] and row["client_certificate"] == mtls for row in calls)
            assert token.encode() not in later.body and url.encode() not in later.body
            assert b" model=" not in later.body
        assert running.closed and running.worker_joined and running.listener_joined


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["ca", "auth"])
async def test_exporter_secure_failure_has_no_old_pass(native_fleet, certs, fault):
    saved, indices = native_fleet
    with fixture.server(certs, token="CorrectPrivateToken_91") as (url, calls):
        connection = MonitorConnection(
            url,
            ca_bundle=certs["wrong_ca"] if fault == "ca" else certs["ca"],
            bearer_token="WrongPrivateToken_91",
        )
        async with api.serve_fleet_exporter(
            saved,
            request([url + f"/r{i}/metrics" for i in (1, 2, 3)]),
            candidate_index=indices["vllm"],
            connections={f"replica-{i}": connection for i in (1, 2, 3)},
            config=api.FleetExporterConfig(port=0),
        ) as running:
            snapshot = await changed(running)
            assert snapshot.native_exit_code == 4 and snapshot.original_replicas == 3
            assert b'chimeraforge_fleet_qualification{outcome="pass"} 0' in snapshot.body
            assert b"chimeraforge_fleet_slot_p95_lower_ms{" not in snapshot.body
        assert calls == [] if fault == "ca" else any(not row["authorized"] for row in calls)


@pytest.mark.asyncio
async def test_foreign_secure_origin_refuses_before_any_contact(native_fleet, certs):
    saved, indices = native_fleet
    with fixture.server(certs) as (url, calls):
        foreign = MonitorConnection("https://foreign.invalid/metrics", ca_bundle=certs["ca"])
        with pytest.raises(MonitorConnectionError, match="origin mismatch"):
            async with api.serve_fleet_exporter(
                saved,
                request([url + f"/r{i}/metrics" for i in (1, 2, 3)]),
                candidate_index=indices["vllm"],
                connections={"replica-3": foreign},
                config=api.FleetExporterConfig(port=0),
            ):
                pytest.fail("foreign connection admitted")
        assert calls == []


@pytest.mark.asyncio
async def test_opted_secure_default_trust_is_held_before_first_poll(
    native_fleet, certs, monkeypatch
):
    import certifi

    saved, indices = native_fleet
    monkeypatch.setattr(certifi, "where", lambda: str(certs["ca"]))
    with fixture.server(certs) as (url, calls):
        mapping = {"replica-1": MonitorConnection(url)}
        async with api.serve_fleet_exporter(
            saved,
            request([url + f"/r{i}/metrics" for i in (1, 2, 3)]),
            candidate_index=indices["vllm"],
            connections=mapping,
            config=api.FleetExporterConfig(port=0, poll_seconds=0.05),
        ) as running:
            first = await changed(running)
            assert first.native_exit_code == 0
            certs["ca"].write_text("changed after startup", encoding="ascii")
            later = await changed(running, first.sequence, state="fresh")
            assert later.native_exit_code == 0, "default TLS context recreated after startup"
        assert calls and running.listener_joined and running.worker_joined


@pytest.mark.asyncio
async def test_anonymous_mixed_http_https_retains_native_policy(native_fleet, certs, monkeypatch):
    import certifi

    saved, indices = native_fleet
    monkeypatch.setattr(certifi, "where", lambda: str(certs["ca"]))
    with anonymous._server("ci/manual-fleet") as (plain, _), fixture.server(certs) as (url, calls):
        async with api.serve_fleet_exporter(
            saved,
            request([url + "/r1/metrics", plain[1], url + "/r3/metrics"]),
            candidate_index=indices["vllm"],
            connections=None,
            config=api.FleetExporterConfig(port=0, poll_seconds=0.05),
        ) as running:
            first = await changed(running)
            assert first.native_exit_code == 0
            later = await changed(running, first.sequence)
            assert later.native_exit_code == 0 and later.original_replicas == 3
        assert calls and running.listener_joined and running.worker_joined
