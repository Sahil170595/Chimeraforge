"""One bounded owned nvidia-smi query; strict observations cannot salvage partial rows."""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import io
import logging
from dataclasses import replace
from typing import Literal

from chimeraforge.deploy import _GPU_ORDINAL, _GPU_UUID, MAX_GPU_IDENTIFIER_CHARS
from chimeraforge.inventory_numbers import number, decimal_text
from chimeraforge.inventory_types import InventoryDevice, InventoryObservation

logger = logging.getLogger(__name__)
COMMAND: tuple[str, ...] = (
    "nvidia-smi",
    "--query-gpu=index,uuid,name,memory.total,memory.free,driver_version,mig.mode.current",
    "--format=csv,noheader,nounits",
)
MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 16 * 1024
MAX_INVENTORY_ROWS = 1024
MAX_FIELD_CHARS = 256
READ_BYTES = 16 * 1024


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_inventory(raw: bytes) -> tuple[InventoryDevice, ...]:
    """Parse a complete successful query, preserving its order and raw MIG status."""
    if not raw or len(raw) > MAX_STDOUT_BYTES or not raw.endswith(b"\n"):
        raise ValueError("incomplete inventory")
    rows = csv.reader(io.StringIO(raw.decode("utf-8")), strict=True, skipinitialspace=True)
    devices: list[InventoryDevice] = []
    ordinals: set[str] = set()
    uuids: set[str] = set()
    for row in rows:
        if len(row) != 7 or len(devices) >= MAX_INVENTORY_ROWS:
            raise ValueError("inventory row bounds")
        values = [value.strip() for value in row]
        if any(
            not value
            or len(value) > MAX_FIELD_CHARS
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            for value in values
        ):
            raise ValueError("inventory field bounds")
        ordinal, uuid, name, total, free, driver, mig = values
        if (
            len(ordinal) > MAX_GPU_IDENTIFIER_CHARS
            or not _GPU_ORDINAL.fullmatch(ordinal)
            or not _GPU_UUID.fullmatch(uuid)
        ):
            raise ValueError("invalid inventory identifier")
        uuid = "GPU-" + uuid[4:].lower()
        if ordinal in ordinals or uuid in uuids:
            raise ValueError("duplicate inventory identity")
        ordinals.add(ordinal)
        uuids.add(uuid)
        # N/A is the documented unsupported value; unknown syntax is never numeric zero.
        total_value = None if total == "N/A" else number(total)
        free_value = None if free == "N/A" else number(free)
        if total_value is not None and free_value is not None and free_value > total_value:
            raise ValueError("contradictory inventory memory")
        devices.append(
            InventoryDevice(
                ordinal,
                uuid,
                name,
                None if total_value is None else decimal_text(total_value),
                None if free_value is None else decimal_text(free_value),
                driver,
                mig,
            )
        )
    if not devices:
        raise ValueError("empty inventory")
    return tuple(devices)


async def _read(stream: asyncio.StreamReader | None, limit: int) -> bytes:
    assert stream is not None
    data = bytearray()
    while chunk := await stream.read(READ_BYTES):
        if len(chunk) > limit - len(data):
            raise ValueError("native output limit")
        data.extend(chunk)
    return bytes(data)


async def _drain(stream: asyncio.StreamReader | None) -> None:
    if stream is not None:
        while await stream.read(READ_BYTES):
            pass


async def _close(
    launch: asyncio.Task[asyncio.subprocess.Process], readers: list[asyncio.Task[bytes]]
) -> Literal["completed", "not_started", "failed"]:
    try:
        process = await launch
    except Exception as exc:
        logger.info("inventory launch created no owned child (%s)", type(exc).__name__)
        return "not_started"
    try:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                logger.debug("inventory child already exited during owned close")
        for task in readers:
            if not task.done():
                task.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        await asyncio.gather(_drain(process.stdout), _drain(process.stderr), process.wait())
        return "completed"
    except Exception as exc:
        logger.info("inventory owned process close unavailable (%s)", type(exc).__name__)
        return "failed"


async def observe(timeout: float) -> InventoryObservation:
    """Supervise launch, both output pipes, completion and repeated cancellation."""
    started = _stamp()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    launch = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *COMMAND,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=READ_BYTES,
        )
    )
    readers: list[asyncio.Task[bytes]] = []
    process = None
    cancelled = False
    result = InventoryObservation(
        "unknown", COMMAND, started_at=started, reason="native_query_unavailable"
    )
    try:
        process = await asyncio.wait_for(asyncio.shield(launch), max(0, deadline - loop.time()))
        readers = [
            asyncio.create_task(_read(process.stdout, MAX_STDOUT_BYTES)),
            asyncio.create_task(_read(process.stderr, MAX_STDERR_BYTES)),
        ]
        await asyncio.wait_for(
            asyncio.gather(*readers, process.wait()), max(0, deadline - loop.time())
        )
        stdout = readers[0].result()
        code = process.returncode
        assert code is not None
        if code != 0:
            result = replace(result, returncode=code, reason="native_query_failed")
        else:
            devices = parse_inventory(stdout)
            result = replace(
                result,
                state="complete",
                returncode=code,
                reason=None,
                devices=devices,
                stdout_sha256=hashlib.sha256(stdout).hexdigest(),
            )
    except asyncio.CancelledError:
        cancelled = True
    except Exception as exc:
        logger.info("inventory native observation unavailable (%s)", type(exc).__name__)
        result = replace(
            result,
            reason="native_observation_invalid"
            if process is not None
            else "native_query_unavailable",
        )
    finally:
        closer = asyncio.create_task(_close(launch, readers))
        while True:
            try:
                closed = await asyncio.shield(closer)
                break
            except asyncio.CancelledError:
                cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    return replace(
        result,
        finished_at=_stamp(),
        returncode=process.returncode if process is not None else None,
        cleanup_state=closed,
    )
