"""Pinned 1.37.0 server defaults and independent native Deployment rollout facts."""

from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
import ipaddress
import logging
from typing import Any

from chimeraforge.deployment_verify import _differences, _pointer

SERVER_VERSION = "v1.37.0"
CLIENT_VERSION = "v1.37.1"
INT32_MAX = (1 << 31) - 1
INT64_MAX = (1 << 63) - 1
CONDITION_TEXT_FIELDS = ("type", "status", "reason", "message")
LOG = logging.getLogger(__name__)
SERVER_METADATA = ("uid", "resourceVersion", "creationTimestamp", "managedFields", "generation")
MAP_PATHS = (
    "/metadata/labels",
    "/metadata/annotations",
    "/spec/selector",
    "/spec/template/metadata/labels",
    "/spec/template/metadata/annotations",
    "/spec/template/spec/nodeSelector",
)


def _shape(actual: dict) -> None:
    if type(actual.get("status", {})) is not dict:
        raise ValueError("native status shape unavailable")
    metadata, spec = actual["metadata"], actual["spec"]
    if "generation" in metadata and (
        type(metadata["generation"]) is not int or not 0 <= metadata["generation"] <= INT64_MAX
    ):
        raise ValueError("native generation shape unavailable")
    for key in ("uid", "resourceVersion"):
        if key in metadata and type(metadata[key]) is not str:
            raise ValueError("native metadata shape unavailable")
    if (
        "creationTimestamp" in metadata
        and metadata["creationTimestamp"] is not None
        and type(metadata["creationTimestamp"]) is not str
    ):
        raise ValueError("native timestamp shape unavailable")
    if "managedFields" in metadata and type(metadata["managedFields"]) is not list:
        raise ValueError("native metadata shape unavailable")
    for key in ("labels", "annotations"):
        if key in metadata and (
            type(metadata[key]) is not dict
            or any(
                type(name) is not str or type(value) is not str
                for name, value in metadata[key].items()
            )
        ):
            raise ValueError("native metadata map unavailable")
    if actual["kind"] == "Deployment":
        if type(spec.get("replicas")) is not int or not 0 <= spec["replicas"] <= INT32_MAX:
            raise ValueError("native replica shape unavailable")
        template = spec.get("template")
        if type(template) is not dict or type(template.get("spec")) is not dict:
            raise ValueError("native template shape unavailable")
        containers = template["spec"].get("containers")
        if type(containers) is not list or not containers:
            raise ValueError("native container shape unavailable")
        for container in containers:
            if (
                type(container) is not dict
                or type(container.get("name")) is not str
                or type(container.get("image")) is not str
            ):
                raise ValueError("native container shape unavailable")
            for key in ("command", "args"):
                if key in container and (
                    type(container[key]) is not list
                    or any(type(value) is not str for value in container[key])
                ):
                    raise ValueError("native argument vector unavailable")
            resources = container.get("resources", {})
            if type(resources) is not dict:
                raise ValueError("native resource requirements unavailable")
            for key in ("requests", "limits"):
                if key in resources and (
                    type(resources[key]) is not dict
                    or any(type(value) is not str for value in resources[key].values())
                ):
                    raise ValueError("native resource quantities unavailable")


def _schema_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], int] = {}
    for change in changes:
        path = change["path"]
        for parent in MAP_PATHS:
            if path.startswith(parent + "/"):
                path = parent
                break
        key = (path, change["category"])
        grouped[key] = grouped.get(key, 0) + change["count"]
    return [
        {"path": path, "category": category, "count": count}
        for (path, category), count in grouped.items()
    ]


def _drop_default(value: dict, name: str, default: object) -> None:
    if name in value and type(value[name]) is type(default) and value[name] == default:
        del value[name]


def _deployment_defaults(actual: dict) -> None:
    spec = actual["spec"]
    _drop_default(spec, "revisionHistoryLimit", 10)
    _drop_default(spec, "progressDeadlineSeconds", 600)
    template = spec.get("template")
    if type(template) is not dict or type(template.get("spec")) is not dict:
        return
    metadata = template.get("metadata")
    if type(metadata) is dict:
        _drop_default(metadata, "creationTimestamp", None)
    pod = template["spec"]
    for key, default in (
        ("restartPolicy", "Always"),
        ("dnsPolicy", "ClusterFirst"),
        ("schedulerName", "default-scheduler"),
        ("securityContext", {}),
        ("terminationGracePeriodSeconds", 30),
    ):
        _drop_default(pod, key, default)
    containers = pod.get("containers")
    if type(containers) is list:
        for container in containers:
            if type(container) is not dict:
                continue
            image = container.get("image")
            if type(image) is str:
                base = image.split("@", 1)[0].rsplit("/", 1)[-1]
                tag = base.rsplit(":", 1)[1] if ":" in base else None
                pull = (
                    "Always"
                    if tag == "latest" or (tag is None and "@" not in image)
                    else "IfNotPresent"
                )
                _drop_default(container, "imagePullPolicy", pull)
            _drop_default(container, "terminationMessagePath", "/dev/termination-log")
            _drop_default(container, "terminationMessagePolicy", "File")
            ports = container.get("ports")
            if type(ports) is list:
                for port in ports:
                    if type(port) is dict:
                        _drop_default(port, "protocol", "TCP")
    annotations = actual["metadata"].get("annotations")
    if type(annotations) is dict:
        revision = annotations.get("deployment.kubernetes.io/revision")
        if (
            type(revision) is str
            and revision.isascii()
            and revision.isdecimal()
            and int(revision) > 0
        ):
            del annotations["deployment.kubernetes.io/revision"]


