"""Observe one native registry launch without interpreting or replaying MCP stdin."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
from typing import BinaryIO

from ci_registry_runtime import (
    MAX_NATIVE_STDERR_BYTES,
    command_digest,
    native_diagnostic,
    native_root_absence,
)

PIPE_CHUNK_BYTES = 16 * 1024


def run(command: list[str], version: str, receipt: Path) -> int:
    """Keep children in the SDK-owned process group/job and drain both pipes."""
    state = {"stdout_bytes": 0, "stderr_bytes": 0, "stream_error": False}
    stderr = bytearray()

    def drain(stream: BinaryIO, forward: bool) -> None:
        try:
            with stream:
                while block := os.read(stream.fileno(), PIPE_CHUNK_BYTES):
                    key = "stdout_bytes" if forward else "stderr_bytes"
                    state[key] += len(block)
                    if forward:
                        try:
                            sys.stdout.buffer.write(block)
                            sys.stdout.buffer.flush()
                        except (BrokenPipeError, OSError):
                            state["stream_error"] = True
                    elif len(stderr) < MAX_NATIVE_STDERR_BYTES:
                        stderr.extend(block[: MAX_NATIVE_STDERR_BYTES - len(stderr)])
        except OSError:
            state["stream_error"] = True

    # Inherited stdin is byte-for-byte native input; there is no replay proxy.
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        print(json.dumps({"native_runner_failure": "spawn_error"}), file=sys.stderr, flush=True)
        return 1  # Missing control evidence is terminal; do not expose the raw exception.
    threads = [
        Thread(target=drain, args=(process.stdout, True)),
        Thread(target=drain, args=(process.stderr, False)),
    ]
    for thread in threads:
        thread.start()
    exit_code = process.wait()
    for thread in threads:
        thread.join()
    overflow = state["stderr_bytes"] > MAX_NATIVE_STDERR_BYTES
    error = stderr.decode("utf-8", errors="replace")
    payload = {
        "schema": 1,
        "command_sha256": command_digest(command),
        "native_exit": exit_code,
        **state,
        "stderr_overflow": overflow,
        "reaped": True,
        "drained": True,
        "root_absent": not overflow and native_root_absence(error, version),
        "diagnostic": native_diagnostic(error, version),
    }
    # Only a fully reaped/drained launch produces the private control receipt.
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream)
    return exit_code if exit_code >= 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the native command after --")
    return run(command, args.version, args.receipt)


if __name__ == "__main__":
    raise SystemExit(main())
