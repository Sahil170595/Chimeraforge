import argparse
from datetime import datetime
import gc
import json
import logging
import os
from pathlib import Path
import sys
import time

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import yaml

# Add root to path
sys.path.append(os.getcwd())

from banterhearts.monitoring.energy import EnergyMonitor
from banterhearts.monitoring.physics import (
    BaselineCalibration,
    ExperimentClock,
    ThermalSafety,
    ThrottlingDetector,
)
from banterhearts.monitoring.vram import VRAMMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TR122_Physics")

# Define global events list to store
global_events = []
global_run_state = "completed"


def get_run_metadata(
    _args, config, poller_stats, baseline_stats, end_reason="completed"
):
    import subprocess

    try:
        git_hash = (
            subprocess.check_output(["git", "rev-parse", "HEAD"])
            .strip()
            .decode("utf-8")
        )
        git_dirty = subprocess.call(["git", "diff", "--quiet"]) != 0
    except Exception:
        git_hash = "unknown"
        git_dirty = False

    return {
        "schema_version": 2,  # V2 schema
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "run_state": global_run_state,
        "end_reason": end_reason,
        "git": {"hash": git_hash, "dirty": git_dirty},
        "hardware": {
            "gpu_name": torch.cuda.get_device_name(0),
            "driver": "unknown",
            "cuda": torch.version.cuda,
        },
        "poller": poller_stats,
        "baseline": {
            "idle_watts_mean": baseline_stats.idle_watts_mean,
            "idle_watts_std": baseline_stats.idle_watts_std,
            "idle_watts_min": getattr(baseline_stats, "idle_watts_min", 0.0),
            "idle_watts_max": getattr(baseline_stats, "idle_watts_max", 0.0),
            "idle_temp": baseline_stats.idle_temp_c,
            "fake_idle": baseline_stats.fake_idle_flag,
            "fake_idle_reasons": getattr(baseline_stats, "fake_idle_reasons", ""),
            "power_outlier_fraction": getattr(
                baseline_stats, "power_outlier_fraction", 0.0
            ),
            "clock_varied": getattr(baseline_stats, "clock_varied", False),
            "idle_gpu_util_p95": baseline_stats.idle_gpu_util_p95,
        },
        "config": config,
    }


