"""Owned bounded native kubectl processes under one observation deadline."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import time
from typing import Any

LOG = logging.getLogger(__name__)
READ_BYTES = 16 * 1024
MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 16 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_PROCESSES = 37


@dataclass(frozen=True)
class NativeOutput:
    state: str
    reason: str | None = None
    stdout: bytes = b""
    returncode: int | None = None


@dataclass
class Child:
    launch: asyncio.Task[asyncio.subprocess.Process]
    readers: list[asyncio.Task[bytes]] = field(default_factory=list)
    waiter: asyncio.Task[int] | None = None
    process: asyncio.subprocess.Process | None = None
    closed: bool = False


class ProcessOwner:
    """A lease covers each native invocation; final cleanup owns every leaf."""

    def __init__(
        self,
        deadline: float,
        concurrency: int,
        cleanup_seconds: float,
        stop_event: asyncio.Event | None,
    ) -> None:
        self.deadline = deadline
        self.cleanup_seconds = cleanup_seconds
        self.semaphore = asyncio.Semaphore(concurrency)
        self.halt = asyncio.Event()
        self.reason: str | None = None
        self.total_bytes = 0
        self.children: list[Child] = []
        self.tasks: list[asyncio.Task[Any]] = []
        self.joins: list[asyncio.Future[Any]] = []
        self.halted = self.task(self.halt.wait())
        if stop_event is not None:
            self.task(self._external_stop(stop_event))

    def task(self, coroutine: Any) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task

    async def _external_stop(self, event: asyncio.Event) -> None:
        await event.wait()
        self.stop("caller_stop")

    def stop(self, reason: str) -> None:
        if self.reason is None:
            self.reason = reason
        self.halt.set()

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.perf_counter())

    async def _wait(self, future: asyncio.Future[Any]) -> bool:
        while not future.done() and not self.halt.is_set():
            remaining = self.remaining()
            if remaining <= 0:
                self.stop("observation_deadline")
                break
            await asyncio.wait(
                {future, self.halted}, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
        return future.done() and not self.halt.is_set()

    async def _read(self, stream: asyncio.StreamReader | None, limit: int) -> bytes:
        assert stream is not None
        data = bytearray()
        while chunk := await stream.read(READ_BYTES):
            # Charge both pipes, across every invocation, before appending.
            self.total_bytes += len(chunk)
            if self.total_bytes > MAX_TOTAL_BYTES:
                self.stop("shared_output_limit")
                raise ValueError("shared native output limit")
            if len(chunk) > limit - len(data):
                self.stop("native_output_limit")
                raise ValueError("native output limit")
            data.extend(chunk)
        return bytes(data)

    async def run(
        self, argv: list[str] | Callable[[float], list[str]], env: dict[str, str]
    ) -> NativeOutput:
        async with self.semaphore:
            if self.halt.is_set() or self.remaining() <= 0:
                if not self.halt.is_set():
                    self.stop("observation_deadline")
                return NativeOutput("unstarted", self.reason)
            if len(self.children) >= MAX_PROCESSES:
                self.stop("native_work_limit")
                return NativeOutput("unstarted", self.reason)
            arguments = argv(self.remaining()) if callable(argv) else argv
            if self.halt.is_set() or not arguments:
                return NativeOutput("unstarted", self.reason)
            child = Child(
                asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        *arguments,
                        env=env,
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        limit=READ_BYTES,
                    )
                )
            )
            self.children.append(child)
            try:
                if not await self._wait(child.launch):
                    return NativeOutput("unavailable", self.reason)
                child.process = child.launch.result()
                child.readers = [
                    self.task(self._read(child.process.stdout, MAX_STDOUT_BYTES)),
                    self.task(self._read(child.process.stderr, MAX_STDERR_BYTES)),
                ]
                child.waiter = self.task(child.process.wait())
                finished = asyncio.gather(*child.readers, child.waiter, return_exceptions=True)
                self.joins.append(finished)
                if not await self._wait(finished):
                    return NativeOutput("unavailable", self.reason)
                outcomes = finished.result()
                if any(isinstance(value, BaseException) for value in outcomes):
                    return NativeOutput("unavailable", "native_stream_unavailable")
                child.closed = True
                code = child.process.returncode
                if code != 0:
                    return NativeOutput("unavailable", "native_command_failed", returncode=code)
                return NativeOutput("complete", stdout=child.readers[0].result(), returncode=0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOG.info("Kubernetes native observation unavailable (%s)", type(exc).__name__)
                return NativeOutput("unavailable", "native_process_unavailable")

    async def _close_child(self, child: Child) -> bool:
        try:
            process = await asyncio.shield(child.launch)
        except Exception as exc:
            LOG.info("Kubernetes launch created no owned process (%s)", type(exc).__name__)
            return True
        child.process = process
        good = True
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                LOG.debug("Kubernetes owned process already exited")
            except OSError as exc:
                LOG.info("Kubernetes owned process signal failed (%s)", type(exc).__name__)
                good = False
        await asyncio.gather(*child.readers, return_exceptions=True)

        async def drain(stream: asyncio.StreamReader | None) -> None:
            if stream is not None:
                while await stream.read(READ_BYTES):
                    pass

        outcomes = await asyncio.gather(
            drain(process.stdout), drain(process.stderr), process.wait(), return_exceptions=True
        )
        if any(isinstance(value, BaseException) for value in outcomes):
            LOG.info("Kubernetes owned stream/process join failed")
            good = False
        child.closed = good and process.returncode is not None
        return child.closed

    async def close(self) -> dict[str, Any]:
        started = time.perf_counter()
        deadline = started + self.cleanup_seconds
        # Capture the common allowance before any final cancellation/signalling.
        for task in self.tasks:
            if not task.done():
                task.cancel()
        closers = [asyncio.create_task(self._close_child(child)) for child in self.children]
        # All owners get a close attempt before any potentially unbounded join.
        joined = asyncio.gather(*closers, *self.tasks, *self.joins, return_exceptions=True)
        overrun = False
        while not joined.done():
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                overrun = True
                break
            await asyncio.wait({joined}, timeout=remaining)
        await joined
        overrun = overrun or time.perf_counter() > deadline
        errors = any(isinstance(value, BaseException) for value in joined.result()[: len(closers)])
        closed = sum(child.process is not None and child.closed for child in self.children)
        owned = sum(child.process is not None for child in self.children)
        return {
            "state": "completed"
            if not errors and closed == owned and not overrun
            else "incomplete",
            "owned_processes": owned,
            "closed_processes": closed,
            "owned_launches": len(self.children),
            "joined_launches": len(self.children),
            "allowance_exceeded": overrun,
            "budget_seconds": self.cleanup_seconds,
            "runtime_files_closed": False,
        }
