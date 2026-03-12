"""TR123 pre-flight validation.

Checks CUDA, VRAM budget, model availability (downloads if needed),
backend imports, HuggingFace authentication for gated models,
and disk space before committing to a multi-hour benchmark run.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

import yaml


def _check_cuda() -> tuple[bool, str]:
    try:
        import torch

        if not torch.cuda.is_available():
            return False, "CUDA not available"
        name = torch.cuda.get_device_name(0)
        mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        return True, f"{name} ({mem_gb:.1f} GB)"
    except ImportError:
        return False, "torch not installed"


def _check_vram() -> tuple[float, str]:
    """Return (total_vram_gb, message)."""
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0, "CUDA not available"
        total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        free = torch.cuda.mem_get_info(0)[0] / (1024**3)
        return total, f"{total:.1f} GB total, {free:.1f} GB free"
    except Exception:
        return 0.0, "Could not query VRAM"


def _check_hf_token() -> tuple[bool, str]:
    """Check if HuggingFace token is available (needed for gated models)."""
    # Check env var
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return True, "HF_TOKEN env var set"

    # Check huggingface-cli login (cached token)
    try:
        from huggingface_hub import HfFolder

        stored = HfFolder.get_token()
        if stored:
            return True, "Token from huggingface-cli login"
    except Exception:
        pass

    return False, "No HF token found (run `huggingface-cli login` for gated models)"


def _check_model(
    path: str,
    gated: bool = False,
    trust_remote_code: bool = False,
    fp16_vram_gb: float = 0.0,
    vram_total_gb: float = 0.0,
) -> tuple[bool, str]:
    """Check model availability. Downloads if not cached."""
    # VRAM budget check
    if fp16_vram_gb > 0 and vram_total_gb > 0:
        needed = fp16_vram_gb + 2.0  # model weights + overhead
        if needed > vram_total_gb:
            return (
                False,
                f"Needs ~{needed:.1f} GB VRAM, only {vram_total_gb:.1f} GB available",
            )

    try:
        from transformers import AutoConfig, AutoTokenizer

        # Try loading config first (fast, validates access)
        config = AutoConfig.from_pretrained(path, trust_remote_code=trust_remote_code)

        # Try loading tokenizer (validates download)
        AutoTokenizer.from_pretrained(path, trust_remote_code=trust_remote_code)

        # Report model size from config
        if hasattr(config, "num_hidden_layers"):
            n_layers = config.num_hidden_layers
            hidden = getattr(config, "hidden_size", "?")
            n_kv = getattr(
                config,
                "num_key_value_heads",
                getattr(config, "num_attention_heads", "?"),
            )
            return (
                True,
                f"{n_layers}L, d={hidden}, kv_heads={n_kv}, vocab={config.vocab_size}",
            )
        return True, f"Config loaded, vocab={config.vocab_size}"

    except OSError as e:
        error_str = str(e)
        if "gated" in error_str.lower() or "401" in error_str or "403" in error_str:
            return (
                False,
                f"Gated model — run `huggingface-cli login` and accept license at https://huggingface.co/{path}",
            )
        if "404" in error_str or "does not appear to have" in error_str:
            return False, f"Model not found: {path}"
        return False, str(e)
    except Exception as e:
        return False, str(e)


def _check_onnx() -> tuple[bool, str]:
    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
        return True, ", ".join(providers)
    except ImportError:
        return False, "onnxruntime not installed"


def _check_disk(results_dir: Path) -> tuple[bool, str]:
    results_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(results_dir)
    free_gb = usage.free / (1024**3)
    ok = free_gb > 1.0
    return ok, f"{free_gb:.1f} GB free"


def run_smoke_test(config_path: str | Path) -> bool:
    config_path = Path(config_path)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    print("=" * 60)
    print("TR123 Smoke Test — KV-Cache Production Economics")
    print("=" * 60)

    all_ok = True
    warnings = []

    # CUDA
    ok, msg = _check_cuda()
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] CUDA: {msg}")
    gpu_backends = [b for b in cfg["backends"] if "gpu" in b]
    if not ok and gpu_backends:
        all_ok = False

    # VRAM
    vram_total, vram_msg = _check_vram()
    print(f"  [INFO] VRAM: {vram_msg}")

    # HuggingFace token
    has_gated = any(m.get("gated", False) for m in cfg["models"])
    if has_gated:
        print()
        ok, msg = _check_hf_token()
        status = "PASS" if ok else "WARN"
        print(f"  [{status}] HuggingFace Auth: {msg}")
        if not ok:
            gated_names = [m["name"] for m in cfg["models"] if m.get("gated")]
            warnings.append(
                f"Gated models ({', '.join(gated_names)}) may fail without HF token"
            )

    # Models
    print()
    print("  Models:")
    backend_skip = cfg.get("backend_skip", {})
    for m in cfg["models"]:
        model_skips = backend_skip.get(m["name"], [])
        active_backends = [b for b in cfg["backends"] if b not in model_skips]

        ok, msg = _check_model(
            m["path"],
            gated=m.get("gated", False),
            trust_remote_code=m.get("trust_remote_code", False),
            fp16_vram_gb=m.get("fp16_vram_gb", 0.0),
            vram_total_gb=vram_total,
        )
        status = "PASS" if ok else "FAIL"
        backends_str = ", ".join(active_backends)
        print(
            f"    [{status}] {m['name']} ({m.get('params_m', '?')}M, "
            f"{m.get('attention_type', '?')}): {msg}"
        )
        print(f"           Backends: {backends_str}")
        if not ok:
            if m.get("gated") and "gated" in msg.lower():
                warnings.append(f"{m['name']}: {msg}")
            else:
                all_ok = False

    # ONNX
    onnx_backends = [b for b in cfg["backends"] if "onnx" in b]
    if onnx_backends:
        print()
        ok, msg = _check_onnx()
        status = "PASS" if ok else "WARN"
        print(f"  [{status}] ONNX Runtime: {msg}")
        if not ok:
            print("         ONNX backends will be skipped")

    # Disk
    print()
    repo_root = config_path.parent.parent.parent
    results_dir = repo_root / cfg.get("output", {}).get(
        "results_dir", "research/tr123/results"
    )
    ok, msg = _check_disk(results_dir)
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] Disk: {msg}")
    if not ok:
        all_ok = False

    # Run estimate
    print()
    n_models = len(cfg["models"])
    n_scenarios = len(cfg["scenarios"])
    reps = cfg.get("repetitions", 7)
    warmup = cfg.get("warmup_runs", 2)

    total_cells = 0
    for m in cfg["models"]:
        model_skips = backend_skip.get(m["name"], [])
        active = [b for b in cfg["backends"] if b not in model_skips]
        total_cells += len(active) * n_scenarios * reps

    total_warmup = 0
    for m in cfg["models"]:
        model_skips = backend_skip.get(m["name"], [])
        active = [b for b in cfg["backends"] if b not in model_skips]
        for b in active:
            w = 5 if b == "transformers-gpu-compile" else warmup
            total_warmup += n_scenarios * w

    print(f"  Measurement cells: {total_cells}")
    print(f"  Warmup runs: {total_warmup}")
    print(f"  Total forward passes: {total_cells + total_warmup}")
    print(f"  Models: {n_models} ({', '.join(m['name'] for m in cfg['models'])})")

    # KV memory sweep
    kv_cfg = cfg.get("kv_cache", {})
    if kv_cfg.get("measure_memory_overhead"):
        ctx_lens = kv_cfg.get("context_lengths", [])
        n_sweep = n_models * len(ctx_lens)
        print(f"  KV memory sweep: {n_sweep} measurements")

    # Warnings
    if warnings:
        print()
        print("  Warnings:")
        for w in warnings:
            print(f"    ! {w}")

    print()
    print("=" * 60)
    verdict = "GO" if all_ok else "NO-GO"
    print(f"  Verdict: {verdict}")
    print("=" * 60)
    return all_ok


if __name__ == "__main__":
    cfg_path = Path(__file__).parent / "configs" / "matrix.yaml"
    if len(sys.argv) > 1:
        cfg_path = Path(sys.argv[1])
    ok = run_smoke_test(cfg_path)
    sys.exit(0 if ok else 1)
