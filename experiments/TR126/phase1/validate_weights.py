#!/usr/bin/env python3
"""TR126 Phase 1: Validate weight parity across platforms.

Loads tiny-gpt2, runs greedy decode on fixed prompts, and records output
tokens + logit statistics. When a Windows reference snapshot exists,
compares logits within tolerance.

Outputs:
  <output_dir>/<timestamp>/weight_parity.json
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))


def _now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def validate_weights(config: dict) -> dict:
    """Load model, run greedy decode, record outputs for cross-platform comparison."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_path = config["model_path"]
    device_str = config.get("device", "cuda")
    dtype_str = config.get("dtype", "fp32")
    seed = config.get("seed", 42)
    max_new_tokens = config.get("max_new_tokens", 32)
    prompts = config.get("reference_prompts", ["Hello"])

    device = torch.device(device_str if torch.cuda.is_available() else "cpu")
    torch_dtype = torch.float16 if dtype_str == "fp16" else torch.float32

    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    print(f"  Loading model: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, local_files_only=True, dtype=torch_dtype
    )
    model.eval().to(device)

    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    results: dict[str, Any] = {
        "timestamp": _now_ts(),
        "model_path": model_path,
        "device": str(device),
        "dtype": dtype_str,
        "seed": seed,
        "platform": "linux-docker",
        "prompts": [],
    }

    for prompt in prompts:
        print(f"  Prompt: {prompt!r}")
        inputs = tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                return_dict_in_generate=True,
                output_scores=True,
            )

        generated_ids = outputs.sequences[0][inputs["input_ids"].shape[1] :]
        generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Capture logit statistics for cross-platform comparison
        logit_stats: list[dict[str, float]] = []
        if outputs.scores:
            for step_logits in outputs.scores:
                l = step_logits[0].float().cpu().numpy()
                logit_stats.append(
                    {
                        "mean": float(np.mean(l)),
                        "std": float(np.std(l)),
                        "min": float(np.min(l)),
                        "max": float(np.max(l)),
                        "argmax": int(np.argmax(l)),
                    }
                )

        prompt_result = {
            "prompt": prompt,
            "generated_text": generated_text,
            "generated_token_ids": generated_ids.cpu().tolist(),
            "num_tokens": len(generated_ids),
            "logit_stats": logit_stats,
        }
        results["prompts"].append(prompt_result)
        print(f"    Output ({len(generated_ids)} tokens): {generated_text[:80]}...")

    # Compare with Windows reference if available
    ref_path = _DIR / "windows_reference.json"
    if ref_path.is_file():
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        comparison = _compare_references(results, ref, config)
        results["cross_platform_comparison"] = comparison
        status = "MATCH" if comparison["match"] else "DIVERGED"
        print(f"  Cross-platform comparison: {status}")
    else:
        print("  No Windows reference found — saving as new reference")
        results["cross_platform_comparison"] = {"match": None, "detail": "no reference"}

    return results


def _compare_references(linux: dict, windows: dict, config: dict) -> dict:
    """Compare Linux vs Windows decode outputs."""
    dtype = config.get("dtype", "fp32")
    tol_key = f"tolerance_{dtype}"
    tolerance = config.get(tol_key, 1e-4)

    match = True
    details: list[str] = []

    for i, (lp, wp) in enumerate(
        zip(linux["prompts"], windows["prompts"], strict=False)
    ):
        # Token sequence match
        if lp["generated_token_ids"] != wp["generated_token_ids"]:
            match = False
            details.append(f"Prompt {i}: token sequence mismatch")
            continue

        # Logit statistics match
        for j, (ls, ws) in enumerate(
            zip(lp["logit_stats"], wp["logit_stats"], strict=False)
        ):
            for key in ["mean", "std", "min", "max"]:
                diff = abs(ls[key] - ws[key])
                if diff > tolerance:
                    match = False
                    details.append(
                        f"Prompt {i} step {j}: {key} diff={diff:.6f} > tol={tolerance}"
                    )

    return {
        "match": match,
        "tolerance": tolerance,
        "dtype": dtype,
        "details": details[:20],  # Cap to avoid huge output
    }


def main() -> int:
    config_path = _DIR / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    print("=" * 60)
    print("TR126 Phase 1: Weight Parity Validation")
    print("=" * 60)

    results = validate_weights(config)

    out_dir = (
        _REPO
        / config.get("output_dir", "research/tr126/results/phase1")
        / results["timestamp"]
    )
    out_path = out_dir / "weight_parity.json"
    _write_json(out_path, results)

    print(f"\nOutput: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
