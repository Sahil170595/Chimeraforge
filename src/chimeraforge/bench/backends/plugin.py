"""Discover installed backend metadata; import only an explicitly selected adapter."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from importlib import metadata

from chimeraforge.bench.backends.base import Backend

ENTRY_POINT_GROUP = "chimeraforge.backends"
BACKEND_NAME = re.compile(r"[a-z][a-z0-9_-]*\Z")
ASYNC_METHODS = ("health_check", "check_model", "generate", "get_version", "generate_text", "close")


class BackendPluginError(ValueError):
    """Installed plugin metadata, adapter contract, or initialization is invalid."""


@dataclass(frozen=True)
class BackendPlugin:
    """An entry-point descriptor; inspecting it never calls ``EntryPoint.load``."""

    name: str
    value: str
    distribution: str | None
    version: str | None
    _entry_point: metadata.EntryPoint = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, str | None]:
        """Return metadata suitable for a backend listing."""
        return {
            "name": self.name,
            "kind": "plugin",
            "value": self.value,
            "distribution": self.distribution,
            "version": self.version,
        }


def discover_plugins() -> tuple[BackendPlugin, ...]:
    """Read installed metadata without importing or constructing any adapter.

    Conflicting or unsafe lookup names are errors, independent of discovery order.
    Built-in selection bypasses this operation, so bad plugin metadata cannot
    disable a built-in engine.
    """
    from chimeraforge.bench.backends import BACKEND_REGISTRY

    try:
        entries = metadata.entry_points(group=ENTRY_POINT_GROUP)
        plugins = []
        for entry in entries:
            dist = entry.dist
            plugins.append(
                BackendPlugin(
                    entry.name,
                    entry.value,
                    dist.metadata.get("Name") if dist else None,
                    dist.version if dist else None,
                    entry,
                )
            )
    except Exception as exc:
        raise BackendPluginError(
            f"Cannot read {ENTRY_POINT_GROUP} entry-point metadata: {exc}"
        ) from exc

    plugins.sort(key=lambda p: (p.name, p.distribution or "", p.version or "", p.value))
    seen: dict[str, BackendPlugin] = {}
    for plugin in plugins:
        context = _context(plugin)
        if not BACKEND_NAME.fullmatch(plugin.name):
            raise BackendPluginError(
                f"Backend plugin {context} has an invalid name; use lowercase ASCII letters, "
                "digits, '-' or '_', starting with a letter"
            )
        if plugin.name in BACKEND_REGISTRY:
            raise BackendPluginError(f"Backend plugin {context} collides with a built-in backend")
        if plugin.name in seen:
            raise BackendPluginError(
                f"Backend plugin name '{plugin.name}' is duplicate: "
                f"{_context(seen[plugin.name])}; {context}"
            )
        seen[plugin.name] = plugin
    return tuple(plugins)


def _context(plugin: BackendPlugin) -> str:
    owner = f"{plugin.distribution or 'unknown distribution'} {plugin.version or ''}".strip()
    return f"'{plugin.name}' ({owner}, {plugin.value})"


def instantiate_plugin(plugin: BackendPlugin, **kwargs: object) -> Backend:
    """Load trusted local Python code for one selected entry point and validate it."""
    context = _context(plugin)
    try:
        cls = plugin._entry_point.load()
    except Exception as exc:
        raise BackendPluginError(f"Cannot load backend plugin {context}: {exc}") from exc
    if not inspect.isclass(cls):
        raise BackendPluginError(f"Backend plugin {context} must export a class")
    if not issubclass(cls, Backend):
        raise BackendPluginError(f"Backend plugin {context} must subclass Backend")
    if inspect.isabstract(cls):
        raise BackendPluginError(f"Backend plugin {context} exports an abstract Backend class")
    if getattr(cls, "name", None) != plugin.name:
        raise BackendPluginError(
            f"Backend plugin {context} class.name must equal the entry-point name"
        )
    for method in ASYNC_METHODS:
        if not inspect.iscoroutinefunction(getattr(cls, method, None)):
            raise BackendPluginError(f"Backend plugin {context} method '{method}' must be async")
    try:
        return cls(**kwargs)
    except Exception as exc:
        raise BackendPluginError(f"Cannot initialize backend plugin {context}: {exc}") from exc
