# CLI README qualification — 2026-10-09

The source code is the reviewed contribution-replay stack at
`97595a4b53d2439c4af25655362b017455a824ab`; this change updates its README and the
linked deployment example. No generation, planner or transport implementation
changed. `local-receipt.json` binds the exact outputs and independently counts
the JUnit XML; working document hashes and canonical LF hashes are explicit.

- `python -m pytest --junitxml=unit.xml`: 3,438 passed, two skipped, 14 warnings.
- `parser.json`: all 66 Bash CLI examples in the README/deployment guide parse
  through the real Typer/Click hierarchy without executing their callbacks.
- `functional.json`: actual metadata-only HF plan with saved latency targets,
  offline registry plan, saved-plan check and Compose export all exited zero.
  Candidate index 15 was selected from this actual artifact by backend,
  precision, replica count and offload; it is not a fixed index in the examples.
- `scripts/corpus_shape.py --check` passed. The generated corpus summary is
  unchanged; its canonical hash is in `parser.json`.

The Windows run reused the existing Python 3.12 environment. No model weights,
new dependencies, GPU runtime or container were installed. The named RTX 4090
is a planning input, not an observed local execution device. Live benchmark,
monitor and MCP clients were not executed here; their flags were parsed and
their prerequisites are documented. The image tag was accepted as a template
input and was not fetched or launched. Export acceptance does not qualify an
engine image or establish GPU prediction accuracy.

The README distinguishes published 0.51.0 from the open reviewed features.
The stdout/stderr, saved plans, Compose file and test outputs retain their exact
bytes under the scoped `.gitattributes` rule. Earlier exploratory examples are
retained externally under `C:\tmp\cf-readme-examples-20261009`, including the
invalid guessed `plan --backend` attempt; that flag is not documented.
