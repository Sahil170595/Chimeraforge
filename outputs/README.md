# Outputs Directory

This directory stores generated artifacts, report outputs, and raw run material.

## Canonical Paths

- `publish_ready/reports/`
  Publication-ready technical reports, conclusive syntheses, and whitepapers.
- `publish_ready/docs/`
  Curated benchmark writeups and long-form supporting documentation.
- `publish_ready/notebooks/`
  Notebook exports and supporting analysis notebooks.

## Working Paths

- `reports/`
  Exploratory notes, scratch summaries, integration digests, legacy mirrors, and
  profiling outputs that are useful during active investigation but are not the
  canonical TR archive.
- `artifacts/`
  Charts, profiler exports, images, and auxiliary report assets.
- `runs/`
  Raw run outputs and profiler sessions.

## Usage Rules

- If a report is something you would link in docs, cite in an issue, or treat as
  stable, it belongs in `publish_ready/reports/`.
- If a file is exploratory, transitional, or legacy, keep it in `reports/` under
  a descriptive subdirectory.
- If a file is primarily an asset rather than a narrative document, keep it in
  `artifacts/`.
