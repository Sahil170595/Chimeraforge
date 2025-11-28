"""Lightweight resource coordination helpers for multi-agent runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from contextlib import asynccontextmanager


@dataclass
class ResourceCoordinator:
    """
    Semaphore-based resource coordinator for managing concurrent agent execution.

    Prevents over-subscription of system resources by limiting the number of
    concurrent operations. Can be used as an async context manager or callable.

    Attributes:
        permits: Maximum number of concurrent operations allowed (default: 2)

    Example:
        Basic usage as context manager:
            coordinator = ResourceCoordinator(permits=2)
            async with coordinator:
                # Execute concurrent operation
                pass

        Alternative callable form:
            async with coordinator():
                # Execute concurrent operation
                pass
    """

    permits: int = 2

    def __post_init__(self) -> None:
        """Initialize the internal semaphore with the specified number of permits."""
        self._sem = asyncio.Semaphore(self.permits)

    @asynccontextmanager
    async def _ctx(self):
        """
        Internal context manager for semaphore acquisition/release.

        Yields control after acquiring the semaphore, ensuring release on exit.
        """
        await self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()

    async def __aenter__(self):
        """
        Async context manager entry: acquire semaphore permit.

        Returns:
            ResourceCoordinator: Self instance for context manager usage
        """
        await self._sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Async context manager exit: release semaphore permit.

        Args:
            exc_type: Exception type (if any)
            exc: Exception instance (if any)
            tb: Traceback (if any)
        """
        self._sem.release()

    def __call__(self):
        """
        Make the coordinator callable for alternative usage pattern.

        Returns:
            AsyncContextManager: Context manager for semaphore control

        Example:
            async with coordinator():
                # Execute operation
                pass
        """
        return self._ctx()
