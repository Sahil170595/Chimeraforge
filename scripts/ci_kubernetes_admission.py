"""Pinned hosted CPU API admission; never persists an inference workload."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Callable
from urllib.request import urlopen
import uuid

KIND_VERSION = "v0.33.0"
KUBECTL_VERSION = "v1.37.1"
SERVER_VERSION = "v1.37.0"
KIND_SHA256 = "aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d"
KUBECTL_SHA256 = "65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8"
NODE_IMAGE = (
    "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
)
CLUSTER = "cf-admission"
OWNER_LABEL = "org.chimeraforge.ci-owner"
MAX_TOOL_BYTES = 128 * 1024 * 1024
MAX_COMMAND_BYTES = 8 * 1024 * 1024
COMMAND_CLEANUP: list[dict] = []


def download(url: str, path: Path, digest: str) -> None:
    with urlopen(url, timeout=30) as response:
        raw = response.read(MAX_TOOL_BYTES + 1)
    assert len(raw) <= MAX_TOOL_BYTES and hashlib.sha256(raw).hexdigest() == digest
    path.write_bytes(raw)
    path.chmod(0o700)


def run(argv: list[str], env: dict, *, timeout: float = 60, negative: bool = False) -> str:
    from ci_cpu_fleet import close_groups

    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env=env,
            start_new_session=True,
        )
        failure: BaseException | None = None
        try:
            process.wait(timeout=timeout)
        except BaseException as exc:
            failure = exc
        finally:
            closed = close_groups([process], [])
            COMMAND_CLEANUP.append(closed)
        if failure is not None:
            raise failure
        assert closed["state"] == "completed", closed
        stdout.seek(0)
        stderr.seek(0)
        out, err = stdout.read(MAX_COMMAND_BYTES + 1), stderr.read(MAX_COMMAND_BYTES + 1)
        assert len(out) <= MAX_COMMAND_BYTES and len(err) <= MAX_COMMAND_BYTES
        if negative:
            assert process.returncode != 0, "negative server validation unexpectedly succeeded"
            return (out + err).decode("utf-8", errors="strict")
        assert process.returncode == 0, (
            Path(argv[0]).name,
            process.returncode,
            err.decode("utf-8", errors="replace"),
        )
        return out.decode("utf-8", errors="strict")


def _subset(expected: object, actual: object) -> None:
    if type(expected) is dict:
        assert type(actual) is dict
        for key, value in expected.items():
            assert key in actual, key
            _subset(value, actual[key])
    elif type(expected) is list:
        assert type(actual) is list and len(actual) == len(expected)
        for before, after in zip(expected, actual):
            _subset(before, after)
    else:
        assert type(expected) is type(actual) and expected == actual, (
            "server changed a declared field"
        )


def validate_response(expected: dict, actual: dict) -> None:
    assert actual["apiVersion"] == "v1" and actual["kind"] == "List"
    assert len(actual["items"]) == len(expected["items"])

    def identity(item: dict) -> tuple[str, str, str]:
        return item["kind"], item["metadata"]["namespace"], item["metadata"]["name"]

    by_id = {identity(item): item for item in actual["items"]}
    assert len(by_id) == len(actual["items"])
    assert set(by_id) == {identity(item) for item in expected["items"]}
    for item in expected["items"]:
        _subset(item, by_id[identity(item)])


def owned_cluster(
    work: Path,
    env: dict,
    kind: str,
    kubectl: str,
    receipt: dict,
    check: Callable[[list[str], dict], None],
) -> None:
    owner = str(uuid.uuid4())
    private = {
        **env,
        "KUBECONFIG": str(work / "kubeconfig"),
        "KIND_EXPERIMENTAL_PROVIDER": "docker",
    }
    private.pop("KIND_EXPERIMENTAL_DOCKER_NETWORK", None)
    clusters = run([kind, "get", "clusters"], private).splitlines()
    if CLUSTER in clusters:
        raise RuntimeError("refusing preexisting admission cluster")
    ids = run(
        ["docker", "network", "ls", "--filter", "name=^kind$", "--no-trunc", "--format", "{{.ID}}"],
        env,
    ).split()
    if len(ids) > 1:
        raise RuntimeError("refusing duplicate kind networks")
    network = ids[0] if ids else None
    created_network = False
    create_intent = False
    failure: BaseException | None = None
    errors: list[str] = []
    config = work / "kind.json"
    config.write_text(
        json.dumps(
            {
                "kind": "Cluster",
                "apiVersion": "kind.x-k8s.io/v1alpha4",
                "networking": {"ipFamily": "ipv4", "apiServerAddress": "127.0.0.1"},
                "nodes": [{"role": "control-plane"}],
            }
        ),
        encoding="utf-8",
    )
    receipt["network"] = {"preexisting_id": network, "created_id": None, "owner": owner}
    try:
        if network is None:
            # Native kind reuses an ordinary existing bridge; no unsupported override.
            created_network = True
            network = run(
                [
                    "docker",
                    "network",
                    "create",
                    "--driver",
                    "bridge",
                    "--label",
                    f"{OWNER_LABEL}={owner}",
                    "--opt",
                    "com.docker.network.bridge.enable_ip_masquerade=true",
                    "kind",
                ],
                env,
            ).strip()
            assert network
            receipt["network"]["created_id"] = network
        else:
            observed = json.loads(run(["docker", "network", "inspect", network], env))[0]
            assert observed["Id"] == network and observed["Name"] == "kind"
        create_intent = True
        receipt["cluster_creation_intent"] = CLUSTER
        run(
            [
                kind,
                "create",
                "cluster",
                "--name",
                CLUSTER,
                "--image",
                NODE_IMAGE,
                "--config",
                str(config),
                "--kubeconfig",
                private["KUBECONFIG"],
                "--wait",
                "120s",
            ],
            private,
            timeout=240,
        )
        kube = [kubectl, "--kubeconfig", private["KUBECONFIG"], "--context", f"kind-{CLUSTER}"]
        check(kube, private)
    except BaseException as exc:
        failure = exc
    finally:
        if create_intent:
            try:
                run(
                    [
                        kind,
                        "delete",
                        "cluster",
                        "--name",
                        CLUSTER,
                        "--kubeconfig",
                        private["KUBECONFIG"],
                    ],
                    private,
                    timeout=120,
                )
            except BaseException as exc:
                errors.append(f"cluster-delete:{type(exc).__name__}")
            for label, command in (
                ("cluster-list", [kind, "get", "clusters"]),
                (
                    "containers",
                    [
                        "docker",
                        "ps",
                        "--all",
                        "--quiet",
                        "--filter",
                        f"label=io.x-k8s.kind.cluster={CLUSTER}",
                    ],
                ),
            ):
                try:
                    value = run(command, private)
                    assert (
                        CLUSTER not in value.splitlines()
                        if label == "cluster-list"
                        else not value.strip()
                    )
                except BaseException as exc:
                    errors.append(f"{label}:{type(exc).__name__}")
        if created_network:
            try:
                # A failed create may have succeeded remotely before losing its output.
                if network is None:
                    found = run(
                        [
                            "docker",
                            "network",
                            "ls",
                            "--filter",
                            f"label={OWNER_LABEL}={owner}",
                            "--no-trunc",
                            "--format",
                            "{{.ID}}",
                        ],
                        env,
                    ).split()
                    assert len(found) <= 1
                    network = found[0] if found else None
                if network is not None:
                    observed = json.loads(run(["docker", "network", "inspect", network], env))[0]
                    assert observed["Id"] == network and observed["Name"] == "kind"
                    assert (
                        observed.get("Labels", {}).get(OWNER_LABEL) == owner
                        and not observed["Containers"]
                    )
                    run(["docker", "network", "rm", network], env)
                    remaining = run(
                        ["docker", "network", "ls", "--no-trunc", "--format", "{{.ID}}"], env
                    ).split()
                    assert network not in remaining
            except BaseException as exc:
                errors.append(f"owned-network:{type(exc).__name__}")
        elif network is not None:
            try:
                observed = json.loads(run(["docker", "network", "inspect", network], env))[0]
                assert observed["Id"] == network and observed["Name"] == "kind"
            except BaseException as exc:
                errors.append(f"preserved-network:{type(exc).__name__}")
        receipt["cleanup"] = {
            "state": "incomplete" if errors else "completed",
            "errors": errors,
            "owned_cluster_deleted": create_intent and not errors,
            "preexisting_network_preserved": not created_network,
        }
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError("owned admission cleanup incomplete")


def fixtures(work: Path, env: dict) -> list[dict]:
    from ci_checkpoint_identity import seed
    from ci_installed_acceptance import run_cli
    from ci_kubernetes_export import IMAGES
    from chimeraforge import api, deploy

    checkpoint = seed(live=False)
    result = []
    for n, rate in ((1, 0.01), (3, 2048)):
        saved = work / f"source-n{n}.json"
        run_cli(
            [
                "plan",
                "--model",
                checkpoint["repo"],
                "--revision",
                checkpoint["commit"],
                "--hardware",
                "RTX 4090 24GB",
                "--platform",
                "linux",
                "--tensor-parallel",
                "2",
                "--request-rate",
                str(rate),
                "--quality-target",
                "0",
                "--budget",
                "100000",
                "--no-network",
                "--save",
                str(saved),
                "--json",
            ],
            work,
            env,
        )
        artifact = api.load_plan(saved)
        source = saved.read_bytes()
        for backend in ("vllm", "sglang"):
            index = next(
                i
                for i, row in enumerate(artifact.to_dict()["result"]["candidates"])
                if row["backend"] == backend and row["quant"] == "FP16" and row["n_agents"] == n
            )
            options = api.KubernetesOptions(
                name_prefix=f"admit-{backend}-n{n}",
                node_selector={"operator.example/accelerator": "declared"},
            )
            manifest = work / f"{backend}-n{n}.json"
            content = deploy.export_deployment(
                artifact,
                format="kubernetes",
                image=IMAGES[backend],
                candidate_index=index,
                kubernetes=options,
            ).content
            manifest.write_text(content, encoding="utf-8", newline="")
            checked = api.verify_deployment(
                saved,
                manifest,
                format="kubernetes",
                image=IMAGES[backend],
                candidate_index=index,
                kubernetes=options,
            )
            assert checked.exit_code == 0
            data = json.loads(content)
            for item in data["items"]:
                if item["kind"] == "Deployment":
                    argv = item["spec"]["template"]["spec"]["containers"][0]["args"]
                    assert argv[argv.index("--revision") + 1] == checkpoint["commit"]
            result.append(
                {
                    "saved": saved,
                    "source": source,
                    "path": manifest,
                    "manifest": data,
                    "backend": backend,
                    "n": n,
                    "index": index,
                    "options": options,
                    "image": IMAGES[backend],
                }
            )
    return result


def accept(kube: list[str], env: dict, cases: list[dict], work: Path, receipt: dict) -> None:
    from chimeraforge import api

    version = json.loads(run([*kube, "version", "-o", "json"], env))
    assert version["clientVersion"]["gitVersion"] == KUBECTL_VERSION
    assert version["serverVersion"]["gitVersion"] == SERVER_VERSION
    nodes = json.loads(run([*kube, "get", "nodes", "-o", "json"], env))
    assert (
        len(nodes["items"]) == 1
        and nodes["items"][0]["status"]["nodeInfo"]["kubeletVersion"] == SERVER_VERSION
    )
    container = json.loads(run(["docker", "inspect", f"{CLUSTER}-control-plane"], env))[0]
    image = json.loads(run(["docker", "image", "inspect", NODE_IMAGE], env))[0]
    expected_digest = "kindest/node@" + NODE_IMAGE.split("@", 1)[1]
    assert container["Image"] == image["Id"] and expected_digest in image["RepoDigests"]
    receipt["versions"] = {
        "client": KUBECTL_VERSION,
        "server": SERVER_VERSION,
        "node": NODE_IMAGE,
        "node_local_image_id": image["Id"],
        "kind": KIND_VERSION,
    }
    controls = receipt["controls"] = []

    def apply(path: Path, *, negative: bool = False) -> str:
        return run(
            [
                *kube,
                "apply",
                "--server-side",
                "--dry-run=server",
                "--validate=strict",
                "--field-manager=chimeraforge-ci",
                "--request-timeout=30s",
                "-f",
                str(path),
                "-o",
                "json",
            ],
            env,
            negative=negative,
        )

    for case in cases:
        validate_response(case["manifest"], json.loads(apply(case["path"])))
        controls.append(
            {
                "backend": case["backend"],
                "original_replicas": case["n"],
                "objects": len(case["manifest"]["items"]),
                "admitted": True,
            }
        )
        assert case["saved"].read_bytes() == case["source"]
    case = cases[-1]
    for fault in ("gpu", "unknown"):
        changed = copy.deepcopy(case["manifest"])
        container = changed["items"][0]["spec"]["template"]["spec"]["containers"][0]
        if fault == "gpu":
            container["resources"]["requests"]["nvidia.com/gpu"] = "1"
        else:
            container["chimeraforgeUnknownField"] = True
        path = work / f"invalid-{fault}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        error = apply(path, negative=True)
        assert (
            ("nvidia.com/gpu" in error and ("equal" in error or "must" in error))
            if fault == "gpu"
            else "unknown field" in error.lower()
        )
    for fault in ("image", "model", "selector"):
        changed = copy.deepcopy(case["manifest"])
        container = changed["items"][0]["spec"]["template"]["spec"]["containers"][0]
        if fault == "image":
            container["image"] = "example/changed:1"
        elif fault == "model":
            args = container["args"]
            position = args.index("--model-path") + 1 if "--model-path" in args else 0
            args[position] = "changed/model"
        else:
            changed["items"][1]["spec"]["selector"]["app.kubernetes.io/instance"] = "changed-member"
        path = work / f"drift-{fault}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        validate_response(changed, json.loads(apply(path)))
        checked = api.verify_deployment(
            case["saved"],
            path,
            format="kubernetes",
            image=case["image"],
            candidate_index=case["index"],
            kubernetes=case["options"],
        )
        assert checked.exit_code == 5
    found = json.loads(
        run(
            [
                *kube,
                "get",
                "deployments,services,pods",
                "--namespace",
                "default",
                "--selector",
                "app.kubernetes.io/managed-by=chimeraforge",
                "-o",
                "json",
                "--request-timeout=30s",
            ],
            env,
        )
    )
    assert found["items"] == []
    receipt.update(
        {
            "server_rejections": ["unequal_gpu", "unknown_field"],
            "admitted_but_native_drift": ["image", "model", "selector"],
            "persisted_feature_objects": 0,
            "source_bytes_unchanged": all(
                case["saved"].read_bytes() == case["source"] for case in cases
            ),
        }
    )
    assert receipt["source_bytes_unchanged"]


def main() -> int:
    from ci_installed_acceptance import assert_installed_origin
    from chimeraforge import __version__, api

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--expect-version", required=True)
    args = parser.parse_args()
    assert_installed_origin(api.__file__, args.checkout)
    assert __version__ == args.expect_version
    receipt: dict = {
        "event": "kubernetes-server-admission",
        "version": __version__,
        "origin": api.__file__,
        "scope": (
            "CPU API dry-run only; no inference-image pull, kubelet argv execution, scheduling, "
            "plugin, GPU, inference or capacity qualification"
        ),
    }
    failure: BaseException | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix="cf-kind-", dir=os.environ["RUNNER_TEMP"]
        ) as temporary:
            work = Path(temporary)
            os.environ["CHIMERAFORGE_CACHE"] = str(work / "cache")
            env = dict(os.environ)
            kind, kubectl = work / "kind", work / "kubectl"
            download(
                f"https://github.com/kubernetes-sigs/kind/releases/download/{KIND_VERSION}/kind-linux-amd64",
                kind,
                KIND_SHA256,
            )
            download(
                f"https://dl.k8s.io/release/{KUBECTL_VERSION}/bin/linux/amd64/kubectl",
                kubectl,
                KUBECTL_SHA256,
            )
            assert KIND_VERSION in run([str(kind), "version"], env)
            cases = fixtures(work, env)
            owned_cluster(
                work,
                env,
                str(kind),
                str(kubectl),
                receipt,
                lambda kube, private: accept(kube, private, cases, work, receipt),
            )
    except BaseException as exc:
        failure = exc
        receipt["failure"] = type(exc).__name__
    finally:
        receipt["private_directory_removed"] = "work" in locals() and not work.exists()
    receipt["command_groups"] = COMMAND_CLEANUP
    receipt["state"] = "failed" if failure else "passed"
    print(json.dumps(receipt, sort_keys=True))
    if failure is not None:
        raise failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
