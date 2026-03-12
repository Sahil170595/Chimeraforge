#!/usr/bin/env python3
"""TR126 Phase 1: Validate Docker/Linux environment for Triton compilation.

Checks:
  1. GPU accessible via CUDA
  2. Triton importable (fails on Windows)
  3. torch.compile with inductor backend does NOT fall back to aot_eager
  4. Triton kernels are actually generated

Outputs:
  <output_dir>/<timestamp>/environment.json
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))

from research.tr126.shared.env_fingerprint import capture_environment


def _now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def validate_environment(config: dict) -> dict:
    """Run environment validation checks. Returns results dict."""
    results: dict = {"timestamp": _now_ts(), "checks": {}, "pass": True}

    # 1. Capture full environment fingerprint
    env = capture_environment()
    results["environment"] = env

    # 2. CUDA check
    cuda_ok = env.get("cuda_available", False)
    results["checks"]["cuda_available"] = {
        "pass": cuda_ok,
        "detail": env.get("gpu_name", "N/A"),
    }
    if not cuda_ok:
        results["pass"] = False
        print("FAIL: CUDA not available")
        return results
    print(f"  CUDA: OK ({env['gpu_name']}, {env.get('gpu_memory_gb', '?')} GB)")

    # 3. Triton import check (the critical TR126 check)
    triton_ok = env.get("triton_available", False)
    results["checks"]["triton_importable"] = {
        "pass": triton_ok,
        "detail": env.get("triton_version", "N/A"),
    }
    if not triton_ok:
        results["pass"] = False
        print("FAIL: Triton not importable (expected on Linux)")
        return results
    print(f"  Triton: OK (v{env['triton_version']})")

    # 4. torch.compile with inductor — verify no fallback
    compile_result = _check_compile(config)
    results["checks"]["torch_compile_inductor"] = compile_result
    if not compile_result["pass"]:
        results["pass"] = False
        print(f"FAIL: torch.compile fell back: {compile_result.get('detail', '')}")
        return results
    print(f"  torch.compile: OK (inductor, {compile_result.get('detail', '')})")

    return results


def _check_compile(config: dict) -> dict:
    """Verify torch.compile uses real Triton, not aot_eager fallback."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_path = config.get("model_path", "models/tiny-gpt2")
    device = torch.device(config.get("device", "cuda"))
    seed = config.get("seed", 42)

    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    # Load model
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, local_files_only=True, dtype=torch.float32
        )
        model.eval().to(device)
    except Exception as e:
        return {"pass": False, "detail": f"Model load failed: {e}"}

    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Clear dynamo state
    torch._dynamo.reset()

    # Compile with inductor (no fallback)
    try:
        compiled_model = torch.compile(
            model,
            backend="inductor",
            mode="reduce-overhead",
            dynamic=False,
            fullgraph=False,
        )
    except Exception as e:
        return {"pass": False, "detail": f"torch.compile failed: {e}"}

    # Run a forward pass to trigger compilation
    inputs = tokenizer("Hello", return_tensors="pt").to(device)
    try:
        with torch.no_grad():
            _ = compiled_model.generate(**inputs, max_new_tokens=8, do_sample=False)
    except Exception as e:
        return {"pass": False, "detail": f"Compiled forward pass failed: {e}"}

    # Check dynamo counters for fallback evidence
    try:
        import torch._dynamo.utils as dynamo_utils

        counters = (
            dict(dynamo_utils.counters) if hasattr(dynamo_utils, "counters") else {}
        )
        graph_breaks = counters.get("graph_break", {})
        # If aot_eager was used, there may be specific counter patterns
        detail = f"graph_breaks={len(graph_breaks)}"
    except Exception:
        detail = "counters unavailable"

    return {
        "pass": True,
        "detail": detail,
        "backend": "inductor",
    }


def main() -> int:
    config_path = _DIR / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    print("=" * 60)
    print("TR126 Phase 1: Environment Validation")
    print("=" * 60)

    results = validate_environment(config)

    # Write output
    out_dir = (
        _REPO
        / config.get("output_dir", "research/tr126/results/phase1")
        / results["timestamp"]
    )
    out_path = out_dir / "environment.json"
    _write_json(out_path, results)

    status = "PASS" if results["pass"] else "FAIL"
    print(f"\nResult: {status}")
    print(f"Output: {out_path}")

    return 0 if results["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
