"""Owned hosted kind observations; genuine GPU declarations must remain pending."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import ssl
import sys
import threading
from typing import Any, Callable, cast
from unittest.mock import patch
import uuid
from xml.etree import ElementTree as ET

PRIVATE = "native-inspection-private-canary"
OWNER_LABEL = "org.chimeraforge.inspection-owner"


@contextmanager
def no_contact_server(paths: dict[str, Path]) -> Iterator[tuple[str, dict[str, int]]]:
    counts = {"requests": 0, "static_version_requests": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            counts["requests"] += 1
            if (
                self.command == "GET"
                and self.path.partition("?")[0] == "/version"
                and self.headers.get("Authorization") == "Bearer " + PRIVATE
            ):
                counts["static_version_requests"] += 1
            body = (
                b'{"apiVersion":"v1","kind":"Status","status":"Failure",'
                b'"reason":"NotFound","code":404}'
            )
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_POST = do_GET

        def log_message(self, format: str, *args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(paths["server"], paths["server_key"])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}", counts
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def _private_config(
    path: Path, server: str, users: list[dict], selected: str, *, ca: str | None = None
) -> None:
    cluster = {"server": server}
    if ca is not None:
        cluster["certificate-authority"] = ca
    value = {
        "apiVersion": "v1",
        "kind": "Config",
        "preferences": {},
        "clusters": [{"name": "fixture", "cluster": cluster}],
        "users": users,
        "contexts": [
            {
                "name": user["name"],
                "context": {
                    "cluster": "fixture",
                    "user": user["name"],
                    "namespace": "ambient-not-selected",
                },
            }
            for user in users
        ],
        "current-context": selected,
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _policy_controls(
    work: Path,
    env: dict,
    run: Callable[..., str],
    executable: str,
    observe: Callable[..., Any],
    run_cli: Callable[..., dict],
    controls: list[dict],
    receipt: dict,
) -> None:
    from ci_secure_monitor import certificates

    tls = certificates(work / "credential-policy-tls")
    with no_contact_server(tls) as (address, counter):
        receipt["phase"] = "native_credential_policy_and_context_projections"
        script, marker = work / "credential-plugin.py", work / "credential-plugin-ran"
        script.write_text(
            "from pathlib import Path\nPath("
            + repr(str(marker))
            + ").write_text('executed')\nprint("
            + repr(
                json.dumps(
                    {
                        "apiVersion": "client.authentication.k8s.io/v1",
                        "kind": "ExecCredential",
                        "status": {"token": PRIVATE},
                    }
                )
            )
            + ")\n",
            encoding="utf-8",
        )
        plugin: dict[str, Any] = {
            "name": "plugin",
            "user": {
                "exec": {
                    "apiVersion": "client.authentication.k8s.io/v1",
                    "interactiveMode": "Never",
                    "command": sys.executable,
                    "args": [str(script)],
                }
            },
        }
        oidc: dict[str, Any] = {
            "name": "oidc",
            "user": {
                "auth-provider": {
                    "name": "oidc",
                    "config": {
                        "idp-issuer-url": address,
                        "client-id": "fixture",
                        "refresh-token": PRIVATE,
                    },
                }
            },
        }
        config = work / "credential-policy.json"
        _private_config(config, address, [plugin], "plugin", ca=str(tls["ca"]))
        allow = work / "owned-positive-kuberc.json"
        allow.write_text(
            json.dumps(
                {
                    "apiVersion": "kubectl.config.k8s.io/v1beta1",
                    "kind": "Preference",
                    "credentialPluginPolicy": "AllowAll",
                }
            ),
            encoding="utf-8",
        )
        home = work / "positive-exec-home"
        home.mkdir()
        (home / ".kube").mkdir()
        legacy = home / ".kube" / ".kubeconfig"
        legacy.write_text('{"apiVersion":"v1","kind":"Config"}', encoding="utf-8")
        positive = {
            key: value
            for key, value in env.items()
            if key.upper()
            not in {"HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "KUBERC", "KUBECTL_KUBERC"}
        }
        positive.update(HOME=str(home), USERPROFILE=str(home), KUBECTL_KUBERC="true")
        run(
            [
                executable,
                "--kubeconfig",
                str(config),
                "--context",
                "plugin",
                "--kuberc",
                str(allow),
                "--cache-dir",
                str(work / "positive-exec-cache"),
                "--request-timeout=10s",
                "version",
                "--output=json",
            ],
            positive,
            negative=True,
        )
        assert marker.exists() and counter["requests"] > 0
        assert (home / ".kube" / "config").read_bytes() == legacy.read_bytes()
        controls.append(
            {
                "control": "owned_native_exec_positive_outside_product",
                "helper_executed": True,
                "tls_contacts_observed": True,
                "native_legacy_migration_positive": True,
            }
        )
        marker.unlink()
        counter["requests"] = 0
        poison = {**env, "KUBERC": "off", "KUBECTL_KUBERC": "false"}
        for user in (plugin, oidc):
            _private_config(config, address, [user], user["name"], ca=str(tls["ca"]))
            before = config.read_bytes()
            with patch.dict(os.environ, {"KUBERC": "off", "KUBECTL_KUBERC": "false"}):
                result = observe(config=config, selected=user["name"])
            assert result.exit_code == 4 and counter["requests"] == 0 and not marker.exists()
            if user["name"] == "oidc":
                assert result._data["preflight"]["reason"] == "legacy_auth_provider_unsupported"
                assert result._data["budget"]["processes"] == 2
                assert not result._data["preflight"]["private_projection_complete"]
            else:
                assert result._data["preflight"]["private_projection_complete"]
                assert result._data["budget"]["processes"] == 5
            command = run_cli(code=4, config=config, selected=user["name"], child_env=poison)
            assert (
                counter["requests"] == 0 and not marker.exists() and config.read_bytes() == before
            )
            assert len(command["resources"]) == 6 and PRIVATE not in result.json_bytes().decode()
            controls.append(
                {
                    "control": user["name"] + "_zero_contact",
                    "api_exit": 4,
                    "cli_exit": 4,
                    "contacts": 0,
                }
            )

        def retain_context(control: str, interface: str, report: dict) -> None:
            safe = {
                "control": control,
                "interface": interface,
                "exit_code": report["exit_code"],
                **{name: deepcopy(report[name]) for name in ("preflight", "budget", "cleanup")},
                "contacts": dict(counter),
            }
            assert PRIVATE not in json.dumps(safe)
            controls.append(safe)

        _private_config(
            config, address, [{"name": "static", "user": {}}, oidc], "oidc", ca=str(tls["ca"])
        )
        before = config.read_bytes()
        counter.update(requests=0, static_version_requests=0)
        empty_user = observe(config=config, selected="static")
        retain_context("empty_user_closed_stdin", "api", empty_user.to_dict())
        assert empty_user.exit_code == 4
        assert empty_user._data["preflight"]["private_projection_complete"]
        assert counter["requests"] == 0 and config.read_bytes() == before
        deny = work / "owned-empty-user-kuberc.json"
        deny.write_text(
            json.dumps(
                {
                    "apiVersion": "kubectl.config.k8s.io/v1beta1",
                    "kind": "Preference",
                    "credentialPluginPolicy": "DenyAll",
                }
            ),
            encoding="utf-8",
        )
        private_output = run(
            [
                executable,
                "--kubeconfig",
                str(config),
                "--context",
                "static",
                "--kuberc",
                str(deny),
                "--cache-dir",
                str(work / "empty-user-cache"),
                "--request-timeout=10s",
                "version",
                "--output=json",
            ],
            positive,
            negative=True,
        )
        prompt_seen = private_output.startswith("Please enter Username: ")
        del private_output
        controls.append(
            {
                "control": "native_empty_user_closed_stdin",
                "prompt_observed": prompt_seen,
                "contacts": dict(counter),
            }
        )
        assert prompt_seen and counter["requests"] == 0 and not marker.exists()
        assert config.read_bytes() == before

        _private_config(
            config,
            address,
            [{"name": "static", "user": {"token": PRIVATE}}, oidc],
            "oidc",
            ca=str(tls["ca"]),
        )
        before = config.read_bytes()
        counter.update(requests=0, static_version_requests=0)
        selected_static = observe(config=config, selected="static")
        retain_context(
            "explicit_context_excludes_unused_provider", "api", selected_static.to_dict()
        )
        assert selected_static.exit_code == 4
        assert selected_static._data["preflight"]["private_projection_complete"]
        assert counter["static_version_requests"] > 0 and counter["requests"] > 0
        assert config.read_bytes() == before and not marker.exists()
        counter.update(requests=0, static_version_requests=0)
        selected_cli = run_cli(code=4, config=config, selected="static")
        retain_context("explicit_context_excludes_unused_provider", "cli", selected_cli)
        assert selected_cli["preflight"]["private_projection_complete"]
        assert counter["static_version_requests"] > 0 and counter["requests"] > 0
        assert config.read_bytes() == before and not marker.exists()


def accept(
    kube: list[str],
    env: dict,
    cases: list[dict],
    work: Path,
    run: Callable[..., str],
    receipt: dict,
) -> dict:
    from chimeraforge import api, deploy

    executable = kube[0]
    original_config = Path(kube[kube.index("--kubeconfig") + 1])
    context = kube[kube.index("--context") + 1]
    owner = uuid.uuid4().hex
    namespace = "cf-inspection-" + owner[:12]
    controls: list[dict] = []
    interfaces: list[dict] = []
    receipt.update(interfaces=interfaces, controls=controls, phase="admitting_owned_namespace")
    inputs = {case["saved"]: case["saved"].read_bytes() for case in cases}
    inputs[original_config] = original_config.read_bytes()
    created = False
    failure: BaseException | None = None
    cleanup: dict[str, Any] = {"state": "not_started"}
    caller_home = work / "caller-home-canary"
    (caller_home / ".kube").mkdir(parents=True)
    legacy = caller_home / ".kube" / ".kubeconfig"
    legacy.write_text('{"apiVersion":"v1","kind":"Config"}', encoding="utf-8")
    legacy_bytes = legacy.read_bytes()
    caller_settings = {"HOME": str(caller_home), "USERPROFILE": str(caller_home)}
    assert (
        run(
            [*kube, "get", "namespace", namespace, "--ignore-not-found=true", "-o", "name"], env
        ).strip()
        == ""
    )

    def admin(args: list[str], **kwargs: Any) -> str:
        return run([*kube, "--namespace", namespace, *args], env, **kwargs)

    def apply(value: dict, name: str) -> None:
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        admin(
            [
                "apply",
                "--server-side",
                "--field-manager=chimeraforge-inspection-ci",
                "-f",
                str(path),
                "--request-timeout=30s",
            ]
        )

    def api_call(
        case: dict,
        options: api.KubernetesOptions,
        *,
        config: Path = original_config,
        selected: str = context,
    ) -> api.KubernetesInspection:
        with patch.dict(os.environ, caller_settings):
            result = asyncio.run(
                api.inspect_kubernetes_deployment(
                    case["saved"],
                    image=case["image"],
                    candidate_index=case["index"],
                    kubernetes=options,
                    kubeconfig=config,
                    context=selected,
                    kubectl=executable,
                    timeout_s=30,
                )
            )
        assert (
            legacy.read_bytes() == legacy_bytes and not (caller_home / ".kube" / "config").exists()
        )
        return result

    def cli(
        case: dict,
        options: api.KubernetesOptions,
        *,
        code: int,
        config: Path = original_config,
        selected: str = context,
        out: Path | None = None,
        junit: Path | None = None,
        child_env: dict | None = None,
    ) -> dict:
        assert options.name_prefix is not None
        args = [
            sys.executable,
            "-I",
            "-m",
            "chimeraforge",
            "deploy-inspect",
            "--plan",
            str(case["saved"]),
            "--image",
            case["image"],
            "--candidate-index",
            str(case["index"]),
            "--kubeconfig",
            str(config),
            "--context",
            selected,
            "--kubectl",
            executable,
            "--namespace",
            options.namespace,
            "--name-prefix",
            options.name_prefix,
            "--json",
        ]
        for key, value in options.node_selector.items():
            args.extend(["--node-selector", f"{key}={value}"])
        if out is not None:
            args.extend(["--out", str(out)])
        if junit is not None:
            args.extend(["--junit", str(junit)])
        runtime_env = {**(env if child_env is None else child_env), **caller_settings}
        text = run(args, runtime_env, expected_code=code)
        assert (
            legacy.read_bytes() == legacy_bytes and not (caller_home / ".kube" / "config").exists()
        )
        assert PRIVATE not in text
        return cast(dict, json.loads(text))

    try:
        created = True
        apply(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": namespace, "labels": {OWNER_LABEL: owner}},
            },
            "inspection-namespace.json",
        )
        selected_cases = [case for case in cases if case["n"] == 3]
        assert [case["backend"] for case in selected_cases] == ["vllm", "sglang"]
        live: list[tuple[dict, api.KubernetesOptions, dict]] = []
        for case in selected_cases:
            receipt["phase"] = "original_gpu_intent_and_pending_rollout"
            options = api.KubernetesOptions(
                namespace=namespace,
                name_prefix=f"observe-{case['backend']}",
                node_selector=case["options"].node_selector,
            )
            manifest = json.loads(
                deploy.export_deployment(
                    api.load_plan(case["saved"]),
                    format="kubernetes",
                    image=case["image"],
                    candidate_index=case["index"],
                    kubernetes=options,
                ).content
            )
            assert len(manifest["items"]) == 6
            assert all(
                row["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"][
                    "nvidia.com/gpu"
                ]
                == "2"
                for row in manifest["items"]
                if row["kind"] == "Deployment"
            )
            if not live:
                empty = api_call(case, options)
                assert empty.exit_code == 5 and len(empty.resources) == 6
                assert all(row["intent"]["state"] == "missing" for row in empty.resources)
                controls.append(
                    {"control": "empty_owned_namespace", "exit_code": 5, "resources": 6}
                )
            apply(manifest, f"inspection-{case['backend']}.json")
            live.append((case, options, manifest))
            direct = api_call(case, options)
            out, junit = (
                work / f"inspect-{case['backend']}.json",
                work / f"inspect-{case['backend']}.xml",
            )
            api.write_kubernetes_inspection(direct, out=out, junit=junit)
            command = cli(case, options, code=4)
            for interface, report in (("api", direct.to_dict()), ("cli", command)):
                interfaces.append(
                    {"backend": case["backend"], "interface": interface, "report": report}
                )
                assert report["exit_code"] == 4 and len(report["resources"]) == 6
                assert all(row["intent"]["state"] == "match" for row in report["resources"]), report
                assert all(
                    row["rollout"]["state"]
                    == ("pending" if row["kind"] == "Deployment" else "not_requested")
                    for row in report["resources"]
                )
                assert (
                    report["cleanup"]["state"] == "completed"
                    and report["cleanup"]["runtime_files_closed"]
                )
                assert (
                    report["cleanup"]["owned_processes"]
                    == report["cleanup"]["closed_processes"]
                    == 11
                )
                assert str(original_config) not in json.dumps(report)
            assert len(ET.fromstring(junit.read_bytes()).findall("testcase")) == 10
        case, options, manifest = live[0]
        for fault in ("image", "argv", "selector", "addition"):
            receipt["phase"] = "known_intent_drift"
            changed = deepcopy(manifest)
            pod = changed["items"][0]["spec"]["template"]["spec"]
            container = pod["containers"][0]
            if fault == "image":
                container["image"] = "example/changed:1"
            elif fault == "argv":
                container["args"].append("--changed-intent")
            elif fault == "selector":
                pod["nodeSelector"]["operator.example/accelerator"] = "changed"
            else:
                container["env"] = [{"name": PRIVATE.replace("-", "_").upper(), "value": PRIVATE}]
            apply(changed, f"inspection-drift-{fault}.json")
            result = api_call(case, options)
            assert result.exit_code == 5 and len(result.resources) == 6
            assert PRIVATE not in result.json_bytes().decode()
            controls.append({"control": fault, "exit_code": 5, "resources": 6})
            apply(manifest, "inspection-restore.json")
        missing_name = manifest["items"][1]["metadata"]["name"]
        receipt["phase"] = "successful_missing_resource"
        admin(["delete", "service", missing_name, "--wait=true", "--request-timeout=30s"])
        missing = api_call(case, options)
        assert missing.exit_code == 5 and missing.resources[1]["intent"]["state"] == "missing"
        controls.append({"control": "missing_service", "exit_code": 5, "resources": 6})
        apply(manifest, "inspection-restore.json")

        pods = json.loads(admin(["get", "pods", "-o", "json"]))["items"]
        assert all(not pod["spec"].get("nodeName") for pod in pods)
        assert all(not pod.get("status", {}).get("containerStatuses") for pod in pods)
        controls.append(
            {"control": "genuine_gpu_fixture_remains_unscheduled", "pods_observed": len(pods)}
        )

        # Generate an owned restricted token; never read/copy kind's private client key.
        receipt["phase"] = "restricted_static_auth_and_lexical_file_guards"
        apply(
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "restricted", "namespace": namespace},
            },
            "inspection-sa.json",
        )
        token = admin(["create", "token", "restricted", "--duration=10m"]).strip()
        assert token and not any(char.isspace() for char in token)
        public_ca = run(
            [
                *kube,
                "config",
                "view",
                "--minify=true",
                "--raw=true",
                "--flatten=false",
                "-o",
                "jsonpath={.clusters[0].cluster.certificate-authority-data}",
            ],
            env,
        ).strip()
        server = run(
            [
                *kube,
                "config",
                "view",
                "--minify=true",
                "--raw=false",
                "--flatten=false",
                "-o",
                "jsonpath={.clusters[0].cluster.server}",
            ],
            env,
        ).strip()
        assert server.startswith("https://127.0.0.1:")
        ca, credential = work / "lexical.ca", work / "lexical.token"
        ca.write_bytes(base64.b64decode(public_ca, validate=True))
        credential.write_text(token, encoding="utf-8")
        credential.chmod(0o600)
        target = work / "cfg-target"
        target.mkdir()
        (target / ca.name).write_bytes(b"wrong-target-parent-canary")
        (target / credential.name).write_bytes(b"wrong-target-parent-canary")
        target_config = target / "config"
        _private_config(
            target_config,
            server,
            [{"name": "restricted", "user": {"tokenFile": credential.name}}],
            "restricted",
            ca=ca.name,
        )
        linked_config = work / "lexical-config"
        linked_config.symlink_to(target_config)
        inputs.update({path: path.read_bytes() for path in (ca, credential, target_config)})
        denied = api_call(case, options, config=linked_config, selected="restricted")
        assert denied.exit_code == 4 and denied._data["preflight"]["complete"]
        assert all(row["intent"]["state"] == "unknown" for row in denied.resources)
        assert {ca, credential} <= set(denied._input_paths)
        rejection = run(
            [
                executable,
                "--kubeconfig",
                str(linked_config),
                "--context",
                "restricted",
                "--namespace",
                namespace,
                "get",
                "deployments.apps",
                manifest["items"][0]["metadata"]["name"],
                "--request-timeout=10s",
            ],
            env,
            negative=True,
        )
        assert "Forbidden" in rejection and token not in rejection
        alias = work / "token-hardlink"
        os.link(credential, alias)
        cli(case, options, code=2, config=linked_config, selected="restricted", out=alias)
        assert credential.read_text(encoding="utf-8") == token
        controls.extend(
            [
                {"control": "restricted_sa_native_denial", "exit_code": 4},
                {"control": "relative_symlink_hardlink_output_guard", "exit_code": 2},
            ]
        )

        from functools import partial

        _policy_controls(
            work,
            env,
            run,
            executable,
            partial(api_call, case, options),
            partial(cli, case, options),
            controls,
            receipt,
        )
        assert all(path.read_bytes() == raw for path, raw in inputs.items())
        assert (
            legacy.read_bytes() == legacy_bytes and not (caller_home / ".kube" / "config").exists()
        )
        assert PRIVATE not in json.dumps(interfaces)
        receipt.update(
            {
                "interfaces": interfaces,
                "controls": controls,
                "original_n": 3,
                "intent_resources_per_invocation": 6,
                "junit_cases": 10,
                "source_and_private_input_bytes_unchanged": True,
                "caller_legacy_home_unchanged_and_target_absent": True,
                "scope": (
                    "Owned CPU kind API observations; genuine GPU requests, matching intent/"
                    "pending rollout4. No scheduling, inference-image pull, GPU "
                    "or capacity qualification."
                ),
            }
        )
    except BaseException as exc:
        failure = exc
    finally:
        if created:
            try:
                found = json.loads(run([*kube, "get", "namespace", namespace, "-o", "json"], env))
                assert found["metadata"]["labels"][OWNER_LABEL] == owner
                run(
                    [*kube, "delete", "namespace", namespace, "--wait=true", "--timeout=60s"],
                    env,
                    timeout=90,
                )
                absent = (
                    run(
                        [
                            *kube,
                            "get",
                            "namespace",
                            namespace,
                            "--ignore-not-found=true",
                            "-o",
                            "name",
                        ],
                        env,
                    ).strip()
                    == ""
                )
                cleanup = {
                    "state": "completed" if absent else "incomplete",
                    "owned_namespace_deleted": absent,
                }
            except BaseException as exc:
                cleanup = {"state": "incomplete", "error": type(exc).__name__}
        receipt["cleanup"] = cleanup
        if failure is not None:
            raise failure
        if cleanup["state"] != "completed":
            raise RuntimeError("owned inspection fixture cleanup incomplete")
    receipt["phase"] = "complete"
    return receipt
