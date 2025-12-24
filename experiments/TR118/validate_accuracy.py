#!/usr/bin/env python3
"""
TR118: Accuracy validation (perplexity) for ONNXRuntime/TensorRT vs PyTorch baseline.

Goal: publishable, statistically meaningful accuracy gates:
- FP32: <0.1% perplexity increase
- FP16: <0.5% perplexity increase
- INT8: <2.0% perplexity increase (with real calibrator)

Outputs:
- `scripts/tr118/results/processed/perplexity_results.csv`
- `scripts/tr118/results/processed/perplexity_results.json`
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import logging
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import resolve_repo_path

logger = logging.getLogger("tr118_accuracy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass(frozen=True)
class PerplexityStats:
    perplexity: float
    nll_sum: float
    token_count: int
    mean_nll: float


def _load_cfg(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_wikitext_texts(dataset_config: str, split: str, limit: int) -> list[str]:
    try:
        from datasets import load_dataset  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("datasets package required for perplexity evaluation") from exc

    ds = load_dataset("wikitext", dataset_config, split=split)
    texts: list[str] = []
    for row in ds:
        txt = str(row.get("text", "")).strip()
        if not txt:
            continue
        texts.append(txt)
        if len(texts) >= limit:
            break
    return texts


def _tokenize_batch(tokenizer, texts: list[str], max_length: int):
    enc = tokenizer(
        texts,
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )
    return enc["input_ids"], enc["attention_mask"]


def _nll_from_logits(logits, input_ids, attention_mask) -> tuple[float, int]:
    import torch.nn.functional as F  # type: ignore

    # Shift for causal LM
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = input_ids[:, 1:].contiguous()
    shift_mask = attention_mask[:, 1:].contiguous()

    vocab = shift_logits.size(-1)
    loss = F.cross_entropy(
        shift_logits.view(-1, vocab),
        shift_labels.view(-1),
        reduction="none",
    )
    mask = shift_mask.view(-1).float()
    nll = float((loss * mask).sum().item())
    tokens = int(mask.sum().item())
    return nll, tokens


def _perplexity_pytorch(
    model,
    tokenizer,
    texts: list[str],
    batch_size: int,
    max_length: int,
    device: str,
) -> PerplexityStats:
    import torch  # type: ignore

    total_nll = 0.0
    total_tokens = 0

    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            input_ids, attention_mask = _tokenize_batch(tokenizer, batch, max_length=max_length)
            input_ids = input_ids.to(device)
            attention_mask = attention_mask.to(device)
            out = model(input_ids=input_ids, attention_mask=attention_mask, use_cache=False)
            logits = out.logits
            nll, tokens = _nll_from_logits(logits, input_ids, attention_mask)
            total_nll += nll
            total_tokens += tokens

    denom = max(1, total_tokens)
    mean_nll = float(total_nll / denom)
    ppl = float(math.exp(mean_nll))
    return PerplexityStats(perplexity=ppl, nll_sum=float(total_nll), token_count=int(total_tokens), mean_nll=mean_nll)

def _perplexity_ort_session(
    session,
    input_type: str,
    tokenizer,
    texts: list[str],
    batch_size: int,
    max_length: int,
) -> PerplexityStats:
    import numpy as np  # type: ignore
    import torch  # type: ignore
    dtype = np.int32 if "int32" in input_type else np.int64

    total_nll = 0.0
    total_tokens = 0
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(
            batch,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="np",
        )
        input_ids = enc["input_ids"].astype(dtype)
        attention_mask = enc["attention_mask"].astype(dtype)
        outputs = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
        logits = torch.from_numpy(outputs[0])
        ids_t = torch.from_numpy(input_ids).long()
        mask_t = torch.from_numpy(attention_mask).long()
        nll, tokens = _nll_from_logits(logits, ids_t, mask_t)
        total_nll += nll
        total_tokens += tokens
    denom = max(1, total_tokens)
    mean_nll = float(total_nll / denom)
    ppl = float(math.exp(mean_nll))
    return PerplexityStats(perplexity=ppl, nll_sum=float(total_nll), token_count=int(total_tokens), mean_nll=mean_nll)


def _perplexity_trt(
    engine_path: Path,
    tokenizer,
    texts: list[str],
    batch_size: int,
    max_length: int,
) -> PerplexityStats:
    import numpy as np  # type: ignore
    import torch  # type: ignore

    from scripts.tr118.trt_inference import TensorRTInferenceEngine

    runner = TensorRTInferenceEngine(engine_path)
    vocab_size = int(getattr(tokenizer, "vocab_size", 50257) or 50257)
    prepared = runner.prepare(batch=batch_size, seq=max_length, vocab_size=vocab_size)

    total_nll = 0.0
    total_tokens = 0
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(
            batch,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="np",
        )
        input_ids = enc["input_ids"].astype(np.int32)
        attention_mask = enc["attention_mask"].astype(np.int32)
        if input_ids.shape[0] < batch_size:
            pad_rows = batch_size - input_ids.shape[0]
            input_ids = np.concatenate([input_ids, np.zeros((pad_rows, max_length), dtype=np.int32)], axis=0)
            attention_mask = np.concatenate([attention_mask, np.zeros((pad_rows, max_length), dtype=np.int32)], axis=0)
        _ms, logits = runner.infer(prepared, input_ids, attention_mask)
        logits_t = torch.from_numpy(np.asarray(logits)).float()
        ids_t = torch.from_numpy(input_ids).long()
        mask_t = torch.from_numpy(attention_mask).long()
        nll, tokens = _nll_from_logits(logits_t, ids_t, mask_t)
        total_nll += nll
        total_tokens += tokens
    denom = max(1, total_tokens)
    mean_nll = float(total_nll / denom)
    ppl = float(math.exp(mean_nll))
    return PerplexityStats(perplexity=ppl, nll_sum=float(total_nll), token_count=int(total_tokens), mean_nll=mean_nll)


def _load_tokenizer(model_name: str):
    from transformers import AutoTokenizer  # type: ignore

    tok = AutoTokenizer.from_pretrained(model_name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


def _load_pytorch_model(model_name: str, device: str):
    import torch  # type: ignore
    from transformers import AutoModelForCausalLM  # type: ignore

    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)
    model.eval()
    model.to(device)
    return model


def _reference_check_pytorch_loss(model, tokenizer, texts: list[str], max_length: int, device: str) -> dict[str, Any]:
    import torch  # type: ignore

    if not texts:
        return {"ok": False, "error": "no_texts"}

    batch = texts[: min(8, len(texts))]
    input_ids, attention_mask = _tokenize_batch(tokenizer, batch, max_length=max_length)
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)

    labels = input_ids.clone()
    labels[attention_mask == 0] = -100
    with torch.no_grad():
        out = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels, use_cache=False)
        mean_nll = float(out.loss.item())
    token_count = int(attention_mask[:, 1:].sum().item())
    ppl = float(math.exp(mean_nll))
    return {"ok": True, "mean_nll": mean_nll, "token_count": token_count, "perplexity": ppl}


def _logit_diffs_last_token(
    model,
    tokenizer,
    device: str,
    onnx_path: Path,
    trt_dir: Path,
    diag_seq: int,
) -> dict[str, Any]:
    """
    Lightweight INT8 proof: compute mean/max abs diff of last-token logits vs PyTorch FP32.
    Uses a single (batch=1, seq=min(32, max_length)) example built from a fixed prompt.
    """
    import numpy as np  # type: ignore
    import torch  # type: ignore

    prompt = "The quick brown fox jumps over the lazy dog."
    diag_seq = int(max(2, diag_seq))
    enc = tokenizer(prompt, truncation=True, padding="max_length", max_length=diag_seq, return_tensors="pt")
    input_ids_t = enc["input_ids"].to(device)
    attention_mask_t = enc["attention_mask"].to(device)

    with torch.no_grad():
        base_logits = model(input_ids=input_ids_t, attention_mask=attention_mask_t, use_cache=False).logits
    base_last = base_logits[0, -1, :].detach().float().cpu()

    diffs: dict[str, Any] = {}

    # ORT
    if onnx_path.exists():
        try:
            import onnxruntime as ort  # type: ignore
        except Exception as exc:
            diffs["onnxruntime_error"] = f"{type(exc).__name__}: {exc}"
            ort = None  # type: ignore

        if ort is not None:
            for name, providers in [
                ("onnxruntime-cpu", ["CPUExecutionProvider"]),
                ("onnxruntime-gpu", ["CUDAExecutionProvider", "CPUExecutionProvider"]),
            ]:
                try:
                    session = ort.InferenceSession(str(onnx_path), providers=providers)
                    used = [str(p) for p in session.get_providers()]
                    input_type = str(session.get_inputs()[0].type)
                    dtype = np.int32 if "int32" in input_type else np.int64
                    enc_np = tokenizer(
                        prompt,
                        truncation=True,
                        padding="max_length",
                        max_length=diag_seq,
                        return_tensors="np",
                    )
                    input_ids = enc_np["input_ids"].astype(dtype)
                    attention_mask = enc_np["attention_mask"].astype(dtype)
                    out = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})[0]
                    cand_last = torch.from_numpy(np.asarray(out)[0, -1, :]).float()
                    diff = (cand_last - base_last).abs()
                    diffs[name] = {
                        "providers_used": used,
                        "mean_abs": float(diff.mean().item()),
                        "max_abs": float(diff.max().item()),
                    }
                except Exception as exc:
                    diffs[name] = {"error": f"{type(exc).__name__}: {exc}"}
    else:
        diffs["onnxruntime_error"] = "missing_onnx"

    # TRT
    try:
        from scripts.tr118.trt_inference import TensorRTInferenceEngine

        vocab_size = int(getattr(tokenizer, "vocab_size", 50257) or 50257)
        enc_np = tokenizer(
            prompt,
            truncation=True,
            padding="max_length",
            max_length=diag_seq,
            return_tensors="np",
        )
        input_ids = enc_np["input_ids"].astype(np.int32)
        attention_mask = enc_np["attention_mask"].astype(np.int32)

        for precision in ["fp32", "fp16", "int8"]:
            name = f"tensorrt-{precision}"
            plan_path = trt_dir / f"{Path(str(onnx_path.stem)).name}_{precision}.plan"
            if not plan_path.exists():
                continue
            try:
                runner = TensorRTInferenceEngine(plan_path)
                prepared = runner.prepare(batch=1, seq=diag_seq, vocab_size=vocab_size)
                _ms, logits = runner.infer(prepared, input_ids, attention_mask)
                cand_last = torch.from_numpy(np.asarray(logits)[0, -1, :]).float()
                diff = (cand_last - base_last).abs()
                diffs[name] = {
                    "mean_abs": float(diff.mean().item()),
                    "max_abs": float(diff.max().item()),
                }
            except Exception as exc:
                diffs[name] = {"error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:
        diffs["tensorrt_error"] = f"{type(exc).__name__}: {exc}"

    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118 perplexity validation")
    parser.add_argument(
        "--config",
        default="scripts/tr118/configs/baseline.yaml",
        help="TR118 config yaml",
    )
    parser.add_argument("--split", default="test", help="Dataset split")
    parser.add_argument("--device", default="cpu", help="PyTorch device (cpu/cuda)")
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_cfg(cfg_path)
    model_name = cfg["model"]["name"]
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"])) / "processed"
    results_dir.mkdir(parents=True, exist_ok=True)

    acc_cfg = cfg.get("accuracy", {}) or {}
    dataset_config = str(acc_cfg.get("perplexity_dataset", "wikitext-2-raw-v1"))
    samples = int(acc_cfg.get("perplexity_samples", 200))
    batch_size = int(acc_cfg.get("perplexity_batch_size", 4))
    max_length = int(acc_cfg.get("perplexity_max_length", 128))

    texts = _load_wikitext_texts(dataset_config, split=args.split, limit=samples)
    logger.info("Loaded %d samples from wikitext:%s", len(texts), dataset_config)

    onnx_path = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["onnx_dir"])) / f"{Path(model_name).name}.onnx"
    trt_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["tensorrt_dir"]))
    baseline_backend = str(cfg.get("baseline", {}).get("backend", "pytorch")).strip() or "pytorch"

    results: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "formula": "Perplexity = exp(NLL_sum / token_count), where NLL is summed cross-entropy on shifted logits/labels and token_count = sum(attention_mask[:,1:]).",
        "dataset": {"name": "wikitext", "config": dataset_config, "split": str(args.split), "samples": len(texts)},
    }

    tokenizer = _load_tokenizer(model_name)
    vocab_size = int(getattr(tokenizer, "vocab_size", 50257) or 50257)
    diagnostics["vocab_size"] = vocab_size
    diagnostics["ln_vocab"] = float(math.log(float(vocab_size)))
    diagnostics["expected_uniform_perplexity"] = float(vocab_size)

    device = str(args.device)
    try:
        model = _load_pytorch_model(model_name, device=device)
    except Exception as exc:
        if device != "cpu":
            logger.warning("Failed to load PyTorch model on %s (%s); falling back to CPU", device, exc)
            device = "cpu"
            model = _load_pytorch_model(model_name, device=device)
        else:
            raise
    diagnostics["pytorch_device"] = device

    # Baseline: PyTorch perplexity
    base = _perplexity_pytorch(
        model=model,
        tokenizer=tokenizer,
        texts=texts,
        batch_size=batch_size,
        max_length=max_length,
        device=device,
    )
    results.append(
        {
            "backend": baseline_backend,
            **asdict(base),
            "delta_frac": 0.0,
            "pass": True,
        }
    )
    diagnostics["baseline"] = asdict(base)
    diagnostics["reference_check_pytorch_loss"] = _reference_check_pytorch_loss(
        model=model,
        tokenizer=tokenizer,
        texts=texts,
        max_length=max_length,
        device=device,
    )
    diagnostics["logit_diffs_last_token"] = _logit_diffs_last_token(
        model=model,
        tokenizer=tokenizer,
        device=device,
        onnx_path=onnx_path,
        trt_dir=trt_dir,
        diag_seq=max_length,
    )

    # ORT CPU
    if onnx_path.exists():
        try:
            import onnxruntime as ort  # type: ignore

            diagnostics["onnx_path"] = str(onnx_path)
        except Exception:
            ort = None  # type: ignore

        for backend, providers in [
            ("onnxruntime-cpu", ["CPUExecutionProvider"]),
            ("onnxruntime-gpu", ["CUDAExecutionProvider", "CPUExecutionProvider"]),
        ]:
            try:
                if ort is None:
                    raise RuntimeError("onnxruntime package required")
                session = ort.InferenceSession(str(onnx_path), providers=providers)
                input_type = str(session.get_inputs()[0].type)
                used = [str(p) for p in session.get_providers()]
                stats = _perplexity_ort_session(
                    session=session,
                    input_type=input_type,
                    tokenizer=tokenizer,
                    texts=texts,
                    batch_size=batch_size,
                    max_length=max_length,
                )
                delta = (stats.perplexity - base.perplexity) / base.perplexity if base.perplexity else 0.0
                results.append(
                    {
                        "backend": backend,
                        **asdict(stats),
                        "delta_frac": delta,
                        "providers_used": used,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "backend": backend,
                        "perplexity": None,
                        "nll_sum": None,
                        "token_count": 0,
                        "mean_nll": None,
                        "delta_frac": None,
                        "error": str(exc),
                    }
                )
    else:
        logger.warning("ONNX file not found at %s; skipping ORT perplexity", onnx_path)

    # TensorRT (optional)
    for precision in ["fp32", "fp16", "int8"]:
        backend = f"tensorrt-{precision}"
        plan_path = trt_dir / f"{Path(model_name).name}_{precision}.plan"
        if not plan_path.exists():
            continue
        try:
            stats = _perplexity_trt(
                engine_path=plan_path,
                tokenizer=tokenizer,
                texts=texts,
                batch_size=batch_size,
                max_length=max_length,
            )
            delta = (stats.perplexity - base.perplexity) / base.perplexity if base.perplexity else 0.0
            results.append(
                {
                    "backend": backend,
                    **asdict(stats),
                    "delta_frac": delta,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "backend": backend,
                    "perplexity": None,
                    "nll_sum": None,
                    "token_count": 0,
                    "mean_nll": None,
                    "delta_frac": None,
                    "error": str(exc),
                }
            )

    # Evaluate pass/fail based on thresholds if provided
    thresholds = acc_cfg.get("perplexity_thresholds", {}) or {}
    for row in results:
        if row.get("backend") == baseline_backend:
            continue
        delta = row.get("delta_frac")
        if delta is None:
            row["pass"] = False
            continue
        # Map backend to threshold bucket
        bucket = "fp32"
        b = str(row["backend"]).lower()
        if "fp16" in b:
            bucket = "fp16"
        if "int8" in b:
            bucket = "int8"
        thresh = float(thresholds.get(bucket, 1.0))
        row["pass"] = delta <= thresh
        row["threshold"] = thresh

    out_csv = results_dir / "perplexity_results.csv"
    out_json = results_dir / "perplexity_results.json"
    pd.DataFrame(results).to_csv(out_csv, index=False)
    out_json.write_text(json.dumps({"results": results, "diagnostics": diagnostics}, indent=2), encoding="utf-8")
    logger.info("Wrote %s and %s", out_csv, out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
