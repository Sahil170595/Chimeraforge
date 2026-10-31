"""Owned Python subprocess controls, not a claim of native kubectl syntax."""

from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest

from chimeraforge import kubernetes_inspection_process as process


async def finish(owner):
    task = asyncio.create_task(owner.close())
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stream,reason", [("stdout", "native_output_limit"), ("stderr", "native_output_limit")]
)
async def test_real_pipe_limits_close_the_owned_process_without_echo(monkeypatch, stream, reason):
    monkeypatch.setattr(process, "MAX_STDOUT_BYTES", 1024)
    monkeypatch.setattr(process, "MAX_STDERR_BYTES", 1024)
    owner = process.ProcessOwner(time.perf_counter() + 5, 1, 2, None)
    result = None
    try:
        result = await owner.run(
            [
                sys.executable,
                "-I",
                "-c",
                f"import sys,time;sys.{stream}.buffer.write(b'x'*2048);"
                f"sys.{stream}.flush();time.sleep(30)",
            ],
            dict(os.environ),
        )
    finally:
        closed = await finish(owner)
    assert result.state == "unavailable" and result.reason == reason and result.stdout == b""
    assert (
        closed["state"] == "completed"
        and closed["owned_processes"] == closed["closed_processes"] == 1
    )
    assert all(task.done() for task in owner.tasks) and all(task.done() for task in owner.joins)


@pytest.mark.asyncio
async def test_shared_budget_charges_sequential_processes_before_append(monkeypatch):
    monkeypatch.setattr(process, "MAX_TOTAL_BYTES", 1000)
    owner = process.ProcessOwner(time.perf_counter() + 5, 1, 2, None)
    argv = [sys.executable, "-I", "-c", "import sys;sys.stdout.buffer.write(b'x'*600)"]
    try:
        first = await owner.run(argv, dict(os.environ))
        second = await owner.run(argv, dict(os.environ))
    finally:
        closed = await finish(owner)
    assert first.state == "complete" and len(first.stdout) == 600
    assert second.state == "unavailable" and second.reason == "shared_output_limit"
    assert owner.total_bytes == 1200 and closed["closed_processes"] == 2


@pytest.mark.asyncio
async def test_real_process_deadline_keeps_all_launches_joined():
    owner = process.ProcessOwner(time.perf_counter() + 0.1, 1, 2, None)
    try:
        result = await owner.run(
            [sys.executable, "-I", "-c", "import time;time.sleep(30)"], dict(os.environ)
        )
    finally:
        closed = await finish(owner)
    assert result.reason == "observation_deadline"
    assert closed["state"] == "completed"
    assert closed["owned_launches"] == closed["joined_launches"] == 1
    assert all(
        child.launch.done() and child.process.returncode is not None for child in owner.children
    )


@pytest.mark.asyncio
async def test_queued_work_rechecks_deadline_after_global_lease():
    owner = process.ProcessOwner(time.perf_counter() + 0.1, 1, 2, None)
    await owner.semaphore.acquire()
    work = owner.task(
        owner.run(
            [sys.executable, "-I", "-c", "raise AssertionError('must not launch')"],
            dict(os.environ),
        )
    )
    try:
        await asyncio.sleep(0.15)
        owner.semaphore.release()
        result = await work
    finally:
        closed = await finish(owner)
    assert result.state == "unstarted" and result.reason == "observation_deadline"
    assert closed["owned_processes"] == closed["owned_launches"] == 0


@pytest.mark.asyncio
async def test_failed_native_command_never_interprets_private_forbidden_stderr(caplog):
    owner = process.ProcessOwner(time.perf_counter() + 5, 1, 2, None)
    try:
        result = await owner.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys;sys.stderr.write('Forbidden private-provider-canary');sys.exit(1)",
            ],
            dict(os.environ),
        )
    finally:
        await finish(owner)
    assert result.state == "unavailable" and result.reason == "native_command_failed"
    assert result.stdout == b"" and "private-provider-canary" not in caplog.text