def run_vram_cliff(config, vram_monitor):
    logger.info("=== Starting VRAM Cliff Experiment ===")
    spec = config["tests"]["vram_cliff"]
    model_name = config["models"]["stress"]

    # 1. Fragmention Stress Test (Allocator Torture)
    logger.info("Running Allocator Torture Test...")
    torch.cuda.empty_cache()

    # Capture state before
    before_stats = vram_monitor.snapshot()

    # Pattern: Many Small Blocks -> Free Alternate -> Alloc Big
    tensors = []
    block_size = 4 * 1024 * 1024  # 4 MiB
    num_blocks = 100  # ~400 MiB total

    for _ in range(num_blocks):
        tensors.append(torch.empty(block_size, dtype=torch.uint8, device="cuda"))

    # Free alternate
    tensors = tensors[::2]
    torch.cuda.synchronize()

    # Alloc Big (try to fill holes)
    try:
        big_block = torch.empty(block_size * 2, dtype=torch.uint8, device="cuda")
        del big_block
    except Exception as e:
        logger.warning(f"Optimization Torture: Alloc Big failed? {e}")

    del tensors
    torch.cuda.empty_cache()
    torch.cuda.synchronize()

    after_stats = vram_monitor.snapshot()
    logger.info(
        f"Torture Complete. Frag Before: {before_stats['fragmentation_metric']:.2f}, After: {after_stats['fragmentation_metric']:.2f}"
    )

    # 2. Binary Search for Max Context
    logger.info(f"Starting Binary Search on {model_name}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="cuda"
        )
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        return

    # Detect Model Limits
    model_limit = getattr(model.config, "max_position_embeddings", None)
    if model_limit is None:
        model_limit = getattr(
            model.config, "n_positions", 1024
        )  # Fallback for some architectures

    logger.info(f"Model Architectural Limit: {model_limit} tokens")

    # Cap configuration with reality
    high = min(spec["max_ctx"], model_limit)
    low = spec["min_ctx"]

    if low > high:
        logger.warning(
            f"Config min_ctx ({low}) > Model Limit ({high}). Adjusting low to 512."
        )
        low = min(512, high)

    max_found = 0

    # Repeat check
    for _rep in range(1):
        while low <= high:
            mid = (low + high) // 2
            # Align to 64 tokens
            mid = (mid // 64) * 64

            logger.info(f"Testing Context: {mid}")
            try:
                # Cleanup
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                gc.collect()
                time.sleep(0.5)

                # Mock Input
                inputs = torch.randint(0, 1000, (1, mid), device="cuda")

                # Inference (just prefill often enough to OOM)
                with torch.no_grad():
                    _ = model(inputs)

                max_found = mid
                low = mid + 64  # Step
            except torch.cuda.OutOfMemoryError:
                logger.info(f"OOM at {mid}")
                high = mid - 64
                torch.cuda.empty_cache()
            except Exception as e:
                logger.error(f"Error at {mid}: {e}")
                break

    logger.info(f"VRAM Cliff Result: Max Context {max_found}")
    del model
    del tokenizer
    torch.cuda.empty_cache()


def run_joule_curve(config, energy_monitor):
    logger.info("=== Starting Joule Curve Experiment ===")
    spec = config["tests"]["joule_curve"]
    model_name = config["models"]["standard"]

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="cuda"
        )
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        return

    global global_events

    # Synchronize monitor clock
    energy_monitor.clock.now_ns()

    for bs in spec["batch_sizes"]:
        for rep in range(spec["repetitions"]):
            logger.info(f"Testing Batch Size {bs} (Rep {rep+1})...")

            # Prepare Input
            prompt = spec["prompts"][0]
            inputs = tokenizer(
                [prompt] * bs,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=1024,
            ).to("cuda")
            input_len = inputs.input_ids.shape[1]

            # Sync
            torch.cuda.synchronize()
            time.sleep(1.0)

            # --- Prefill Phase ---
            # Step A: Prefill (Forward pass)
            t0 = energy_monitor.clock.now_ns()
            with torch.no_grad():
                out = model(**inputs, use_cache=True)
            torch.cuda.synchronize()
            t1 = energy_monitor.clock.now_ns()

            global_events.append(
                {
                    "event_id": f"bs{bs}_rep{rep}_prefill",
                    "phase": "prefill",
                    "t_start_ns": t0,
                    "t_end_ns": t1,
                    "input_tokens": input_len * bs,
                    "output_tokens": 0,
                    "batch_size": bs,
                    "tokens_per_second": (input_len * bs) / max(1e-9, (t1 - t0) / 1e9),
                }
            )

            # Step B: Decode
            past_key_values = out.past_key_values
            gen_tokens = spec["gen_tokens"]
            current_input = torch.argmax(out.logits[:, -1, :], dim=-1).unsqueeze(1)

            t2 = energy_monitor.clock.now_ns()
            with torch.no_grad():
                for _ in range(gen_tokens):
                    out = model(
                        current_input, past_key_values=past_key_values, use_cache=True
                    )
                    past_key_values = out.past_key_values
                    current_input = torch.argmax(
                        out.logits[:, -1, :], dim=-1
                    ).unsqueeze(1)
            torch.cuda.synchronize()
            t3 = energy_monitor.clock.now_ns()

            global_events.append(
                {
                    "event_id": f"bs{bs}_rep{rep}_decode",
                    "phase": "decode",
                    "t_start_ns": t2,
                    "t_end_ns": t3,
                    "input_tokens": 0,
                    "output_tokens": gen_tokens * bs,
                    "batch_size": bs,
                    "tokens_per_second": (gen_tokens * bs) / max(1e-9, (t3 - t2) / 1e9),
                }
            )

    del model
    del tokenizer
    torch.cuda.empty_cache()


