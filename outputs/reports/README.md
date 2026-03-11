# Outputs Reports

This directory contains exploratory and legacy report material.

It is not the canonical home for the numbered technical report series.

## Canonical Report Location

Use `../publish_ready/reports/` for:

- publication-ready technical reports
- conclusive syntheses
- executive whitepapers
- stable report links from docs, issues, or PRs

## Current Layout

- `legacy_tr_mirrors/`
  Historical copies of early TR files that now live canonically under
  `../publish_ready/reports/`.
- `integration/`
  Integration notes, digests, and one-off validation summaries.
- `diagnostics/`
  Diagnostic JSON outputs and self-healing / demo traces.
- `profiling/`
  Profiling exports and supporting CSV summaries.
- `compilation/`
  Historical compilation benchmark notes and figures.
- `gemma3/`
  Legacy Gemma 3 benchmark outputs and summaries.
- `kernel_optimization/`
  Low-level kernel benchmark summaries.
- `llama3/`
  Historical Llama / Ollama benchmark artifacts.
- `notebook_validations/`
  Notebook validation exports.
- `ollama/`
  Timestamped Ollama benchmark runs and related notes.
- `quantization/`
  Quantization report drafts and supporting outputs.

## Hygiene Rules

- Keep the top level of `outputs/reports/` as clean as possible.
- Put new files in a named subdirectory that explains their role.
- Promote anything stakeholder-facing to `../publish_ready/reports/`.

## Related Paths

- `../README.md`
  Map of the full `outputs/` tree.
- `../publish_ready/reports/README.md`
  Canonical technical report index.
