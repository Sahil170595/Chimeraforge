"""Lightweight resource coordination helpers for multi-agent runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from contextlib import asynccontextmanager


@dataclass
class ResourceCoordinator:
    """Semaphore wrapper to avoid accidental over-subscription."""

    permits: int = 2

    def __post_init__(self) -> None:
        self._sem = asyncio.Semaphore(self.permits)

    @asynccontextmanager
    async def _ctx(self):
        await self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()

    async def __aenter__(self):
        await self._sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._sem.release()

    # Optional callable form: async with coordinator(): ...
    def __call__(self):
        return self._ctx()
