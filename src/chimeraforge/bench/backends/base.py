"""Abstract backend interface for LLM serving backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from chimeraforge.bench.metrics import RunMetrics


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
