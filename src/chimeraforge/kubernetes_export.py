"""Deterministic native Kubernetes declarations, never a cluster operation."""

from __future__ import annotations

import copy
import json

from chimeraforge.kubernetes_options import KubernetesOptions
from chimeraforge.planner.engine import Candidate

MAX_ARGV_TOKENS = 128
MAX_ARGV_TOKEN_BYTES = 4096
MAX_ARGV_BYTES = 64 * 1024
SHARED_MEMORY_SIZE = "1Gi"
ANNOTATION_PREFIX = "org.chimeraforge/"


def literal_argv(argv: list[str]) -> list[str]:
    from chimeraforge.deploy import DeploymentError

    if type(argv) is not list or not 1 <= len(argv) <= MAX_ARGV_TOKENS:
        raise DeploymentError("Kubernetes native argv exceeds its token bound")
    result, total = [], 0
    for value in argv:
        if type(value) is not str or len(value) > MAX_ARGV_TOKEN_BYTES:
            raise DeploymentError("Kubernetes native argv token exceeds its byte bound")
        # Kubelet expansion consumes $$ once; JSON/shell quoting does not prevent $(...) lookup.
        encoded = value.replace("$", "$$")
        try:
            size = len(encoded.encode("utf-8"))
        except UnicodeError:
            raise DeploymentError("Kubernetes native argv must be valid UTF-8") from None
        total += size
        if size > MAX_ARGV_TOKEN_BYTES or total > MAX_ARGV_BYTES:
            raise DeploymentError("Kubernetes encoded argv exceeds its byte bound")
        result.append(encoded)
    return result


def render(
    candidate: Candidate,
    argv: list[str],
    image: str,
    fingerprint: str,
    index: int,
    options: KubernetesOptions,
) -> str:
    from chimeraforge.deploy import DeploymentError
    from chimeraforge.deployment_verify import MAX_CONFIG_BYTES, _admit

    encoded = literal_argv(argv)
    command_length = 2 if candidate.backend == "vllm" else 3
    port = 8000 if candidate.backend == "vllm" else 30000
    quantity = str(candidate.tensor_parallel * candidate.pipeline_parallel)
    items = []
    for member in range(1, candidate.n_agents + 1):
        name = f"{options.name_prefix}-m{member}"
        labels = {
            "app.kubernetes.io/name": "chimeraforge",
            "app.kubernetes.io/instance": name,
            "app.kubernetes.io/managed-by": "chimeraforge",
        }
        metadata = {
            "name": name,
            "namespace": options.namespace,
            "labels": labels,
            "annotations": {
                ANNOTATION_PREFIX + "plan-fingerprint": fingerprint,
                ANNOTATION_PREFIX + "candidate-index": str(index),
                ANNOTATION_PREFIX + "replica-index": str(member),
                ANNOTATION_PREFIX + "replica-count": str(candidate.n_agents),
            },
        }
        items.append(
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": copy.deepcopy(metadata),
                "spec": {
                    "replicas": 1,
                    "strategy": {"type": "Recreate"},
                    "selector": {"matchLabels": copy.deepcopy(labels)},
                    "template": {
                        "metadata": {"labels": copy.deepcopy(labels)},
                        "spec": {
                            "nodeSelector": dict(options.node_selector),
                            "containers": [
                                {
                                    "name": "inference",
                                    "image": image,
                                    "command": encoded[:command_length],
                                    "args": encoded[command_length:],
                                    "ports": [{"name": "http", "containerPort": port}],
                                    "resources": {
                                        "requests": {"nvidia.com/gpu": quantity},
                                        "limits": {"nvidia.com/gpu": quantity},
                                    },
                                    "volumeMounts": [
                                        {"name": "shared-memory", "mountPath": "/dev/shm"}
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "shared-memory",
                                    "emptyDir": {
                                        "medium": "Memory",
                                        "sizeLimit": SHARED_MEMORY_SIZE,
                                    },
                                }
                            ],
                        },
                    },
                },
            }
        )
        items.append(
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": copy.deepcopy(metadata),
                "spec": {
                    "type": "ClusterIP",
                    "selector": copy.deepcopy(labels),
                    "ports": [
                        {"name": "http", "port": port, "targetPort": port, "protocol": "TCP"}
                    ],
                },
            }
        )
    data = {"apiVersion": "v1", "kind": "List", "items": items}
    try:
        _admit(data, MAX_CONFIG_BYTES)
        content = json.dumps(data, indent=2, allow_nan=False) + "\n"
        if len(content.encode("utf-8")) > MAX_CONFIG_BYTES:
            raise ValueError
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise DeploymentError("Kubernetes manifest exceeds its bounded JSON contract") from None
    return content
