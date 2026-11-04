"""Aggregate passive HTTP budgets with explicit pool and stream ownership."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from chimeraforge.monitor_connection import MonitorConnection


class FleetTransportError(httpx.TransportError):
    """A declared observation cannot continue within its admitted transport contract."""


@dataclass
class SharedBudget:
    deadline: float
    max_requests: int
    max_body_bytes: int
    concurrency: int
    requests: int = 0
    accepted_body_bytes: int = 0
    termination: str | None = None
    semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.semaphore = asyncio.Semaphore(self.concurrency)

    def check(self) -> None:
        if self.termination is None and asyncio.get_running_loop().time() >= self.deadline:
            self.termination = "observation_deadline"
        if self.termination is not None:
            raise FleetTransportError(self.termination)

    def contact(self) -> None:
        self.check()
        if self.requests >= self.max_requests:
            self.termination = "request_limit"
            raise FleetTransportError(self.termination)
        self.requests += 1

    def accept(self, count: int) -> None:
        self.check()
        if count > self.max_body_bytes - self.accepted_body_bytes:
            self.termination = "body_limit"
            raise FleetTransportError(self.termination)
        self.accepted_body_bytes += count

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "max_requests": self.max_requests,
            "accepted_body_bytes": self.accepted_body_bytes,
            "max_body_bytes": self.max_body_bytes,
            "termination": self.termination,
            "byte_scope": "accepted identity-encoded body chunks; not wire/transport buffers",
        }


class OwnedPool:
    """The coordinator owns one pool; client borrowers never close it."""

    def __init__(
        self,
        budget: SharedBudget,
        limit: int,
        timeout: float = 10.0,
        *,
        connection: MonitorConnection | None = None,
    ) -> None:
        self.budget = budget
        self.limit = limit
        self.timeout = timeout
        self._connection = connection
        self.inner: httpx.AsyncBaseTransport | None = None
        self.streams: set[BudgetStream] = set()
        self.violation: str | None = None
        self.closed = False
        self.requests = 0

    def _transport(self) -> httpx.AsyncBaseTransport:
        if self.inner is None:
            self.inner = httpx.AsyncHTTPTransport(
                retries=0,
                trust_env=False,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                **(self._connection._transport_kwargs() if self._connection is not None else {}),
            )
        return self.inner

    async def aclose(self) -> None:
        try:
            for stream in tuple(self.streams):
                await stream.aclose()
        finally:
            if self.inner is not None:
                await self.inner.aclose()
        self.closed = not self.streams


class BudgetStream(httpx.AsyncByteStream):
    def __init__(self, inner: httpx.AsyncByteStream, pool: OwnedPool) -> None:
        self.inner, self.pool = inner, pool
        self.size = 0
        self.closed = False
        self.closing: asyncio.Task[None] | None = None
        pool.streams.add(self)

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.inner:
            self.pool.budget.check()
            if len(chunk) > self.pool.limit - self.size:
                self.pool.violation = "response_size_limit"
                raise FleetTransportError(self.pool.violation)
            self.pool.budget.accept(len(chunk))
            self.size += len(chunk)
            yield chunk

    async def _close(self) -> None:
        try:
            await self.inner.aclose()
            self.closed = True
            self.pool.streams.discard(self)
        finally:
            self.pool.budget.semaphore.release()

    async def aclose(self) -> None:
        if self.closing is None:
            self.closing = asyncio.create_task(self._close())
        await asyncio.shield(self.closing)


class BorrowedTransport(httpx.AsyncBaseTransport):
    def __init__(self, pool: OwnedPool) -> None:
        self.pool = pool

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        budget = self.pool.budget
        budget.check()
        await budget.semaphore.acquire()
        stream: BudgetStream | None = None
        try:
            budget.contact()
            self.pool.requests += 1
            request.headers["Accept-Encoding"] = "identity"
            request.extensions["timeout"] = dict.fromkeys(
                ("connect", "read", "write", "pool"), self.pool.timeout
            )
            response = await self.pool._transport().handle_async_request(request)
            if not isinstance(response.stream, httpx.AsyncByteStream):
                raise FleetTransportError("transport returned a non-async stream")
            stream = BudgetStream(response.stream, self.pool)
            response.stream = stream
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                self.pool.violation = "encoded_response"
                await stream.aclose()
                raise FleetTransportError(self.pool.violation)
            return response
        except BaseException:
            if stream is None:
                budget.semaphore.release()
            else:
                await stream.aclose()
            raise

    async def aclose(self) -> None:
        """Client closure ends its borrowing lease; pool ownership stays external."""
