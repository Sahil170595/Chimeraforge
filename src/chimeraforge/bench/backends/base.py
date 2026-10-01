"""Abstract backend interface for LLM serving backends."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from chimeraforge.bench.metrics import RunMetrics

logger = logging.getLogger(__name__)

# Identity probes are a GET of a tiny JSON document; a slow answer is not an engine.
IDENTITY_TIMEOUT_S = 10


def identity_message(engine: str, base_url: str, why: str) -> str:
    """The refusal for a port that answers but does not name the engine."""
    return f"a service answers at {base_url} but did not identify as {engine} ({why})"


async def fetch_json_field(client: httpx.AsyncClient, url: str, field: str) -> str | None:
    """GET ``url`` and return the JSON body's ``field`` as a string, else None.

    Anything short of a 200 JSON object carrying a non-empty ``field`` is None,
    never the raw body: a fallback would let any JSON 200 pass as the engine.
    """
    try:
        resp = await client.get(url, timeout=IDENTITY_TIMEOUT_S)
    except httpx.HTTPError as exc:
        logger.debug("identity probe %s failed: %s", url, exc)
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        logger.debug("identity probe %s: body is not JSON", url)
        return None
    value = data.get(field) if isinstance(data, dict) else None
    return str(value) if value else None


class Backend(ABC):
    """Abstract interface for LLM serving backends.

    Each backend adapter translates the common generate() call into
    the backend-specific HTTP API, extracts timing metrics from the
    response, and returns a standardized RunMetrics object.
    """

    name: str

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Check if the backend is reachable.

        Returns:
            Tuple of (ok, message). If not ok, message describes the error.
        """

    @abstractmethod
    async def check_model(self, model: str) -> tuple[bool, str]:
        """Check if a model is available on the backend.

        Returns:
            Tuple of (ok, message). If not ok, message includes remediation.
        """

    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """Run a single generation and return metrics.

        Args:
            model: Model name or tag.
            prompt: Input prompt text.
            options: Backend-specific generation options.

        Returns:
            RunMetrics with timing and token counts.
        """

    @abstractmethod
    async def get_version(self) -> str | None:
        """Return the backend version string, or None if unavailable."""

    async def generate_text(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> str:
        """Run a single generation and return the response text.

        Optional capability used by the safety screen. Backends that do not
        implement it raise NotImplementedError (the screen reports a clean
        "not supported" error rather than crashing).
        """
        raise NotImplementedError(
            f"backend '{getattr(self, 'name', type(self).__name__)}' "
            "does not support text generation for the safety screen yet"
        )
