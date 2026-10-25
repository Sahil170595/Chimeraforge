"""Owned CPU HTTPS fixtures for source and installed monitoring acceptance."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import ssl
import threading
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

FIXTURE_JOIN_SECONDS = 5


@contextmanager
def proxy_sentinel() -> Iterator[tuple[str, list[str]]]:
    calls: list[str] = []

    class Proxy(BaseHTTPRequestHandler):
        def do_CONNECT(self) -> None:
            calls.append("CONNECT")
            self.send_error(502)

        def do_GET(self) -> None:
            calls.append("GET")
            self.send_error(502)

        def log_message(self, format: str, *args: Any) -> None:
            return

    listener = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    listener.daemon_threads = False
    listener.block_on_close = True
    worker = threading.Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield f"http://127.0.0.1:{listener.server_port}", calls
    finally:
        listener.shutdown()
        listener.server_close()
        worker.join(FIXTURE_JOIN_SECONDS)
        assert not worker.is_alive()


def accept(cwd: Path, env: dict[str, str], saved: Path) -> dict[str, Any]:
    """Consume the complete public CLI/API against both native metadata protocols."""
    import asyncio
    import hashlib

    from ci_installed_acceptance import run_cli
    from chimeraforge import api
    from chimeraforge.monitor import MonitorRequest, run_monitor
    from chimeraforge.monitor_connection import MonitorConnection

    original = saved.read_bytes()
    data = json.loads(original)
    paths = certificates(cwd / "secure-fixture")
    controls = []
    negative_controls = []
    for backend in ("vllm", "sglang"):
        index = next(
            i
            for i, row in enumerate(data["result"]["candidates"])
            if row["backend"] == backend
            and row["quant"] == "FP16"
            and row["n_agents"] == 3
            and row["gpus_total"] == 6
        )
        model = data["result"]["candidates"][index]["model"]
        routes = (
            ["version", "v1/models", "server_info?config_format=json"]
            if backend == "vllm"
            else ["server_info", "model_info"]
        )
        for mtls in (False, True):
            with (
                server(paths, backend=backend, model=model, token="FixtureToken_78", mtls=mtls) as (
                    url,
                    calls,
                ),
                proxy_sentinel() as (proxy, proxy_calls),
            ):
                keylog = cwd / "must-not-create-keylog"
                child_env = dict(
                    env,
                    CF_FIXTURE_TOKEN_78="FixtureToken_78",
                    HTTP_PROXY=proxy,
                    HTTPS_PROXY=proxy,
                    ALL_PROXY=proxy,
                    NO_PROXY="",
                    SSL_CERT_FILE=str(cwd / "missing-ca"),
                    SSL_CERT_DIR=str(cwd / "missing-cadir"),
                    SSLKEYLOGFILE=str(keylog),
                )
                options: dict[str, Any] = {
                    "ca_bundle": paths["ca"],
                    "bearer_token": "FixtureToken_78",
                }
                cli_options = [
                    "--bearer-env",
                    "CF_FIXTURE_TOKEN_78",
                    "--ca-bundle",
                    str(paths["ca"]),
                ]
                if mtls:
                    options.update(client_cert=paths["client"], client_key=paths["client_key"])
                    cli_options += [
                        "--client-cert",
                        str(paths["client"]),
                        "--client-key",
                        str(paths["client_key"]),
                    ]
                connection = MonitorConnection(url, **options)
                request = MonitorRequest(backend, url, model, ttft_slo=500, interval=0.01)
                for scope in ("standalone", "saved", "fleet"):
                    calls.clear()
                    direct: api.MonitorReport | api.FleetMonitorReport
                    if scope == "fleet":
                        endpoints = tuple(
                            api.FleetEndpoint(f"replica-{i}", url + f"/r{i}/metrics")
                            for i in range(1, 4)
                        )
                        fleet_request = api.FleetMonitorRequest(
                            endpoints, interval=0.01, ttft_slo=500, observation_seconds=20
                        )
                        direct = asyncio.run(
                            api.monitor_fleet(
                                saved,
                                fleet_request,
                                candidate_index=index,
                                connections={row.id: connection for row in endpoints},
                            )
                        )
                        cli = [
                            "monitor-fleet",
                            "--from-plan",
                            str(saved),
                            "--candidate-index",
                            str(index),
                            "--interval",
                            ".01",
                            "--ttft-slo",
                            "500",
                            "--observation-seconds",
                            "20",
                            "--json",
                        ]
                        for endpoint in endpoints:
                            cli += [
                                "--endpoint",
                                endpoint.id + "=" + endpoint.url,
                                "--bearer-env",
                                endpoint.id + "=CF_FIXTURE_TOKEN_78",
                                "--ca-bundle",
                                endpoint.id + "=" + str(paths["ca"]),
                            ]
                            if mtls:
                                cli += [
                                    "--client-cert",
                                    endpoint.id + "=" + str(paths["client"]),
                                    "--client-key",
                                    endpoint.id + "=" + str(paths["client_key"]),
                                ]
                    else:
                        direct = (
                            api.monitor_plan(
                                saved, request, candidate_index=index, connection=connection
                            )
                            if scope == "saved"
                            else run_monitor(request, connection=connection)
                        )
                        cli = [
                            "monitor",
                            "--backend",
                            backend,
                            "--url",
                            url,
                            "--model",
                            model,
                            "--ttft-slo",
                            "500",
                            "--interval",
                            ".01",
                            "--json",
                            *cli_options,
                        ]
                        if scope == "saved":
                            cli += ["--from-plan", str(saved), "--candidate-index", str(index)]
                    observed = json.loads(run_cli(cli, cwd, child_env))
                    assert direct.exit_code == 0
                    if scope == "fleet":
                        assert isinstance(direct, api.FleetMonitorReport)
                        assert observed["exit_code"] == 0 and len(observed["slots"]) == 3
                        assert (
                            direct.cleanup["closed_pools"]
                            == observed["cleanup"]["closed_pools"]
                            == 6
                        )
                        assert all(
                            len(row["observations"]) == 2
                            and row["binding"]["identity"]["state"] == "matched"
                            for row in observed["slots"]
                        )
                    elif scope == "saved":
                        assert observed["plan_binding"]["identity"]["state"] == "matched"
                    else:
                        assert observed["outcome"] == "pass"
                    replicas = [f"r{i}" for i in range(1, 4)] if scope == "fleet" else ["root"]
                    if scope != "standalone":
                        assert all(
                            sum(
                                row["route"] == route and row["replica"] == replica for row in calls
                            )
                            == 4
                            for replica in replicas
                            for route in routes
                        ), calls
                    assert all(
                        row["authorized"] and row["client_certificate"] == mtls for row in calls
                    )
                    controls.append(
                        {
                            "backend": backend,
                            "mode": "bearer-privateCA-mTLS" if mtls else "bearer-privateCA",
                            "scope": scope,
                            "api_exit": 0,
                            "cli_exit": 0,
                            "declared_slots": len(replicas),
                            "metadata_brackets": scope != "standalone",
                            "authorized_routes": len(calls),
                        }
                    )
                assert proxy_calls == [] and not keylog.exists()
                encrypted = [
                    "monitor",
                    "--backend",
                    backend,
                    "--url",
                    url,
                    "--model",
                    model,
                    "--ttft-slo",
                    "500",
                    "--json",
                    "--ca-bundle",
                    str(paths["ca"]),
                    "--client-cert",
                    str(paths["client"]),
                    "--client-key",
                    str(paths["encrypted_key"]),
                ]
                before = len(calls)
                refused = json.loads(run_cli(encrypted, cwd, child_env, 1))
                assert (
                    refused == {"error": "invalid or unavailable monitor TLS configuration"}
                    and len(calls) == before
                )
                negative_controls.extend(
                    _reject_transports(
                        cwd, child_env, paths, backend, model, url, calls, mtls, options
                    )
                )
    assert saved.read_bytes() == original
    return {
        "scope": "owned CPU TLS protocol fixtures; no real serving engine/GPU qualification",
        "controls": controls,
        "negative_controls": negative_controls,
        "encrypted_key_cli": "noninteractive refusal; zero contacts",
        "proxy_contacts": 0,
        "implicit_keylog_created": False,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_bytes_unchanged": True,
        "fixture_resources": "closed",
        "physical_identity": "unverified",
        "runtime_capacity": "unverified",
    }


def _reject_transports(
    cwd: Path,
    env: dict[str, str],
    paths: dict[str, Path],
    backend: str,
    model: str,
    url: str,
    calls: list[dict[str, Any]],
    mtls: bool,
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    from ci_installed_acceptance import run_cli
    from chimeraforge.monitor import MonitorError, MonitorRequest, run_monitor
    from chimeraforge.monitor_connection import MonitorConnection

    controls = []
    for fault in ("wrong-ca", "missing-client" if mtls else "wrong-bearer"):
        bad_options = dict(options)
        bad_cli = [
            "monitor",
            "--backend",
            backend,
            "--url",
            url,
            "--model",
            model,
            "--ttft-slo",
            "500",
            "--interval",
            ".01",
            "--json",
        ]
        if fault == "wrong-ca":
            bad_options["ca_bundle"] = paths["wrong_ca"]
            bad_cli += [
                "--ca-bundle",
                str(paths["wrong_ca"]),
                "--bearer-env",
                "CF_FIXTURE_TOKEN_78",
            ]
            if mtls:
                bad_cli += [
                    "--client-cert",
                    str(paths["client"]),
                    "--client-key",
                    str(paths["client_key"]),
                ]
        elif fault == "missing-client":
            bad_options.pop("client_cert")
            bad_options.pop("client_key")
            bad_cli += ["--ca-bundle", str(paths["ca"]), "--bearer-env", "CF_FIXTURE_TOKEN_78"]
        else:
            bad_options["bearer_token"] = "WrongFixtureToken_78"
            bad_cli += ["--ca-bundle", str(paths["ca"]), "--bearer-env", "CF_WRONG_TOKEN_78"]
        connection = MonitorConnection(url, **bad_options)
        before = len(calls)
        try:
            run_monitor(
                MonitorRequest(backend, url, model, ttft_slo=500, interval=0.01),
                connection=connection,
            )
        except MonitorError as exc:
            assert str(exc) == "secure metrics observation unavailable"
        else:
            raise AssertionError("invalid secure transport unexpectedly passed")
        failed = json.loads(
            run_cli(bad_cli, cwd, dict(env, CF_WRONG_TOKEN_78="WrongFixtureToken_78"), 1)
        )
        assert failed == {"error": "secure metrics observation unavailable"}
        if fault != "wrong-bearer":
            assert len(calls) == before
        else:
            assert len(calls) == before + 2 and all(not row["authorized"] for row in calls[before:])
        controls.append(
            {
                "backend": backend,
                "mtls": mtls,
                "fault": fault,
                "api": "categorical error",
                "cli_exit": 1,
                "http_contacts": len(calls) - before,
            }
        )
    return controls


def certificates(cwd: Path) -> dict[str, Path]:
    """Generate ephemeral protocol-only keys, including independent wrong-CA controls."""
    cwd.mkdir(parents=True, exist_ok=True)
    paths = {}

    def issue(
        name: str,
        ca: tuple[Any, Any] | None = None,
        *,
        client: bool = False,
        wrong_host: bool = False,
    ) -> tuple[Any, Any]:
        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
        now = datetime.now(timezone.utc)
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca[1].subject if ca else subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=ca is None, path_length=None), critical=True)
        )
        if ca:
            purpose = ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH
            builder = builder.add_extension(x509.ExtendedKeyUsage([purpose]), critical=False)
            if not client:
                names: list[x509.GeneralName] = (
                    [x509.DNSName("wrong.example")]
                    if wrong_host
                    else [
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    ]
                )
                builder = builder.add_extension(x509.SubjectAlternativeName(names), critical=False)
        cert = builder.sign(ca[0] if ca else key, hashes.SHA256())
        paths[name] = cwd / (name + ".pem")
        paths[name + "_key"] = cwd / (name + "-key.pem")
        paths[name].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        paths[name + "_key"].write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        return key, cert

    ca = issue("ca")
    wrong = issue("wrong_ca")
    issue("server", ca)
    issue("wrong_host", ca, wrong_host=True)
    client, _ = issue("client", ca, client=True)
    issue("wrong_client", wrong, client=True)
    paths["encrypted_key"] = cwd / "encrypted-key.pem"
    paths["encrypted_key"].write_bytes(
        client.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b"fixture-only-passphrase"),
        )
    )
    return paths


def histogram(backend: str, model: str, count: int, *, slow: bool = False) -> bytes:
    name = (
        "vllm:time_to_first_token_seconds"
        if backend == "vllm"
        else "sglang:time_to_first_token_seconds"
    )
    label = "model_name" if backend == "vllm" else "model_name"
    labels = f"{label}={json.dumps(model)}"
    rows = [f"# TYPE {name} histogram"]
    rows += [
        f'{name}_bucket{{{labels},le="{edge}"}} {0 if slow and edge == "0.1" else count}'
        for edge in ("0.1", "0.5", "1.0", "+Inf")
    ]
    rows += [
        f"{name}_count{{{labels}}} {count}",
        f"{name}_sum{{{labels}}} {count * (0.2 if slow else 0.05)}",
    ]
    return ("\n".join(rows) + "\n").encode()


@contextmanager
def server(
    paths: dict[str, Path],
    *,
    backend: str = "vllm",
    model: str = "ci/manual-fleet",
    token: str | None = None,
    mtls: bool = False,
    wrong_host: bool = False,
    redirect: str | None = None,
    quant: str = "float16",
    deny_metadata: bool = False,
    slow: bool = False,
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Observe authorized route counts only; never retain headers or credential values."""
    calls: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            prefix, _, route = self.path.strip("/").partition("/")
            if prefix not in ("r1", "r2", "r3"):
                route, prefix = self.path.strip("/"), "root"
            authorized = token is None or self.headers.get("Authorization") == "Bearer " + token
            if deny_metadata and route != "metrics":
                authorized = False
            calls.append(
                {
                    "route": route,
                    "replica": prefix,
                    "authorized": authorized,
                    "client_certificate": bool(self.connection.getpeercert())
                    if isinstance(self.connection, ssl.SSLSocket)
                    else False,
                }
            )
            if not authorized:
                code, body = 401, b"{}"
            elif redirect:
                self.send_response(307)
                self.send_header("Location", redirect)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            elif route == "metrics":
                count = counts.get(prefix, 0)
                counts[prefix] = count + 1
                code, body = 200, histogram(backend, model, 100 + count * 20, slow=slow)
            else:
                data: dict[str, Any]
                if route == "version":
                    data = {"version": "0.30.0"}
                elif route == "v1/models":
                    data = {"data": [{"id": model}]}
                elif route.startswith("server_info") or route == "get_server_info":
                    data = {"version": "0.5.20", "dtype": quant, "tp_size": 2, "pp_size": 1}
                    if backend == "vllm":
                        data = {
                            "vllm_config": {
                                "model_config": {"dtype": quant, "max_model_len": 2048},
                                "parallel_config": {
                                    "tensor_parallel_size": 2,
                                    "pipeline_parallel_size": 1,
                                    "data_parallel_size": 1,
                                },
                            }
                        }
                elif route == "model_info":
                    data = {"served_model_name": model}
                else:
                    self.send_error(404)
                    return
                code, body = 200, json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    listener = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    listener.daemon_threads = False
    listener.block_on_close = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    identity = "wrong_host" if wrong_host else "server"
    context.load_cert_chain(paths[identity], paths[identity + "_key"])
    if mtls:
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=paths["ca"])
    listener.socket = context.wrap_socket(listener.socket, server_side=True)
    worker = threading.Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield f"https://127.0.0.1:{listener.server_port}", calls
    finally:
        listener.shutdown()
        listener.server_close()
        worker.join(FIXTURE_JOIN_SECONDS)
        assert not worker.is_alive(), "secure protocol fixture server did not close"


def main() -> int:
    """Regenerate aggregate protocol observations without installed/GPU claims."""
    import argparse
    import hashlib
    import os
    import tempfile

    from chimeraforge import __version__, api

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-secure-monitor-") as temporary:
        cwd = Path(temporary)
        artifact = api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                latency_slo=10000,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        )
        saved = cwd / "saved.json"
        artifact.save(saved)
        result = accept(cwd, dict(os.environ), saved)
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "scripts/ci_secure_monitor.py",
        root / "src/chimeraforge/monitor_connection.py",
        root / "src/chimeraforge/monitor.py",
        root / "src/chimeraforge/plan_monitor.py",
        root / "src/chimeraforge/fleet_monitor.py",
        root / "src/chimeraforge/fleet_monitor_transport.py",
    ]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "evidence": (
            "source CLI/API on owned CPU TLS fixtures; "
            "no installed-distribution or GPU qualification"
        ),
        "result": result,
        "source_sha256": {
            str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in files
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"controls": len(result["controls"]), "fixture_resources": result["fixture_resources"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
