# Repository Structure & Data Governance

Chimeraforge is meant to look and feel like an internal frontier lab repo.
This guide captures the structure and conventions that keep the code, data,
and published artifacts organized.

## Principles
- **Separation of concerns** – source lives under `src/`, generated data under
  `benchmarks/` or `outputs/`, and narrative assets under `docs/` or
  `resources/`.
- **Reproducibility first** – any artifact in `benchmarks/`, `data/`, or
  `outputs/` must be traceable to a script/config checked into `src/` or
  `scripts/`.
- **Clean root** – top-level files should stay limited to project metadata
  (README, licenses, requirements). Everything else belongs in one of the
  directories listed below.

## Top-Level Map
| Path | Contains |
| --- | --- |
| `benchmarks/` | Replayable sweep outputs (Python & Rust) referenced by the TRs. |
| `data/` | Baseline JSON/TXT snapshots (`baselines/`), normalized CSV exports (`csv/`), and research datasets (`research/`). |
| `docs/` | All human-facing documentation plus this structure guide. |
| `experiments/` | Scratchpads, notebooks, and proto-studies that have not graduated into formal reports. |
| `logs/` | Persistent log streams; `logs/benchmarks/` mirrors the old root-level log files. |
| `outputs/` | Publish-ready reports, finalized artifacts, and long-running run directories. |
| `resources/` | Supporting assets such as prompts and historical patch notes. |
| `scripts/` | Python helpers plus platform-specific wrappers in `scripts/windows/`. |
| `src/` | Production-ready source for the Python and Rust agents. |

## Generated Artifacts
- **Benchmark drops** – store whole sweeps in `benchmarks/python/` or
  `benchmarks/rust/` (each folder carries its own README and mirrors the report
  structure). PowerShell helpers (e.g., `run_quick_rust_test.ps1`) are wired to
  these directories.
- **Canonical baselines** – keep JSON/TXT exports in `data/baselines/` only.
  Treat the folder as read-mostly so downstream analyses always point to a
  single location.
- **Logs** – move any root-level `.log` output to `logs/benchmarks/` with the
  same filename. New jobs should log to a scenario-specific subfolder under
  `logs/`.
- **Reports** – in-progress results go to `outputs/reports/`; anything final
  enough for stakeholders moves to `outputs/publish_ready/`.

## Contribution Checklist
1. **Pick the right bucket** – if a change introduces new data, ask “is this
   code (`src/`), tooling (`scripts/`), documentation (`docs/`/`resources/`), or
   an artifact (`benchmarks/`, `data/`, `outputs/`)?”. Avoid dropping files at
   the repo root.
2. **Document locally** – every non-trivial directory should own a short
   `README.md` describing the contents and pointing at the script(s) that
   generated them.
3. **Keep generated files reproducible** – if a CSV or report lands in
   `benchmarks/` or `outputs/`, capture the exact command and configuration in
   the accompanying README or metadata file.
4. **Respect platform split** – cross-platform helpers belong in `scripts/`,
   Windows-only wrappers in `scripts/windows/`, and production agent logic in
   `src/python` or `src/rust`.
5. **Update references** – whenever directories move, fix the relevant links in
   `README.md`, `docs/technical_reports.md`, and any TR-specific notebooks.

Following this layout keeps the repository predictable, auditable, and ready for
the next TR without a round of archaeology.
