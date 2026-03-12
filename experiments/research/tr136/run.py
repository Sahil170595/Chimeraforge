"""TR136: Run cross-backend safety consistency experiment.

Usage:
    python research/tr136/run.py [-v] [--skip-prep] [--skip-eval] [--skip-judge]
      [--backends BACKEND,...] [--models MODEL,...]

Steps:
  1. Prepare benchmarks (copy TR134 safety tasks)
  2. For each (backend, model): start backend, run all safety prompts, stop
  3. Run LLM judge post-hoc
  4. Analyze (safety per backend, pairwise agreement, response divergence)
  5. Generate report

Backends run sequentially (they compete for GPU VRAM).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr130.shared.backends import create_backend, ServingBackend
from research.tr130.shared.docker_utils import docker_available, docker_gpu_available
from research.tr136.shared.utils import (
    TR136_MODELS,
    TR136_BACKEND_CONFIGS,
    get_ollama_quant_tag,
)

logger = logging.getLogger("tr136.run")


def _load_prompts(task_dir: Path) -> list[dict]:
    """Load all prompts from task YAML files."""
    prompts = []
    for path in sorted(task_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        task_name = data.get("name", path.stem)
        task_type = data.get("type", "unknown")
        template = data.get("prompt_template", "{instruction}")
        for sample in data.get("samples", []):
            prompt_text = template
            for key, val in sample.items():
                prompt_text = prompt_text.replace("{{ " + key + " }}", str(val))
            prompts.append(
                {
                    "task_name": task_name,
                    "task_type": task_type,
                    "sample_id": sample.get("id", ""),
                    "prompt": prompt_text,
                    "reference": sample.get("reference", ""),
                    "correct_answers": sample.get("correct_answers", []),
                    "incorrect_answers": sample.get("incorrect_answers", []),
                    "sample_meta": {
                        k: v
                        for k, v in sample.items()
                        if k
                        in (
                            "category",
                            "stereotyped_idx",
                            "anti_stereotyped_idx",
                            "answer_choice_0",
                            "answer_choice_1",
                            "answer_choice_2",
                            "context",
                            "question",
                            "jailbreak_type",
                            "instruction",
                        )
                    },
                }
            )
    return prompts


async def _run_backend_eval(
    backend: ServingBackend,
    backend_label: str,
    model_name: str,
    prompts: list[dict],
    max_tokens: int,
    seed: int,
) -> list[dict]:
    """Run all prompts through a single backend, return records."""
    records = []
    for i, p in enumerate(prompts):
        t0 = time.perf_counter()
        try:
            result = await backend.generate(
                prompt=p["prompt"],
                max_tokens=max_tokens,
                temperature=0.0,
                seed=seed,
            )
            wall_ms = result.wall_ms
            response_text = result.response_text
            status = result.status
            prompt_tokens = result.prompt_tokens
            completion_tokens = result.completion_tokens
        except Exception as exc:
            wall_ms = (time.perf_counter() - t0) * 1000
            response_text = ""
            status = f"error: {exc}"
            prompt_tokens = 0
            completion_tokens = 0

        record = {
            "model": model_name,
            "model_name": model_name,
            "backend": backend.name,
            "backend_label": backend_label,
            "quant": backend.quantization,
            "task_name": p["task_name"],
            "task_type": p["task_type"],
            "sample_id": p["sample_id"],
            "prompt": p["prompt"],
            "candidate": response_text,
            "reference": str(p["reference"]) if p["reference"] else "",
            "correct_answers": p["correct_answers"],
            "incorrect_answers": p["incorrect_answers"],
            "sample_meta": p["sample_meta"],
            "wall_ms": round(wall_ms, 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "status": status,
            "seed": seed,
            "repetition": 0,
        }
        records.append(record)

        if (i + 1) % 50 == 0:
            logger.info(
                "  %s/%s: %d/%d (wall=%.0fms)",
                backend_label,
                model_name,
                i + 1,
                len(prompts),
                wall_ms,
            )

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="TR136 cross-backend safety")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--skip-prep", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument(
        "--backends",
        type=str,
        default=None,
        help="Comma-separated backend labels to run (default: all)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model names to run (default: all)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with open(_DIR / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    max_tokens = config["max_new_tokens"]
    seed = config["seed"]
    cooldown = config.get("cooldown_between_backends_s", 10)

    # Pre-flight: check Docker if any non-Ollama backends are selected
    needs_docker = any(b["name"] != "ollama" for b in TR136_BACKEND_CONFIGS)
    if needs_docker and not args.skip_eval:
        if not docker_available():
            print(
                "ERROR: Docker is required for vLLM/TGI backends but is not available."
            )
            print("       Start Docker Desktop or install Docker Engine, then retry.")
            return 1
        if not docker_gpu_available():
            print("WARNING: Docker GPU access not detected. vLLM/TGI may fail.")
            print("         Ensure nvidia-container-toolkit is installed.")

    # Filter backends/models if specified
    backend_configs = TR136_BACKEND_CONFIGS
    models = TR136_MODELS
    if args.backends:
        allowed = set(args.backends.split(","))
        backend_configs = [b for b in backend_configs if b["label"] in allowed]
    if args.models:
        allowed = set(args.models.split(","))
        models = [m for m in models if m["name"] in allowed]

    # Step 1: Prepare benchmarks
    if not args.skip_prep:
        print("=== Step 1: Preparing benchmarks ===")
        prep_cmd = [sys.executable, str(_DIR / "prepare_benchmarks.py")]
        if args.verbose:
            prep_cmd.append("-v")
        result = subprocess.run(prep_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("ERROR: Benchmark preparation failed")
            return result.returncode

    # Step 2: Run evaluation
    if not args.skip_eval:
        print("\n=== Step 2: Running cross-backend safety evaluation ===")
        task_dir = _DIR / "tasks"
        prompts = _load_prompts(task_dir)
        logger.info("Loaded %d prompts", len(prompts))

        run_ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run_dir = _REPO / config["output_dir"] / run_ts
        run_dir.mkdir(parents=True, exist_ok=True)

        with open(run_dir / "config_snapshot.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        samples_path = run_dir / "samples.jsonl"
        all_records: list[dict] = []

        for bcfg in backend_configs:
            backend_name = bcfg["name"]
            backend_label = bcfg["label"]
            quant = bcfg["quant"]
            cfg = {**config["backends"].get(backend_name, {}), **bcfg.get("config", {})}

            for model in models:
                model_name = model["name"]
                logger.info("=== %s / %s ===", backend_label, model_name)

                # Determine model identifiers for this backend
                if backend_name == "ollama":
                    ollama_tag = get_ollama_quant_tag(model["ollama_tag"], quant)
                    hf_id = model["hf_id"]
                else:
                    ollama_tag = None
                    hf_id = model["hf_id"]

                # Create and start backend
                backend = create_backend(backend_name, cfg)
                backend.quantization = quant
                try:
                    backend.start(model_hf_id=hf_id, model_ollama_tag=ollama_tag)
                except Exception as e:
                    logger.error("Failed to start %s: %s", backend_label, e)
                    continue

                # Warmup
                try:
                    warmup_info = backend.warmup(
                        prompt="Hello",
                        n=config.get("warmup_requests", 3),
                        max_tokens=16,
                    )
                    logger.info("Warmup: %s", warmup_info)
                except Exception as e:
                    logger.warning("Warmup failed: %s", e)

                # Run prompts
                t_eval = time.perf_counter()
                records = asyncio.run(
                    _run_backend_eval(
                        backend,
                        backend_label,
                        model_name,
                        prompts,
                        max_tokens,
                        seed,
                    )
                )
                elapsed = time.perf_counter() - t_eval

                all_records.extend(records)
                n_ok = sum(1 for r in records if r["status"] == "ok")
                logger.info(
                    "%s/%s: %d/%d ok, %.1fs",
                    backend_label,
                    model_name,
                    n_ok,
                    len(records),
                    elapsed,
                )

                # Stop backend
                try:
                    backend.stop()
                except Exception as e:
                    logger.warning("Stop failed: %s", e)

                # Cooldown between runs
                if cooldown > 0:
                    logger.info("Cooldown %ds...", cooldown)
                    time.sleep(cooldown)

        # Write samples
        with open(samples_path, "w", encoding="utf-8") as f:
            for rec in all_records:
                f.write(json.dumps(rec, default=str) + "\n")
        logger.info("Wrote %d records to %s", len(all_records), samples_path)

    # Resolve run_dir for downstream steps (avoids find_latest_run race condition)
    if not args.skip_eval:
        # run_dir was set during eval above
        run_dir_arg = ["--run-dir", str(run_dir)]
    else:
        run_dir_arg = []  # let downstream steps use find_latest_run

    # Step 3: LLM judge
    if not args.skip_judge:
        print("\n=== Step 3: Running LLM judge ===")
        judge_cmd = [sys.executable, str(_DIR / "judge_analysis.py")]
        if args.verbose:
            judge_cmd.append("-v")
        judge_cmd.extend(run_dir_arg)
        result = subprocess.run(judge_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("WARNING: Judge analysis failed (non-fatal)")

    # Step 4: Analyze
    print("\n=== Step 4: Running analysis ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if args.verbose:
        analyze_cmd.append("-v")
    analyze_cmd.extend(run_dir_arg)
    result = subprocess.run(analyze_cmd, cwd=_REPO)
    if result.returncode != 0:
        print("ERROR: Analysis failed")
        return result.returncode

    # Step 5: Generate report
    print("\n=== Step 5: Generating report ===")
    report_cmd = [sys.executable, str(_DIR / "generate_report.py")]
    if args.verbose:
        report_cmd.append("-v")
    report_cmd.extend(run_dir_arg)
    result = subprocess.run(report_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
