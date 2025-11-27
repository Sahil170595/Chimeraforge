"""
TR117 Phase 2: Hardware Forensics (dmon wrapper)

Polls nvidia-smi at ~100ms during a command execution and writes gpu_metrics.csv.
Usage: python dmon_wrapper.py --output-dir <dir> -- <command>
"""

import subprocess
import time
import argparse
import sys
from pathlib import Path
import threading


def monitor_gpu(output_file: Path, stop_event: threading.Event):
    # WDDM often lacks PCIe counters; stick to fields that work on Windows
    query = "timestamp,power.draw,utilization.gpu,memory.used"
    header = "timestamp,power.draw [W],utilization.gpu [%],memory.used [MiB]\n"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header)
        while not stop_event.is_set():
            try:
                raw = (
                    subprocess.check_output(
                        [
                            "nvidia-smi",
                            f"--query-gpu={query}",
                            "--format=csv,noheader",
                        ],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode("utf-8")
                    .strip()
                )
                if raw:
                    f.write(f"{raw}\n")
                    f.flush()
            except Exception:
                pass
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.command:
        print("No command specified")
        sys.exit(1)

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_gpu, args=(output_dir / "gpu_metrics.csv", stop_event))
    monitor_thread.start()

    print(f"Starting GPU monitor and command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd)
        exit_code = result.returncode
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        stop_event.set()
        monitor_thread.join()

    print(f"Command finished with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
