"""Abstract backend interface for LLM serving backends."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Callable

import httpx

from chimeraforge.bench.metrics import RunMetrics

logger = logging.getLogger(__name__)

# Identity probes are a GET of a tiny JSON document; a slow answer is not an engine.
IDENTITY_TIMEOUT_S = 10


@dataclass(frozen=True)
class GenerationObservation:
    """Native final metrics and an explicitly scoped mean decode interval."""

    native: dict
    mean_tpot_ms: float | None = None
    mean_tpot_basis: str = "unavailable"


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

    async def close(self) -> None:
        """Release task-owned resources; stateless adapters need no cleanup."""

    async def observe_serving(self, model: str) -> dict:
        """Observed metadata; replicas means full endpoint topology, not engine DP size."""
        return {"source": "serving metadata capability unavailable"}

    async def generate_observed(
        self,
        model: str,
        prompt: str,
        options: dict,
        on_first_output: Callable[[], None],
    ) -> GenerationObservation:
        """Legacy fallback has no first-output callback; never infer one from prefill."""
        metrics = await self.generate(model, prompt, options)
        interval = None
        basis = "unavailable"
        if metrics.ttft_basis == "client-stream-first-content" and metrics.tokens_generated >= 2:
            interval = metrics.eval_duration_ms / (metrics.tokens_generated - 1)
            basis = "client-first-to-last-content/(server-output-count-1)"
        return GenerationObservation(asdict(metrics), interval, basis)


@asynccontextmanager
async def backend_lifecycle(
    backend: Backend, *, _cleanup: dict | None = None
) -> AsyncIterator[Backend]:
    """Close an adapter on success, error, or cancellation without hiding the original failure."""
    failed = False
    try:
        yield backend
    except BaseException:
        failed = True
        raise
    finally:
        if _cleanup is not None:
            _cleanup["state"] = "started"
        try:
            # Keep the existing optional-close protocol used by doctor and legacy adapters.
            close = getattr(backend, "close", None)
            if close is not None:
                await close()
            if _cleanup is not None:
                _cleanup["state"] = "completed"
        except asyncio.CancelledError:
            if _cleanup is not None:
                _cleanup["state"] = "incomplete"
            raise
        except Exception as exc:
            if _cleanup is not None:
                _cleanup["state"] = "incomplete"
            name = getattr(backend, "name", type(backend).__name__)
            logger.warning("Backend '%s' cleanup failed: %s", name, exc, exc_info=True)
            if not failed:
                raise RuntimeError(f"Backend '{name}' cleanup failed: {exc}") from exc
