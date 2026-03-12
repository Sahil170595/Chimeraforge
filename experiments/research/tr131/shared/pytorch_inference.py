"""Direct PyTorch/HuggingFace inference — bypasses all serving stacks.

Loads a model via transformers, calls model.generate() directly.
Supports single-threaded and concurrent (N threads via ThreadPoolExecutor).
GPU operations release the GIL so threads achieve real concurrency.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

log = logging.getLogger("tr131.pytorch_inference")


@dataclass
class InferenceResult:
    """Single inference result."""

    thread_id: int
    request_seq: int
    wall_ms: float
    prompt_tokens: int
    completion_tokens: int
    effective_tps: float
    status: str = "ok"


class PyTorchInferenceEngine:
    """Direct HuggingFace model loader and inference engine."""

    def __init__(self, hf_id: str, max_new_tokens: int = 128):
        self.hf_id = hf_id
        self.max_new_tokens = max_new_tokens
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def load(self) -> None:
        """Load model and tokenizer to GPU."""
        log.info("Loading %s to %s...", self.hf_id, self.device)
        t0 = time.perf_counter()

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.hf_id,
            trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            self.hf_id,
            torch_dtype=dtype,
            device_map=self.device,
            trust_remote_code=True,
        )
        self.model.eval()

        load_s = time.perf_counter() - t0
        params_m = sum(p.numel() for p in self.model.parameters()) / 1e6
        log.info("Loaded %s (%.0fM params) in %.1fs", self.hf_id, params_m, load_s)

    def generate_one(self, prompt: str) -> dict:
        """Single synchronous generation. Returns token counts and timing."""
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self.device)

        prompt_tokens = inputs["input_ids"].shape[1]

        t0 = time.perf_counter()
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
            )
        wall_ms = (time.perf_counter() - t0) * 1000

        # Count only new tokens (exclude prompt)
        new_tokens = outputs.shape[1] - prompt_tokens

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": new_tokens,
            "wall_ms": wall_ms,
            "effective_tps": new_tokens / wall_ms * 1000 if wall_ms > 0 else 0,
        }

    def unload(self) -> None:
        """Free GPU memory."""
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        log.info("Model unloaded, GPU memory freed")


def run_single_thread(
    engine: PyTorchInferenceEngine,
    prompts: list[str],
) -> list[InferenceResult]:
    """Run inference requests sequentially on a single thread."""
    results = []
    for seq, prompt in enumerate(prompts):
        try:
            out = engine.generate_one(prompt)
            results.append(
                InferenceResult(
                    thread_id=0,
                    request_seq=seq,
                    wall_ms=out["wall_ms"],
                    prompt_tokens=out["prompt_tokens"],
                    completion_tokens=out["completion_tokens"],
                    effective_tps=out["effective_tps"],
                )
            )
        except Exception as e:
            log.warning("Request %d failed: %s", seq, e)
            results.append(
                InferenceResult(
                    thread_id=0,
                    request_seq=seq,
                    wall_ms=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    effective_tps=0,
                    status=f"error: {e}",
                )
            )
    return results


def run_concurrent(
    engine: PyTorchInferenceEngine,
    n_threads: int,
    prompts_per_thread: list[list[str]],
) -> list[InferenceResult]:
    """Run inference with N concurrent threads.

    GPU ops (CUDA kernels) release the GIL, so threads achieve
    real GPU concurrency. This is the key comparison with Ollama N=8.
    """
    results: list[InferenceResult] = []

    def _worker(thread_id: int, prompts: list[str]) -> list[InferenceResult]:
        thread_results = []
        for seq, prompt in enumerate(prompts):
            try:
                out = engine.generate_one(prompt)
                thread_results.append(
                    InferenceResult(
                        thread_id=thread_id,
                        request_seq=seq,
                        wall_ms=out["wall_ms"],
                        prompt_tokens=out["prompt_tokens"],
                        completion_tokens=out["completion_tokens"],
                        effective_tps=out["effective_tps"],
                    )
                )
            except Exception as e:
                log.warning("Thread %d req %d failed: %s", thread_id, seq, e)
                thread_results.append(
                    InferenceResult(
                        thread_id=thread_id,
                        request_seq=seq,
                        wall_ms=0,
                        prompt_tokens=0,
                        completion_tokens=0,
                        effective_tps=0,
                        status=f"error: {e}",
                    )
                )
        return thread_results

    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        futures = {
            pool.submit(_worker, i, prompts_per_thread[i]): i for i in range(n_threads)
        }
        for future in as_completed(futures):
            tid = futures[future]
            try:
                thread_results = future.result()
                results.extend(thread_results)
            except Exception as e:
                log.error("Thread %d crashed: %s", tid, e)

    return results