def run_heat_soak(config, _energy_monitor, thermal_safety, throttle_detector):
    logger.info("=== Starting Heat Soak Experiment ===")
    spec = config["tests"]["heat_soak"]
    model_name = spec["model"]

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="cuda"
        )
    except Exception as e:
        logger.error(f"Failed to load {model_name}: {e}")
        return

    # Steady State Logic
    target_slope = spec["equilibrium_slope"]  # 0.5 C/min
    duration_s = spec["duration_min"] * 60
    window_s = spec["rolling_window_min"] * 60

    start_time = time.time()
    temp_history = []  # (t, temp)

    logger.info("Beginning Heat Soak Loop...")

    # Prompt
    input_ids = tokenizer(
        "The physics of thermal dynamics in silicon is complex because",
        return_tensors="pt",
    ).input_ids.to("cuda")

    state = "running"

    while (time.time() - start_time) < duration_s:
        # Check Safety
        try:
            thermal_safety.check()
        except Exception as e:
            logger.critical(f"Aborting Heat Soak: {e}")
            state = "aborted_thermal_safety"
            break

        # Run Burst
        with torch.no_grad():
            _ = model.generate(input_ids, max_new_tokens=100, do_sample=False)

        # Check Throttling
        reasons, is_thr, _src = throttle_detector.check(
            current_util=99, current_tps=100.0, current_clock=2500
        )
        if is_thr:
            logger.warning(f"Throttling Detected: {reasons}")

        # Check Equilibrium
        import pynvml

        try:
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            curr_temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            now = time.time()
            temp_history.append((now, curr_temp))
        except Exception:
            pass

        # Prune
        temp_history = [x for x in temp_history if (now - x[0]) < window_s]

        # Calc Slope
        if len(temp_history) > 10 and (temp_history[-1][0] - temp_history[0][0]) > 60:
            times = np.array([x[0] for x in temp_history])
            temps = np.array([x[1] for x in temp_history])
            slope, _ = np.polyfit(times, temps, 1)  # deg/sec
            slope_min = slope * 60  # deg/min

            logger.info(f"T={curr_temp}C, Slope={slope_min:.3f} C/min")

            if abs(slope_min) < target_slope:
                logger.info("Thermal Equilibrium Reached.")
                state = "equilibrium"
                break

    if state == "running":
        state = "timeout"

    global global_run_state
    global_run_state = state
    logger.info(f"Heat Soak Ended. State: {state}")


def main():
    parser = argparse.ArgumentParser(description="TR122 Physics of Inference Harness")
    parser.add_argument(
        "--config",
        default="research/tr122/configs/physics.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run minimal verified loop"
    )
    args = parser.parse_args()

    # Load Config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Setup Artifact Dir
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(config["experiment"]["output_dir"]) / run_id
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Init Physics Primitives
    ExperimentClock()

    # 2. Baseline Calibration
    baseline = BaselineCalibration(duration_s=120 if not args.dry_run else 5)
    baseline_stats = baseline.calibrate()

    with open(results_dir / "baseline.json", "w") as f:
        json.dump(baseline_stats.__dict__, f, indent=2)

    # 3. Start Monitors
    energy_monitor = EnergyMonitor(
        output_path=str(results_dir / "power_trace.csv"),
        poll_interval_ms=config["poller"]["target_period_ms"],
        gap_threshold_s=config["poller"]["gap_dt_threshold_s"],
    )
    vram_monitor = VRAMMonitor()
    thermal_safety = ThermalSafety()
    throttle_detector = ThrottlingDetector()

    # 4. Instrument Response Test
    # Do not start monitor here; response test manages its own thread

    response_result = {}
    if config["tests"]["instrument_response"]["enabled"]:
        response_result = energy_monitor.instrument_response_test(
            duration_s=10 if not args.dry_run else 3
        )
        logger.info(f"Instrument Response: {response_result}")

    # 5. Start Monitor for Main Experiments
    # ensure it's fresh
    energy_monitor._data = []
    energy_monitor._stop_event.clear()
    energy_monitor.start()

    # Run Experiments
    try:
        if args.dry_run:
            logger.info("DRY RUN MODE: Skipping full tests, running light smoke test")
            # Verified Load smoke test
            run_joule_curve(config, energy_monitor)
        else:
            if config["tests"]["vram_cliff"]["enabled"]:
                run_vram_cliff(config, vram_monitor)

            if config["tests"]["joule_curve"]["enabled"]:
                run_joule_curve(config, energy_monitor)

            if config["tests"]["heat_soak"]["enabled"]:
                run_heat_soak(config, energy_monitor, thermal_safety, throttle_detector)

    except Exception as e:
        logger.error(f"Experiment Aborted: {e}", exc_info=True)
        global global_run_state
        global_run_state = f"aborted_{e}"
    finally:
        # Stop Monitors
        df_trace = energy_monitor.stop()

        # Post-Process Events
        processed_events = EnergyMonitor.integrate_energy(
            df_trace,
            global_events,
            baseline_stats.idle_watts_mean,
            config["poller"]["gappy_gap_fraction_threshold"],
        )

        # Write Events
        with open(results_dir / "generation_events.jsonl", "w") as f:
            for evt in processed_events:
                f.write(json.dumps(evt) + "\n")

        # Write Metadata
        metadata = get_run_metadata(
            args, config, energy_monitor.poller_stats, baseline_stats, global_run_state
        )
        metadata["checks"] = {"instrument_response": response_result}

        with open(results_dir / "run_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Run Complete. Results in {results_dir}")


if __name__ == "__main__":
    main()
