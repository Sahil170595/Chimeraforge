"""Backend registry — maps backend names to adapter classes."""

from __future__ import annotations

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.backends.ollama import OllamaBackend
from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends.vllm import VLLMBackend

BACKEND_REGISTRY: dict[str, type[Backend]] = {
    "ollama": OllamaBackend,
    "vllm": VLLMBackend,
    "tgi": TGIBackend,
}


def get_backend(name: str, **kwargs: object) -> Backend:
    """Instantiate a backend by name.

    Args:
        name: Backend identifier ("ollama", "vllm", or "tgi").
        **kwargs: Passed to the backend constructor (e.g. base_url).

    Returns:
        Configured Backend instance.

    Raises:
        ValueError: If backend name is unknown.
    """
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown backend: {name}. Available: {list(BACKEND_REGISTRY)}")
    return cls(**kwargs)
