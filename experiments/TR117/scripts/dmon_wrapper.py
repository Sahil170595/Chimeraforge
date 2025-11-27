"""
TR117 Phase 2: Hardware Forensics (dmon wrapper)

Wraps nvidia-smi query to log GPU metrics at 100ms resolution during a command execution.
Usage: python dmon_wrapper.py --output-dir <dir> -- <command>
"""

import subprocess
import time
import argparse
import signal
import sys
from pathlib import Path
import threading

def monitor_gpu(output_file: Path, stop_event: threading.Event):
    # nvidia-smi --query-gpu=timestamp,power.draw,utilization.gpu,memory.used,pcie.rx,pcie.tx --format=csv -lms 100
    # Note: -lms might not be supported on all versions, or might be -l ms. 
    # Standard is -l (seconds) or -lms (milliseconds) on newer versions.
    # If -lms fails, we might need a loop in python calling it, but that's slow.
    # Let's try the command.
    
    cmd = [
        "nvidia-smi",
        "--query-gpu=timestamp,power.draw,utilization.gpu,memory.used,pcie.rx,pcie.tx",
        "--format=csv",
        "-lms", "100"
    ]
    
    with open(output_file, "w") as f:
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE)
        
        while not stop_event.is_set():
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    
    if not args.command:
        print("No command specified")
        sys.exit(1)
        
    # Remove '--' if present
    cmd = args.command
    if cmd[0] == "--":
        cmd = cmd[1:]
        
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_gpu, args=(output_dir / "gpu_metrics.csv", stop_event))
    monitor_thread.start()
    
    print(f"Starting GPU monitor and command: {' '.join(cmd)}")
    start_time = time.time()
    
    try:
        # Run the actual benchmark
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
