"""
TR117 Phase 2: Tokenizer Micro-Benchmark

Benchmarks tokenizer throughput (tokens/sec) and latency for Qwen, Gemma, and Llama.
Uses `transformers` or `tokenizers` library.
"""

import time
import argparse
import sys
from pathlib import Path
import json

try:
    from transformers import AutoTokenizer
except ImportError:
    print("Transformers library not found. Please install it: pip install transformers")
    sys.exit(1)

MODELS = {
    "gemma3": "google/gemma-2-9b", # Proxy for Gemma 3 if not available, or use gemma-2
    "qwen2.5": "Qwen/Qwen2.5-7B-Instruct",
    "llama3.1": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}

# Use local paths if available, otherwise download (might be slow/large)
# For this benchmark, we assume the user has these models or we can use the fast tokenizer
# from huggingface hub.

def bench_model(model_name: str, hf_repo: str, text: str, iterations: int = 10):
    print(f"Loading tokenizer for {model_name} ({hf_repo})...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(hf_repo, use_fast=True)
    except Exception as e:
        print(f"Failed to load {model_name}: {e}")
        return None

    # Warmup
    tokenizer.encode("Hello world")
    
    start_time = time.perf_counter()
    total_tokens = 0
    
    for _ in range(iterations):
        tokens = tokenizer.encode(text)
        total_tokens += len(tokens)
        
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    tps = total_tokens / duration
    latency_ms = (duration / iterations) * 1000
    
    return {
        "model": model_name,
        "tps": tps,
        "latency_ms": latency_ms,
        "total_tokens": total_tokens
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="experiments/TR117/results/phase2")
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate 10MB of text
    print("Generating 10MB of synthetic text...")
    # Use a repetitive pattern to avoid compression but keep it simple
    # "The quick brown fox jumps over the lazy dog. " * N
    base = "The quick brown fox jumps over the lazy dog. "
    target_size = 10 * 1024 * 1024 # 10MB
    text = base * (target_size // len(base))
    
    results = []
    
    for model, repo in MODELS.items():
        res = bench_model(model, repo, text, args.iterations)
        if res:
            results.append(res)
            print(f"{model}: {res['tps']:.2f} tok/s, {res['latency_ms']:.2f} ms/iter")
            
    # Save results
    with open(output_dir / "tokenizer_bench.txt", "w") as f:
        f.write(f"{'Model':<15} | {'Tokens/Sec':<15} | {'Latency (ms)':<15}\n")
        f.write("-" * 50 + "\n")
        for r in results:
            f.write(f"{r['model']:<15} | {r['tps']:<15.2f} | {r['latency_ms']:<15.2f}\n")
            
    print(f"Results saved to {output_dir / 'tokenizer_bench.txt'}")

if __name__ == "__main__":
    main()
