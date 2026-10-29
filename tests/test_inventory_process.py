"""Owned Python protocol children exercise bounds without probing local GPUs."""

import asyncio
import logging
import sys

import pytest

from chimeraforge import inventory_process as process


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        "import time;time.sleep(60)",
        "import sys;sys.stdout.write('x'*1100000)",
        "import sys;sys.stderr.write('x'*17000)",
        "raise SystemExit(9)",
    ],
)
async def test_native_process_failure_bounds_are_unknown_and_reaped(monkeypatch, code):
    children = []
    original = asyncio.create_subprocess_exec

    async def launch(*args, **kwargs):
        child = await original(sys.executable, "-B", "-c", code, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    result = await process.observe(0.2)
    assert result.state == "unknown" and not result.devices
    assert result.cleanup_state == "completed"
    assert len(children) == 1 and children[0].returncode is not None


@pytest.mark.asyncio
async def test_second_cancellation_during_owned_close_is_joined(monkeypatch):
    original_close = process._close
    closing, release = asyncio.Event(), asyncio.Event()

    async def delayed_close(*args):
        closing.set()
        await release.wait()
        return await original_close(*args)

    monkeypatch.setattr(process, "_close", delayed_close)
    monkeypatch.setattr(process, "COMMAND", (sys.executable, "-B", "-c", "pass"))
    task = asyncio.create_task(process.observe(2))
    await asyncio.wait_for(closing.wait(), 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)


@pytest.mark.asyncio
async def test_unavailable_launch_never_discloses_exception_message(monkeypatch, caplog):
    secret = "inventory-secret-canary"

    async def unavailable(*args, **kwargs):
        raise OSError(secret)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", unavailable)
    with caplog.at_level(logging.INFO):
        result = await process.observe(2)
    assert result.state == "unknown" and secret not in repr(result) + caplog.text
    assert "OSError" in caplog.text and "inventory" in caplog.text
