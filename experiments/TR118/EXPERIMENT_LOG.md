# TR118 Experiment Log

## 2025-12-12

- Run-level benchmark pipeline implemented (TR115_v2-style sampling).
- ONNX export fixed via wrapper (keyword args) + TRT-friendly int32 inputs option.
- TRT engine builder supports dynamic profiles + INT8 calibration batches/cache (optional deps).
- Perplexity validator supports PyTorch + ORT + TensorRT (when available).
- Publish-ready report generator added (writes `reports/generated/Technical_Report_118.md`).