def _service_defaults(actual: dict) -> None:
    spec = actual["spec"]
    if spec.get("type") != "ClusterIP":
        return
    _drop_default(spec, "sessionAffinity", "None")
    _drop_default(spec, "internalTrafficPolicy", "Cluster")
    # Only allocated ordinary ClusterIP addresses are observational allocation fields.
    # Headless, inconsistent and alternate traffic/family policies stay visible.
    cluster_ip, cluster_ips, families = (
        spec.get(key) for key in ("clusterIP", "clusterIPs", "ipFamilies")
    )
    try:
        address = ipaddress.ip_address(cluster_ip) if type(cluster_ip) is str else None
    except ValueError:
        LOG.debug("Kubernetes Service has no ordinary allocated ClusterIP")
        address = None
    if address is not None:
        family = "IPv4" if address.version == 4 else "IPv6"
        if (
            type(cluster_ips) is list
            and cluster_ips == [cluster_ip]
            and type(families) is list
            and families == [family]
            and spec.get("ipFamilyPolicy") == "SingleStack"
        ):
            for key in ("clusterIP", "clusterIPs", "ipFamilies", "ipFamilyPolicy"):
                del spec[key]


def _complete_changes(expected: Any, actual: Any, prefix: str = "") -> list[dict[str, Any]]:
    changes, _, truncated = _differences({"value": expected}, {"value": actual})
    if not truncated:
        return [
            {**asdict(change), "path": prefix + change.path[len("/value") :]} for change in changes
        ]
    # Partition only trusted expected keys when the offline verifier's own cap fills.
    result: list[dict[str, Any]] = []
    if type(expected) is dict and type(actual) is dict:
        extras = sum(key not in expected for key in actual)
        if extras:
            result.append({"path": prefix, "category": "extra_keys", "count": extras})
        for key, before in expected.items():
            if key not in actual:
                result.append(
                    {"path": _pointer(prefix, key), "category": "missing_key", "count": 1}
                )
            else:
                result.extend(_complete_changes(before, actual[key], _pointer(prefix, key)))
    else:
        assert type(expected) is list and type(actual) is list
        if len(expected) != len(actual):
            result.append(
                {
                    "path": prefix,
                    "category": "array_length",
                    "count": abs(len(expected) - len(actual)),
                }
            )
        for index in range(min(len(expected), len(actual))):
            result.extend(
                _complete_changes(expected[index], actual[index], _pointer(prefix, index))
            )
    return result


def compare_intent(expected: dict, actual: dict) -> dict[str, Any]:
    """Compare full behavior after removing only the pinned native defaults."""
    metadata = actual.get("metadata")
    if (
        actual.get("apiVersion") != expected["apiVersion"]
        or actual.get("kind") != expected["kind"]
        or type(metadata) is not dict
        or metadata.get("name") != expected["metadata"]["name"]
        or metadata.get("namespace") != expected["metadata"]["namespace"]
        or type(actual.get("spec")) is not dict
    ):
        raise ValueError("native object identity or shape unavailable")
    _shape(actual)
    normalized = deepcopy(actual)
    normalized.pop("status", None)
    for key in SERVER_METADATA:
        normalized["metadata"].pop(key, None)
    if actual["kind"] == "Deployment":
        _deployment_defaults(normalized)
    else:
        _service_defaults(normalized)
    changes = _schema_changes(_complete_changes(expected, normalized))
    return {
        "state": "drift" if changes else "match",
        "reason": None,
        "changes": changes,
        "change_count": sum(change["count"] for change in changes),
    }


def rollout(actual: dict) -> dict[str, Any]:
    """Mirror the pinned DeploymentStatusViewer, without persisting status messages."""
    if actual.get("kind") == "Service":
        return {"state": "not_requested", "reason": None}
    metadata, spec, status = actual.get("metadata"), actual.get("spec"), actual.get("status", {})
    if type(metadata) is not dict or type(spec) is not dict or type(status) is not dict:
        return {"state": "unknown", "reason": "native_rollout_invalid"}
    numbers = {
        "generation": metadata.get("generation"),
        "desired": spec.get("replicas"),
        "observed": status.get("observedGeneration", 0),
        "updated": status.get("updatedReplicas", 0),
        "replicas": status.get("replicas", 0),
        "available": status.get("availableReplicas", 0),
    }
    if any(
        type(value) is not int
        or not 0 <= value <= (INT64_MAX if name in ("generation", "observed") else INT32_MAX)
        for name, value in numbers.items()
    ):
        return {"state": "unknown", "reason": "native_rollout_invalid"}
    conditions = status.get("conditions", [])
    if type(conditions) is not list or any(type(value) is not dict for value in conditions):
        return {"state": "unknown", "reason": "native_rollout_invalid"}
    if any(
        type(value.get(field, "")) is not str
        for value in conditions
        for field in CONDITION_TEXT_FIELDS
    ):
        return {"state": "unknown", "reason": "native_rollout_invalid"}
    reason = None
    if metadata.get("deletionTimestamp") is not None:
        reason = "deleting"
    elif numbers["generation"] > numbers["observed"]:
        reason = "generation_unobserved"
    elif any(
        value.get("type") == "Progressing" and value.get("reason") == "ProgressDeadlineExceeded"
        for value in conditions
    ):
        reason = "progress_deadline_exceeded"
    elif numbers["updated"] < numbers["desired"]:
        reason = "updated_replicas_pending"
    elif numbers["replicas"] > numbers["updated"]:
        reason = "old_replicas_pending"
    elif numbers["available"] < numbers["updated"]:
        reason = "available_replicas_pending"
    return {"state": "complete" if reason is None else "pending", "reason": reason, **numbers}
