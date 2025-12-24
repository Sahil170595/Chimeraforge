# Research Workspace

This directory contains all research experiments and technical report implementations.

## Structure

- **TR108-TR116**: Early multi-agent and cross-language performance studies
- **TR117**: Cross-backend inference benchmark (inference track) + Multi-agent root cause analysis
- **TR117_multiagent**: Multi-agent root cause analysis experiments
- **TR118**: ONNX Runtime + TensorRT deep dive experiments
- **TR119**: Cost & energy analysis experiments
- **TR120**: "Compile Paradox" root-cause audit experiments
- **TR121**: Model scaling study (5M to 20B parameters)
- **TR122**: Resource profiling deep dive (planned)
- **TR123**: Multi-hardware generalization (planned)
- **tr117**: TR117 tier-3 infrastructure and scripts
- **compilation**: Compilation benchmark experiments
- **ollama**: Ollama-specific benchmark experiments
- **quantization**: Quantization experiments

## Artifacts

Shared raw data lives in `data/` and is consumed by per-report directories. Each TR folder holds its own scripts, results, and artifacts. Final publish-ready reports are in `outputs/publish_ready/reports/`.

## Quick Reference

- **TR108-TR115**: Python/Rust agent performance baseline
- **TR116**: Cross-model benchmarks (Qwen, Gemma, Llama)
- **TR117**: Backend inference matrix + Multi-agent root cause
- **TR118**: ONNX/TRT optimization deep dive
- **TR119**: Cost/energy economics analysis
- **TR120**: Compile paradox root cause
- **TR121**: Model scaling pipeline
