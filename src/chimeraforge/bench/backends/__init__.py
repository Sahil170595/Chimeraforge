"""Backend registry - maps backend names to adapter classes."""

from __future__ import annotations

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.backends.ollama import OllamaBackend
from chimeraforge.bench.backends.sglang import SGLangBackend
from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends.vllm import VLLMBackend

BACKEND_REGISTRY: dict[str, type[Backend]] = {
    "ollama": OllamaBackend,
    "vllm": VLLMBackend,
    "tgi": TGIBackend,
    "sglang": SGLangBackend,
}


def get_backend(name: str, **kwargs: object) -> Backend:
    """Instantiate a backend by name.

    Args:
        name: Built-in backend or an installed ``chimeraforge.backends`` entry-point name.
        **kwargs: Passed to the backend constructor (e.g. base_url).

    Returns:
        Configured Backend instance.

    Raises:
        ValueError: If backend name is unknown.
    """
    cls = BACKEND_REGISTRY.get(name)
    connection = kwargs.get("connection")
    if connection is not None:
        from chimeraforge.monitor_connection import (
            MonitorConnection,
            MonitorConnectionError,
            admit_connection,
        )

        if type(connection) is not MonitorConnection:
            raise MonitorConnectionError("invalid secure backend connection")
        if not (
            (name == "vllm" and cls is VLLMBackend) or (name == "sglang" and cls is SGLangBackend)
        ):
            raise MonitorConnectionError("secure backend is unsupported")
        url = kwargs.get("base_url")
        if not isinstance(url, str):
            raise MonitorConnectionError("secure backend requires an explicit HTTPS URL")
        admit_connection(connection, url)
    if cls is not None:
        return cls(**kwargs)

    from chimeraforge.bench.backends.plugin import discover_plugins, instantiate_plugin

    plugins = discover_plugins()
    for plugin in plugins:
        if plugin.name == name:
            return instantiate_plugin(plugin, **kwargs)
    available = sorted([*BACKEND_REGISTRY, *(p.name for p in plugins)])
    raise ValueError(f"Unknown backend: {name}. Available: {available}")


def list_backends() -> list[dict[str, str | None]]:
    """List built-ins and installed plugin metadata without importing plugin code."""
    from chimeraforge.bench.backends.plugin import discover_plugins

    rows = [
        {"name": name, "kind": "built-in", "value": None, "distribution": None, "version": None}
        for name in BACKEND_REGISTRY
    ]
    rows.extend(plugin.to_dict() for plugin in discover_plugins())
    return sorted(rows, key=lambda row: row["name"] or "")
