"""Docker container lifecycle utilities for TR130."""

from __future__ import annotations

import contextlib
import logging
import subprocess
import time

log = logging.getLogger("tr130.docker")


def docker_run(
    name: str,
    image: str,
    ports: dict[int, int] | None = None,
    env: dict[str, str] | None = None,
    volumes: dict[str, str] | None = None,
    args: list[str] | None = None,
    gpus: str = "all",
    shm_size: str | None = None,
) -> None:
    """Start a detached Docker container.

    Parameters
    ----------
    name : Container name (for stop/rm).
    image : Docker image (e.g. "vllm/vllm-openai:latest").
    ports : Host→container port mapping, e.g. {8000: 8000}.
    env : Environment variables passed to -e.
    volumes : Host→container volume mounts, e.g. {"/host/path": "/container/path"}.
    args : Additional args appended after image (model flags, etc).
    gpus : GPU specification (default "all").
    shm_size : Shared memory size (e.g. "1g").
    """
    cmd = ["docker", "run", "-d", "--name", name]

    if gpus:
        cmd.extend(["--gpus", gpus])

    if shm_size:
        cmd.extend(["--shm-size", shm_size])

    if ports:
        for host_port, container_port in ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])

    if env:
        for k, v in env.items():
            cmd.extend(["-e", f"{k}={v}"])

    if volumes:
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

    cmd.append(image)
    if args:
        cmd.extend(args)

    log.info("docker run: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"docker run failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    container_id = result.stdout.strip()[:12]
    log.info("Container %s started (id=%s)", name, container_id)


def docker_stop(name: str, timeout: int = 30) -> None:
    """Stop a Docker container by name."""
    log.info("Stopping container %s (timeout=%ds)", name, timeout)
    subprocess.run(
        ["docker", "stop", "-t", str(timeout), name],
        capture_output=True,
        text=True,
        timeout=timeout + 10,
    )


def docker_rm(name: str, force: bool = True) -> None:
    """Remove a Docker container by name."""
    cmd = ["docker", "rm"]
    if force:
        cmd.append("-f")
    cmd.append(name)
    subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def docker_logs(name: str, tail: int = 50) -> str:
    """Fetch recent logs from a container."""
    result = subprocess.run(
        ["docker", "logs", "--tail", str(tail), name],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout + result.stderr


def docker_is_running(name: str) -> bool:
    """Check if a container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def ensure_container_stopped(name: str) -> None:
    """Stop and remove a container if it exists. Ignore errors."""
    with contextlib.suppress(subprocess.TimeoutExpired, Exception):
        docker_stop(name, timeout=10)
    with contextlib.suppress(subprocess.TimeoutExpired, Exception):
        docker_rm(name, force=True)


def docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def docker_gpu_available() -> bool:
    """Check if Docker can access NVIDIA GPU."""
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--gpus",
                "all",
                "nvcr.io/nvidia/pytorch:26.01-py3",
                "nvidia-smi",
                "--query-gpu=name",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def wait_for_url(url: str, timeout_s: float = 180, poll_s: float = 3.0) -> bool:
    """Poll a URL until it returns 200 or timeout expires."""
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(poll_s)
    return False
