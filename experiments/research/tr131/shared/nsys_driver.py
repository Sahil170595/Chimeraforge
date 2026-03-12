"""Nsight Systems driver — wraps nsys.exe for profiling, stats, and export."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess

log = logging.getLogger("tr131.nsys")


class NsysDriver:
    """Wrapper for NVIDIA Nsight Systems CLI."""

    def __init__(self, nsys_path: str | Path, cfg: dict | None = None):
        self.nsys = str(nsys_path)
        cfg = cfg or {}
        self.trace = cfg.get("trace", "cuda")
        self.gpuctxsw = cfg.get("gpuctxsw", True)
        self.gpu_metrics_set = cfg.get("gpu_metrics_set", "ad10x")
        self.gpu_metrics_freq = cfg.get("gpu_metrics_frequency", 10000)
        self.gpu_metrics_devices = cfg.get("gpu_metrics_devices", "0")
        self.sample = cfg.get("sample", "none")
        self.cpuctxsw = cfg.get("cpuctxsw", "none")

    # ── Profile ───────────────────────────────────────────────────────

    def profile(
        self,
        target_cmd: list[str],
        output_path: str | Path,
        duration_s: int = 30,
        extra_flags: list[str] | None = None,
    ) -> Path:
        """Run nsys profile wrapping a target command.

        Returns path to .nsys-rep file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Strip .nsys-rep suffix if present (nsys adds it automatically)
        out_stem = str(output_path)
        if out_stem.endswith(".nsys-rep"):
            out_stem = out_stem[:-9]

        cmd = [
            self.nsys,
            "profile",
            "--trace",
            self.trace,
            f"--sample={self.sample}",
            f"--cpuctxsw={self.cpuctxsw}",
            "-d",
            str(duration_s),
            "-o",
            out_stem,
            "-w",
            "true",
            "-f",
            "true",
        ]
        # Optional flags that require admin on Windows
        if self.gpuctxsw:
            cmd.extend(["--gpuctxsw=true"])
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
        cmd.extend(target_cmd)

        log.info("nsys profile: %s", " ".join(cmd[-3:]))
        log.debug("Full command: %s", cmd)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration_s + 120,  # generous timeout
        )

        # nsys may return non-zero if the target process exits before -d,
        # but still produces a valid .nsys-rep file (common with `ollama serve`).
        rep_path = Path(f"{out_stem}.nsys-rep")
        if not rep_path.exists():
            # Sometimes nsys appends a number
            candidates = list(rep_path.parent.glob(f"{rep_path.stem}*.nsys-rep"))
            if candidates:
                rep_path = candidates[0]
            else:
                # Only raise if we truly have no output file
                if result.returncode != 0:
                    log.error("nsys profile failed (exit %d)", result.returncode)
                    log.error("stderr: %s", result.stderr[:2000])
                    log.error("stdout: %s", result.stdout[:2000])
                    raise RuntimeError(f"nsys profile failed: {result.stderr[:500]}")
                raise FileNotFoundError(f"nsys-rep file not found: {rep_path}")

        if result.returncode != 0:
            log.warning(
                "nsys exited with code %d but .nsys-rep was generated",
                result.returncode,
            )

        log.info(
            "Trace saved: %s (%.1f MB)", rep_path.name, rep_path.stat().st_size / 1e6
        )
        return rep_path

    # ── Stats (CSV reports) ───────────────────────────────────────────

    def stats_csv(
        self,
        nsys_rep_path: str | Path,
        reports: list[str],
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """Run nsys stats for multiple reports, output as CSV.

        Returns {report_name: csv_path}.
        """
        nsys_rep_path = Path(nsys_rep_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        for report in reports:
            out_base = output_dir / f"{nsys_rep_path.stem}_{report}"
            cmd = [
                self.nsys,
                "stats",
                "--report",
                report,
                "--format",
                "csv",
                "-o",
                str(out_base),
                "--force-overwrite",
                "true",
                "--force-export",
                "true",
                str(nsys_rep_path),
            ]
            log.debug("nsys stats: %s", report)
            ret = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if ret.returncode != 0:
                log.warning("nsys stats %s failed: %s", report, ret.stderr[:300])
                continue

            # nsys stats appends _report_name.csv
            csv_candidates = list(output_dir.glob(f"{out_base.name}*.csv"))
            if csv_candidates:
                results[report] = csv_candidates[0]
                log.debug("  -> %s", csv_candidates[0].name)
            else:
                log.warning("No CSV output for report %s", report)

        return results

    # ── Export to SQLite ──────────────────────────────────────────────

    def export_sqlite(
        self,
        nsys_rep_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        """Export .nsys-rep to SQLite."""
        nsys_rep_path = Path(nsys_rep_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.nsys,
            "export",
            "-t",
            "sqlite",
            "-o",
            str(output_path),
            "-f",
            "true",
            str(nsys_rep_path),
        ]
        log.debug("nsys export sqlite: %s", output_path.name)
        ret = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if ret.returncode != 0:
            log.warning("nsys export failed: %s", ret.stderr[:300])
            raise RuntimeError(f"nsys export failed: {ret.stderr[:300]}")

        log.info(
            "SQLite export: %s (%.1f MB)",
            output_path.name,
            output_path.stat().st_size / 1e6,
        )
        return output_path

    # ── Validate ──────────────────────────────────────────────────────

    def validate(self) -> dict:
        """Quick validation: check nsys is reachable and report features."""
        validation = {"nsys_ok": False, "features": {}}
        try:
            ret = subprocess.run(
                [self.nsys, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if ret.returncode == 0:
                validation["nsys_ok"] = True
                validation["version"] = ret.stdout.strip()
        except Exception as e:
            validation["error"] = str(e)
        return validation
