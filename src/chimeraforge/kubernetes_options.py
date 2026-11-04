"""Closed Kubernetes declaration options, independent of cluster credentials."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

MAX_DNS_LABEL_CHARS = 63
MAX_PREFIX_CHARS = 40
MAX_NODE_SELECTORS = 16
MAX_DNS_SUBDOMAIN_CHARS = 253
DNS_LABEL = re.compile(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?\Z")
OBJECT_NAME = re.compile(r"[a-z](?:[-a-z0-9]*[a-z0-9])?\Z")
LABEL_NAME = re.compile(r"[A-Za-z0-9](?:[-A-Za-z0-9_.]*[A-Za-z0-9])?\Z")
LINUX_SELECTOR = "kubernetes.io/os"


@dataclass(frozen=True)
class KubernetesOptions:
    """Explicit namespace, logical name prefix and shared scheduler-label intent."""

    namespace: str = "default"
    name_prefix: str | None = None
    node_selector: dict[str, str] = field(default_factory=dict)


def _label_key(value: object) -> bool:
    if type(value) is not str or len(value) > MAX_DNS_SUBDOMAIN_CHARS + MAX_DNS_LABEL_CHARS + 1:
        return False
    parts = value.split("/")
    if len(parts) == 2:
        prefix, name = parts
        if not 0 < len(prefix) <= MAX_DNS_SUBDOMAIN_CHARS or any(
            not 0 < len(label) <= MAX_DNS_LABEL_CHARS or not DNS_LABEL.fullmatch(label)
            for label in prefix.split(".")
        ):
            return False
    elif len(parts) == 1:
        name = parts[0]
    else:
        return False
    return bool(0 < len(name) <= MAX_DNS_LABEL_CHARS and LABEL_NAME.fullmatch(name))


def admit_options(
    value: KubernetesOptions | None, fingerprint: str, index: int
) -> KubernetesOptions:
    from chimeraforge.deploy import DeploymentError

    selected = KubernetesOptions() if value is None else value
    if type(selected) is not KubernetesOptions:
        raise DeploymentError("Kubernetes options require typed independent intent")
    prefix = selected.name_prefix
    if prefix is None:
        prefix = f"cf-{fingerprint[:12]}-c{index}"
    if (
        type(selected.namespace) is not str
        or not 0 < len(selected.namespace) <= MAX_DNS_LABEL_CHARS
        or not OBJECT_NAME.fullmatch(selected.namespace)
        or type(prefix) is not str
        or not 0 < len(prefix) <= MAX_PREFIX_CHARS
        or not OBJECT_NAME.fullmatch(prefix)
        or type(selected.node_selector) is not dict
        or len(selected.node_selector) > MAX_NODE_SELECTORS
    ):
        raise DeploymentError("invalid bounded Kubernetes namespace, prefix or selectors")
    labels = dict(selected.node_selector)
    for key, item in labels.items():
        if (
            not _label_key(key)
            or type(item) is not str
            or len(item) > MAX_DNS_LABEL_CHARS
            or (item and not LABEL_NAME.fullmatch(item))
        ):
            raise DeploymentError("invalid Kubernetes node selector key or value")
    if labels.get(LINUX_SELECTOR, "linux") != "linux":
        raise DeploymentError("Kubernetes export requires the Linux node selector")
    labels[LINUX_SELECTOR] = "linux"
    if len(labels) > MAX_NODE_SELECTORS:
        raise DeploymentError("Kubernetes selector count includes mandatory Linux selection")
    return KubernetesOptions(selected.namespace, prefix, dict(sorted(labels.items())))
