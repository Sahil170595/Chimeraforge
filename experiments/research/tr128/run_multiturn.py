"""TR128 Phase 5 — Multi-Turn Conversations.

Measures per-turn latency degradation with context accumulation and
compares full context vs sliding-window strategies.

Cross-validates with TR127 context-length scaling data.
3 models x 2 turn_counts x 2 strategies x 8 convos = ~720 turn-level rows.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

from research.tr128.shared.load_generator import run_multiturn_conversation

log = logging.getLogger("tr128.phase5")

# Diverse multi-turn prompts — each conversation uses a different topic
CONVERSATION_TOPICS = [
    [
        "Explain how transformers work in machine learning.",
        "How does self-attention differ from cross-attention?",
        "What is the role of the key-value cache in autoregressive generation?",
        "How does the KV cache size scale with sequence length?",
        "What optimizations exist to reduce KV cache memory usage?",
        "Explain grouped-query attention and its benefits.",
        "How does sliding window attention work in Mistral?",
        "Compare multi-head attention with grouped-query attention.",
        "What are the trade-offs between model quality and inference speed?",
        "Summarize the key points from our entire conversation.",
    ],
    [
        "What is the difference between CPU and GPU computation?",
        "How does GPU memory bandwidth affect LLM inference?",
        "What is the roofline model for performance analysis?",
        "Explain the difference between compute-bound and memory-bound operations.",
        "How does batch size affect GPU utilization?",
        "What is tensor parallelism in distributed inference?",
        "How does pipeline parallelism differ from tensor parallelism?",
        "What are the main bottlenecks in serving LLMs at scale?",
        "How do quantization methods reduce inference cost?",
        "Summarize the key performance concepts we discussed.",
    ],
    [
        "Describe the Python asyncio event loop.",
        "How does async/await differ from threading?",
        "What are the main use cases for asyncio in web servers?",
        "Explain how connection pooling works with async HTTP clients.",
        "What is backpressure in async systems?",
        "How do you handle timeouts in asyncio?",
        "What are the common pitfalls of async programming?",
        "How does asyncio compare to Go goroutines?",
        "What profiling tools exist for async Python code?",
        "Summarize the async programming patterns we covered.",
    ],
    [
        "What is the CAP theorem in distributed systems?",
        "How does eventual consistency work in practice?",
        "Explain the Raft consensus algorithm.",
        "What are the trade-offs between strong and eventual consistency?",
        "How do distributed databases handle partitions?",
        "What is the role of a write-ahead log?",
        "How does sharding differ from replication?",
        "What are vector clocks used for?",
        "How do CRDTs enable conflict-free replication?",
        "Summarize the distributed systems concepts we discussed.",
    ],
    [
        "Explain how HTTP/2 differs from HTTP/1.1.",
        "What is server-sent events and how does it compare to WebSockets?",
        "How does gRPC use HTTP/2 features?",
        "What are the benefits of protocol buffers over JSON?",
        "How does connection multiplexing work in HTTP/2?",
        "What is head-of-line blocking?",
        "How does HTTP/3 with QUIC address HOL blocking?",
        "What are the trade-offs between REST and gRPC?",
        "How do load balancers handle HTTP/2 connections?",
        "Summarize the network protocol concepts we covered.",
    ],
    [
        "Explain the basics of operating system memory management.",
        "What is virtual memory and how does it work?",
        "How do page tables map virtual to physical addresses?",
        "What is a TLB and why is it important for performance?",
        "How does memory-mapped I/O work?",
        "What are the trade-offs of different page sizes?",
        "How does NUMA architecture affect application performance?",
        "What is memory fragmentation and how is it managed?",
        "How do modern CPUs implement memory prefetching?",
        "Summarize the memory management concepts we covered.",
    ],
    [
        "What are the fundamental data structures used in databases?",
        "How does a B-tree differ from a hash index?",
        "What is an LSM tree and when is it preferred?",
        "Explain write-ahead logging in database systems.",
        "How do databases implement MVCC?",
        "What are the isolation levels in SQL databases?",
        "How does a query optimizer work?",
        "What is the difference between row and column storage?",
        "How do bloom filters improve database performance?",
        "Summarize the database internals we discussed.",
    ],
    [
        "Describe how a compiler processes source code.",
        "What are the stages of compilation?",
        "How does lexical analysis work?",
        "What is an abstract syntax tree?",
        "How do compilers optimize intermediate representation?",
        "What is register allocation and why is it important?",
        "How does JIT compilation differ from AOT compilation?",
        "What are the trade-offs of garbage collection strategies?",
        "How do modern CPUs execute instructions out of order?",
        "Summarize the compilation and execution concepts we covered.",
    ],
]


def run_phase5(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> int:
    """Execute Phase 5: multi-turn conversation experiments.

    Returns number of rows written.
    """
    p5 = cfg["phase5"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    sliding_window = p5["sliding_window_turns"]
    n_convos = p5["conversations_per_combo"]
    rows_written = 0

    for model_cfg in models:
        tag = model_cfg["ollama_tag"]
        model_name = model_cfg["name"]

        for turn_count in p5["turn_counts"]:
            for strategy in p5["context_strategies"]:
                for conv_idx in range(n_convos):
                    conv_id = f"{model_name}_{strategy}_t{turn_count}_c{conv_idx}"
                    log.info(
                        "  P5: %s / %d turns / %s / conv %d",
                        model_name,
                        turn_count,
                        strategy,
                        conv_idx,
                    )

                    # Select prompts — cycle through topics
                    topic = CONVERSATION_TOPICS[conv_idx % len(CONVERSATION_TOPICS)]
                    prompts = topic[:turn_count]

                    results = asyncio.run(
                        run_multiturn_conversation(
                            url,
                            tag,
                            prompts,
                            context_strategy=strategy,
                            sliding_window=sliding_window,
                            max_tokens=max_tokens,
                            timeout=timeout,
                        )
                    )

                    for r in results:
                        row = {
                            "phase": "p5_multiturn",
                            "model": model_name,
                            "num_parallel": 1,
                            "arrival_pattern": "",
                            "arrival_rate_rps": "",
                            "prompt_distribution": "",
                            "response_mode": "chat",
                            "request_id": r.request_id,
                            "queue_depth_at_submit": 0,
                            "wall_ms": round(r.wall_ms, 2),
                            "ttft_ms": "",
                            "ichunk_mean_ms": "",
                            "ichunk_p95_ms": "",
                            "ichunk_jitter_cv": "",
                            "prompt_tokens": r.prompt_tokens,
                            "completion_tokens": r.completion_tokens,
                            "prompt_eval_ms": round(r.prompt_eval_ms, 2),
                            "eval_ms": round(r.eval_ms, 2),
                            "total_duration_ms": round(r.total_duration_ms, 2),
                            "load_duration_ms": round(r.load_duration_ms, 2),
                            "tokens_per_s": round(r.tokens_per_s, 2),
                            "turn_number": r.request_id,
                            "conversation_id": conv_id,
                            "context_strategy": strategy,
                            "status": r.status,
                        }
                        writer.writerow(row)
                        rows_written += 1

    log.info("  Phase 5 complete: %d rows", rows_written)
    return rows_written
