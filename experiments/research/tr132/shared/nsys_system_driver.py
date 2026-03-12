"""System-wide nsys driver — captures Docker GPU kernels from the host.

Strategy: `nsys profile` wraps a dummy Python sleep process.  While nsys
profiles that process, it captures ALL system-wide CUDA activity including
Docker containers.  To stop, we remove a sentinel file — the sleep script
exits, nsys collects data and writes the .nsys-rep report.

Inherits stats_csv() and validate() from NsysDriver unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import subprocess
import sys
import time

from research.tr131.shared.nsys_driver import NsysDriver

log = logging.getLogger("tr132.nsys_system")

# Duration for the dummy sleep (generous upper bound; stopped early via sentinel)
_MAX_CAPTURE_S = 600


@dataclass
class SessionHandle:
    """Opaque handle returned by start_session, passed to stop_session."""

    session_name: str
    output_stem: str
    sentinel_path: Path
    process: subprocess.Popen = field(repr=False)


class NsysSystemDriver(NsysDriver):
    """Nsight Systems driver with system-wide capture via background profile.

    Usage::

        driver = NsysSystemDriver(nsys_path, cfg)
        handle = driver.start_session(output_path, session_name="tr132_cap")
        # ... run workload (Docker vLLM, etc.) ...
        rep_path = driver.stop_session(handle)
        stats = driver.stats_csv(rep_path, reports, output_dir)
    """

    def start_session(
        self,
        output_path: str | Path,
        session_name: str = "tr132",
        extra_flags: list[str] | None = None,
    ) -> SessionHandle:
        """Start a system-wide nsys capture.

        Launches ``nsys profile`` in the background wrapping a Python sleep
        script that polls a sentinel file.  All CUDA activity on the system
        (including Docker containers) is captured.

        Returns a SessionHandle that must be passed to stop_session().
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        out_stem = str(output_path)
        if out_stem.endswith(".nsys-rep"):
            out_stem = out_stem[:-9]

        # Sentinel file: sleep script exits when this file is removed
        sentinel = Path(f"{out_stem}.sentinel")
        sentinel.touch()

        # Python one-liner that sleeps until sentinel is gone
        sleep_script = (
            "import time,pathlib,sys;"
            f"p=pathlib.Path(r'{sentinel}');"
            f"[time.sleep(0.3) for _ in iter(lambda:p.exists(),False)]"
        )

        cmd = [
            self.nsys,
            "profile",
            "--trace",
            self.trace,
            f"--sample={self.sample}",
            f"--cpuctxsw={self.cpuctxsw}",
            "-d",
            str(_MAX_CAPTURE_S),
            "-o",
            out_stem,
            "-f",
            "true",
        ]
        if self.gpuctxsw:
            cmd.append("--gpuctxsw=true")
        if self.gpu_metrics_set:
            cmd.extend(
                [
                    "--gpu-metrics-set",
                    self.gpu_metrics_set,
                    "--gpu-metrics-devices",
                    str(self.gpu_metrics_devices),
                    "--gpu-metrics-frequency",
                    str(self.gpu_metrics_freq),
                ]
            )
        if extra_flags:
            cmd.extend(extra_flags)

        # The wrapped command: Python sleep-until-sentinel
        cmd.extend([sys.executable, "-c", sleep_script])

        log.info("nsys profile start (session=%s)", session_name)
        log.debug("Full command: %s", cmd)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Give nsys a moment to initialize before returning
        time.sleep(2.0)

        if proc.poll() is not None:
            # Process exited immediately — something went wrong
            _, stderr = proc.communicate(timeout=5)
            sentinel.unlink(missing_ok=True)
            raise RuntimeError(
                f"nsys profile exited immediately (code={proc.returncode}): "
                f"{stderr.decode(errors='replace')[:500]}"
            )

        log.info("nsys capture running (pid=%d, sentinel=%s)", proc.pid, sentinel.name)

        return SessionHandle(
            session_name=session_name,
            output_stem=out_stem,
            sentinel_path=sentinel,
            process=proc,
        )

    def stop_session(self, handle: SessionHandle) -> Path:
        """Stop a running capture by removing the sentinel file.

        The wrapped Python script exits, nsys collects data, and writes
        the .nsys-rep report.  Returns path to the report file.
        """
        log.info("nsys stop (session=%s) — removing sentinel", handle.session_name)

        # Remove sentinel → Python script exits → nsys saves report
        handle.sentinel_path.unlink(missing_ok=True)

        # Wait for nsys to finish writing the report
        try:
            _stdout, stderr = handle.process.communicate(timeout=120)
            log.debug("nsys exit code: %d", handle.process.returncode)
            if stderr:
                output = stderr.decode(errors="replace")
                if "error" in output.lower():
                    log.warning("nsys stderr: %s", output[:500])
        except subprocess.TimeoutExpired:
            log.warning("nsys did not exit within 120s — killing")
            handle.process.kill()
            handle.process.wait(timeout=10)

        # Find the .nsys-rep file
        rep_path = Path(f"{handle.output_stem}.nsys-rep")
        if not rep_path.exists():
            # nsys sometimes appends a number suffix
            candidates = list(
                rep_path.parent.glob(f"{Path(handle.output_stem).name}*.nsys-rep")
            )
            if candidates:
                rep_path = candidates[0]
            else:
                raise FileNotFoundError(
                    f"nsys-rep file not found after stop: {rep_path}"
                )

        log.info(
            "Trace saved: %s (%.1f MB)", rep_path.name, rep_path.stat().st_size / 1e6
        )
        return rep_path

    def cancel_session(self, handle_or_name: SessionHandle | str) -> None:
        """Cancel a running capture without saving (cleanup on error)."""
        if isinstance(handle_or_name, SessionHandle):
            handle_or_name.sentinel_path.unlink(missing_ok=True)
            try:
                handle_or_name.process.kill()
                handle_or_name.process.wait(timeout=10)
            except Exception:
                pass
            log.info("nsys session '%s' cancelled", handle_or_name.session_name)
        else:
            # Legacy string-based cancel (try nsys cancel command)
            try:
                subprocess.run(
                    [self.nsys, "cancel", "--session", handle_or_name],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                log.info("nsys session '%s' cancelled", handle_or_name)
            except Exception as e:
                log.warning("Failed to cancel nsys session: %s", e)
