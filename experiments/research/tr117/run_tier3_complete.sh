#!/bin/bash
# TR117 Tier 3 Complete Benchmark Suite
# Executes full frontier-lab quality benchmark

set -e

echo "========================================="
echo "TR117 Tier 3 Frontier Lab Benchmark"
echo "========================================="
echo ""

# Configuration
export PYTHONPATH="."
export HF_HUB_OFFLINE="1"
export BANTER_TRANSFORMER_MODEL="models/tiny-gpt2"
export BANTER_OLLAMA_MODEL="gemma3:latest"

RESULTS_DIR="results/tr117_tier3"
CONFIG="scripts/tr117/configs/matrix_tier3.yaml"

echo "Step 1: Building TensorRT engines..."
python scripts/tr117/build_tensorrt_engines.py \
    --models-dir models \
    --output-dir artifacts/tensorrt_engines \
    --precision fp32 fp16

echo ""
echo "Step 2: Running benchmark matrix (this will take several hours)..."
python scripts/tr117/run_matrix.py \
    --config ${CONFIG} \
    --output-root ${RESULTS_DIR}/runs \
    --prepare-quant

echo ""
echo "Step 3: Aggregating results..."
python scripts/tr117/analyze_tr117.py \
    --runs-root ${RESULTS_DIR}/runs \
    --output ${RESULTS_DIR}/metrics.csv

echo ""
echo "Step 4: Statistical analysis..."
python scripts/tr117/statistical_analysis.py

echo ""
echo "Step 5: Cost analysis..."
python scripts/tr117/cost_analysis.py \
    --metrics ${RESULTS_DIR}/metrics.csv \
    --output ${RESULTS_DIR}/cost_analysis.json

echo ""
echo "Step 6: Capturing environment..."
python scripts/tr117/env_capture.py

echo ""
echo "========================================="
echo "✓ TR117 Tier 3 Benchmark Complete!"
echo "========================================="
echo ""
echo "Results location: ${RESULTS_DIR}/"
echo ""
echo "Key outputs:"
echo "  - ${RESULTS_DIR}/metrics.csv"
echo "  - ${RESULTS_DIR}/statistical_analysis.json"
echo "  - ${RESULTS_DIR}/cost_analysis.json"
echo "  - ${RESULTS_DIR}/latency_by_backend.png"
echo "  - results/tr117/env.json"
echo ""
echo "Next steps:"
echo "  1. Review statistical significance in statistical_analysis.json"
echo "  2. Check cost-performance tradeoffs in cost_analysis.json"
echo "  3. Generate technical report from analysis/"
echo ""

