"""
TR117 Phase 2: Tokenizer Micro-Benchmark

Benchmarks tokenizer throughput (tokens/sec) and latency for Qwen, Gemma, and Llama.
Uses Hugging Face fast tokenizers if available; avoids downloads unless --allow-download is set.
"""

import time
import argparse
import sys
from pathlib import Path

try:
    from transformers import AutoTokenizer
except ImportError:
    print("Transformers library not found. Please install it: pip install transformers")
    sys.exit(1)

MODELS = {
    # Use closest available tokenizers; allow override via CLI if needed
    "gemma3": "google/gemma-2-9b",
    "qwen2.5": "Qwen/Qwen2.5-7B-Instruct",
    "llama3.1": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}


def bench_model(model_name: str, hf_repo: str, text: str, iterations: int, allow_download: bool):
    print(f"Loading tokenizer for {model_name} ({hf_repo})...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            hf_repo,
            use_fast=True,
            local_files_only=not allow_download,
        )
    except Exception as e:
        print(f"Skipped {model_name}: {e}")
        return None

    # Warmup
    tokenizer.encode("Hello world")

    start_time = time.perf_counter()
    total_tokens = 0

    for _ in range(iterations):
        tokens = tokenizer.encode(text)
        total_tokens += len(tokens)

    duration = time.perf_counter() - start_time
    tps = total_tokens / duration if duration > 0 else 0
    latency_ms = (duration / iterations) * 1000 if iterations else 0

    return {
        "model": model_name,
        "tps": tps,
        "latency_ms": latency_ms,
        "total_tokens": total_tokens,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="experiments/TR117/results/phase2")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--bytes", type=int, default=10 * 1024 * 1024, help="Corpus size in bytes (default 10MB)")
    parser.add_argument("--allow-download", action="store_true", help="Allow HF to download tokenizers if not cached")
    parser.add_argument(
        "--gemma-tokenizer",
        default=MODELS["gemma3"],
        help="HF repo or local path for Gemma tokenizer (comma-separated fallbacks allowed)",
    )
    parser.add_argument(
        "--qwen-tokenizer",
        default=MODELS["qwen2.5"],
        help="HF repo or local path for Qwen tokenizer (comma-separated fallbacks allowed)",
    )
    parser.add_argument(
        "--llama-tokenizer",
        default=MODELS["llama3.1"],
        help="HF repo or local path for Llama tokenizer (comma-separated fallbacks allowed)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build corpus
    base = "The quick brown fox jumps over the lazy dog. "
    text = base * max(1, args.bytes // len(base))
    print(f"Generated corpus of ~{len(text.encode('utf-8')) / (1024*1024):.2f} MB")

    def expand(candidates: str):
        return [c.strip() for c in candidates.split(",") if c.strip()]

    model_map = {
        "gemma3": expand(args.gemma_tokenizer),
        "qwen2.5": expand(args.qwen_tokenizer),
        "llama3.1": expand(args.llama_tokenizer),
    }

    results = []
    for model, repos in model_map.items():
        success = False
        for repo in repos:
            res = bench_model(model, repo, text, args.iterations, args.allow_download)
            if res:
                results.append(res)
                print(f"{model} [{repo}]: {res['tps']:.2f} tok/s, {res['latency_ms']:.2f} ms/iter")
                success = True
                break
        if not success:
            print(f"{model}: no tokenizer available (checked: {', '.join(repos)})")

    if not results:
        print("No tokenizer results recorded; ensure tokenizers are available locally or pass --allow-download.")
        return

    # Save results
    out_file = output_dir / "tokenizer_bench.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"{'Model':<15} | {'Tokens/Sec':<15} | {'Latency (ms)':<15}\n")
        f.write("-" * 50 + "\n")
        for r in results:
            f.write(f"{r['model']:<15} | {r['tps']:<15.2f} | {r['latency_ms']:<15.2f}\n")

    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    main()
