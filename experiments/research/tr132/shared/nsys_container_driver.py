"""In-container nsys driver — mounts Linux nsys into Docker for CUPTI traces.

nsys on the Windows host cannot see CUDA kernels from Docker containers due to
WSL2/WDDM isolation (confirmed by NVIDIA — architectural limitation).  The fix:
mount the Linux nsys binary into the container, override the entrypoint to
``nsys profile -- <server-cmd>``, and capture CUPTI traces from inside.

Traces are volume-mounted back to the host; stats export uses the Windows nsys
binary (``.nsys-rep`` is cross-platform).

Inherits ``stats_csv()`` and ``validate()`` from TR131's NsysDriver.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import subprocess
import time

from research.tr130.shared.docker_utils import (
    docker_is_running,
    docker_logs,
    docker_rm,
    docker_stop,
    ensure_container_stopped,
)
from research.tr131.shared.nsys_driver import NsysDriver

log = logging.getLogger("tr132.nsys_container")

# Server entrypoints per backend (use python3 — many containers lack a
# ``python`` symlink, and nsys resolves executables without shell PATH)
_SERVER_ENTRYPOINTS = {
    "vllm": ["python3", "-m", "vllm.entrypoints.openai.api_server"],
    "tgi": ["text-generation-launcher"],
}

# Internal container ports per backend
_CONTAINER_PORTS = {
    "vllm": 8000,
    "tgi": 80,
}


def _sanitize_container_name(name: str) -> str:
    """Sanitize a string for use as a Docker container name."""
    name = re.sub(r"[./:]", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return name[:80]


@dataclass
class ContainerHandle:
    """Opaque handle for a profiled container."""

    container_name: str
    backend_name: str
    trace_stem: str
    host_traces_dir: Path
    port: int
    model_hf_id: str


class NsysContainerDriver(NsysDriver):
    """Nsight Systems driver that profiles from inside Docker containers.

    Mounts the Linux nsys binary into the container as ``/nsys_bin`` and
    overrides the entrypoint to ``/nsys_bin/nsys profile --trace cuda -- <server>``.
    CUPTI injection happens inside the container where it can see the CUDA context.

    Usage::

        driver = NsysContainerDriver(nsys_path, nsys_linux_dir, cfg)
        handle = driver.start_profiled_container(
            "vllm", backend_cfg, model_cfg, "p1_val", traces_dir)
        # ... send requests via HTTP ...
        rep_path = driver.stop_profiled_container(handle)
        stats = driver.stats_csv(rep_path, reports, output_dir)
    """

    def __init__(
        self,
        nsys_path: str | Path,
        nsys_linux_dir: str | Path,
        cfg: dict | None = None,
        stop_timeout_s: int = 120,
    ):
        super().__init__(nsys_path, cfg)
        self.nsys_linux_dir = str(Path(nsys_linux_dir).resolve())
        self.stop_timeout_s = stop_timeout_s

    def _hf_cache_path(self) -> str:
        """Resolve HF cache path for volume mount."""
        hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        return str(Path(hf_home).resolve())

    def _build_docker_cmd(
        self,
        container_name: str,
        backend_name: str,
        backend_cfg: dict,
        model_hf_id: str,
        trace_name: str,
        traces_dir: Path,
    ) -> list[str]:
        """Build the full ``docker run`` command with nsys wrapping.

        nsys refuses to run directly from its ``target-linux-x64/`` directory —
        it must be invoked via a symlink from a parent directory (NVIDIA
        installation convention).  We work around this by using ``/bin/sh -c``
        as the entrypoint: create a symlink at ``/tmp/nsys`` pointing to the
        mounted binary, then ``exec`` it with the profile command.
        """
        image = backend_cfg.get("docker_image")
        port = backend_cfg.get("port", _CONTAINER_PORTS.get(backend_name, 8000))
        container_port = _CONTAINER_PORTS.get(backend_name, 8000)
        extra_args = backend_cfg.get("extra_args", [])

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--gpus",
            "all",
            "--init",
            "--cap-add",
            "SYS_ADMIN",
            "--security-opt",
            "seccomp=unconfined",
        ]

        # Port mapping
        cmd.extend(["-p", f"{port}:{container_port}"])

        # Environment
        hf_token = os.environ.get("HF_TOKEN", "")
        if hf_token:
            if backend_name == "tgi":
                cmd.extend(["-e", f"HUGGING_FACE_HUB_TOKEN={hf_token}"])
            else:
                cmd.extend(["-e", f"HF_TOKEN={hf_token}"])

        # Volume mounts
        hf_cache = self._hf_cache_path()
        if backend_name == "tgi":
            cmd.extend(["-v", f"{hf_cache}:/data"])
        else:
            cmd.extend(["-v", f"{hf_cache}:/root/.cache/huggingface"])

        # Mount the nsys target-linux-x64 directory
        cmd.extend(["-v", f"{self.nsys_linux_dir}:/nsys_root/target-linux-x64:ro"])

        # Mount traces directory for output
        host_traces = str(traces_dir.resolve())
        cmd.extend(["-v", f"{host_traces}:/traces"])

        # Shared memory for TGI
        if backend_name == "tgi":
            cmd.extend(["--shm-size", "1g"])

        # Use /bin/sh as entrypoint — we need to create a symlink first
        cmd.extend(["--entrypoint", "/bin/sh"])

        # Image
        cmd.append(image)

        # Build the server command string
        server_parts = list(_SERVER_ENTRYPOINTS.get(backend_name, []))
        if backend_name == "vllm":
            server_parts.extend(["--model", model_hf_id])
            server_parts.extend(extra_args)
        elif backend_name == "tgi":
            server_parts.extend(["--model-id", model_hf_id])
            server_parts.extend(extra_args)
        server_str = " ".join(server_parts)

        # CMD: create symlink (nsys requires invocation via symlink from
        # outside target-linux-x64/), then exec nsys profile wrapping server
        inner_cmd = (
            "ln -sf /nsys_root/target-linux-x64/nsys /tmp/nsys && "
            f"exec /tmp/nsys profile --trace cuda "
            f"-o /traces/{trace_name} -f true "
            f"-- {server_str}"
        )
        cmd.extend(["-c", inner_cmd])

        return cmd

    def start_profiled_container(
        self,
        backend_name: str,
        backend_cfg: dict,
        model_cfg: dict,
        trace_name: str,
        traces_dir: Path,
    ) -> ContainerHandle:
        """Start a Docker container with nsys wrapping the server entrypoint.

        Parameters
        ----------
        backend_name : "vllm" or "tgi".
        backend_cfg : Backend config dict (port, docker_image, extra_args, etc).
        model_cfg : Model config dict with "hf_id" and "name".
        trace_name : Stem for the trace file (e.g. "p1_validation").
        traces_dir : Host directory for trace output (volume-mounted as /traces).

        Returns
        -------
        ContainerHandle for use with stop/cancel methods.
        """
        model_hf_id = model_cfg["hf_id"]
        port = backend_cfg.get("port", _CONTAINER_PORTS.get(backend_name, 8000))

        container_name = _sanitize_container_name(
            f"tr132-nsys-{backend_name}-{trace_name}"
        )

        # Clean up any leftover container with same name
        ensure_container_stopped(container_name)

        traces_dir.mkdir(parents=True, exist_ok=True)

        cmd = self._build_docker_cmd(
            container_name=container_name,
            backend_name=backend_name,
            backend_cfg=backend_cfg,
            model_hf_id=model_hf_id,
            trace_name=trace_name,
            traces_dir=traces_dir,
        )

        log.info(
            "Starting profiled container: %s (backend=%s, model=%s)",
            container_name,
            backend_name,
            model_cfg["name"],
        )
        log.debug("Docker command: %s", cmd)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(
                f"docker run failed (rc={result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        container_id = result.stdout.strip()[:12]
        log.info("Container %s started (id=%s)", container_name, container_id)

        # Wait a few seconds for container to initialize
        time.sleep(3.0)

        # Verify container is still running (catches entrypoint errors)
        if not docker_is_running(container_name):
            logs = docker_logs(container_name, tail=50)
            ensure_container_stopped(container_name)
            raise RuntimeError(
                f"Container {container_name} exited immediately after start.\n"
                f"Logs:\n{logs}"
            )

        return ContainerHandle(
            container_name=container_name,
            backend_name=backend_name,
            trace_stem=trace_name,
            host_traces_dir=traces_dir,
            port=port,
            model_hf_id=model_hf_id,
        )

    def stop_profiled_container(self, handle: ContainerHandle) -> Path:
        """Stop the profiled container and retrieve the .nsys-rep trace.

        Sends SIGTERM via ``docker stop`` with generous timeout so nsys can
        finalize the trace.  The trace file is in the volume-mounted traces
        directory on the host.

        Returns path to the ``.nsys-rep`` file.
        """
        log.info(
            "Stopping profiled container: %s (timeout=%ds)",
            handle.container_name,
            self.stop_timeout_s,
        )

        # Fetch exit code for diagnostics
        try:
            docker_stop(handle.container_name, timeout=self.stop_timeout_s)
        except subprocess.TimeoutExpired:
            log.warning(
                "Container stop timed out after %ds — force killing",
                self.stop_timeout_s,
            )

        # Log container exit code
        try:
            inspect_result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.ExitCode}}",
                    handle.container_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if inspect_result.returncode == 0:
                exit_code = inspect_result.stdout.strip()
                log.info("Container %s exit code: %s", handle.container_name, exit_code)
        except Exception:
            pass

        # Clean up container
        with contextlib.suppress(Exception):
            docker_rm(handle.container_name, force=True)

        # Find the .nsys-rep file in the host traces directory
        expected_path = handle.host_traces_dir / f"{handle.trace_stem}.nsys-rep"
        if expected_path.exists():
            log.info(
                "Trace saved: %s (%.1f MB)",
                expected_path.name,
                expected_path.stat().st_size / 1e6,
            )
            return expected_path

        # Fallback: nsys may append a numeric suffix
        candidates = list(handle.host_traces_dir.glob(f"{handle.trace_stem}*.nsys-rep"))
        if candidates:
            rep_path = candidates[0]
            log.info(
                "Trace saved (suffixed): %s (%.1f MB)",
                rep_path.name,
                rep_path.stat().st_size / 1e6,
            )
            return rep_path

        raise FileNotFoundError(
            f"No .nsys-rep trace found in {handle.host_traces_dir} "
            f"for stem '{handle.trace_stem}'. "
            f"Check container logs for nsys errors."
        )

    def cancel_profiled_container(self, handle: ContainerHandle) -> None:
        """Force-kill a profiled container without saving the trace."""
        log.info("Cancelling profiled container: %s", handle.container_name)
        ensure_container_stopped(handle.container_name)
