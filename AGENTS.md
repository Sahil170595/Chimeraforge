# AGENTS.md — Chimeraforge

Vendor-neutral contract for AI coding agents working in this repo (Codex, Claude Code,
or anything else). Claude Code additionally reads CLAUDE.md — the navigation map with
architecture, patch history, and full command list; read it if you can.

## Verify gates

Run these before claiming work done; report the real output, fix, re-run:

- `python -m pytest` (CLI + capacity planner tests)

## Engineering Standards (chimera-wide)

> **Canonical source:** `Banterpacks/CLAUDE.md`. This block is propagated verbatim to every
> chimera-ecosystem repo — Banterpacks, Banterhearts, Chimera_Multi_agent (Muse), Chimeraforge,
> Echo, jarvis-console, Banterblogs, Chimeradroid. Edit it in Banterpacks and re-propagate; don't fork it per-repo.

**The bar — all repos, all languages:**

- **Build it right or don't build it.** Tech debt by choice is a discipline failure, not pragmatism. "Fine for now" / "fix later" is rejected.
- **No toy/stub code when production is asked.** Hash-encodings standing in for models, unwired controllers, empty eval gates, placeholder returns — unacceptable. Verify end-to-end with real data, or explicitly flag it as scaffold.
- **Functional, not ceremonial.** Every system must *do* something real. Rubber-stamp consensus, keyword-matching "AI", orphan telemetry = ceremony. Advisory-only enforcement is not enforcement — make the gate real or don't ship it.
- **TDD.** Tests first (red → green → refactor), defining behavior — not retrofitted to match output. New behavior ships with a test.
- **Honesty over optimism.** Report outcomes faithfully: failing tests stated with their actual output; "done" only when verified end-to-end; "I don't know, need to check X" beats a plausible guess. Distinguish observed / inferred / guessed; read the artifact before claiming a root cause.
- **No silent failures.** Every `catch`/`except` logs with context; no bare swallow-and-continue.
- **Named constants.** No magic numbers — thresholds, timeouts, and parameters are named, with rationale.
- **Terse inline comments.** Comments say what's non-obvious; the *why* and the patch/arc history go in commit messages / patch notes, not verbose source docstrings.
- **No cross-repo filesystem coupling.** Inter-service comms are HTTP + pinned contracts (OpenAPI / JSON schema), never `../SiblingRepo` imports.
- **Secrets & config through one typed boundary.** Never commit secrets; read config/secrets via the service's settings layer, not scattered raw env reads in leaf modules.
- **Verify, don't trust "done".** Re-check claims (yours or an agent's) against real output before reporting complete.
- **Git hygiene.** Conventional commits (`type(scope): subject`). **Never** add `Co-Authored-By` or any AI-authorship trailer. Batch pushes (one per repo per batch). For repos whose `main` is a live deploy, keep unpolished/audience-facing WIP on a branch — docs/internal changes to main are fine.
- **Anthropic model lineup (current as of 2026-07).** When pinning Claude models in code, configs, or agents, use bare aliases from the current family: `claude-opus-4-8` (default for coding/agentic work), `claude-sonnet-5` (balanced), `claude-haiku-4-5` (fast/cheap judges & bulk work), `claude-fable-5` (only when explicitly chosen - premium pricing, always-on thinking). Never date-suffix aliases; never pin retired `claude-3-*`/`claude-2*` IDs (they 404). Claude 4.6+ API rules: adaptive thinking (`{"type": "adaptive"}`, no `budget_tokens`); never send `temperature` + `top_p` together (Opus 4.7+/Sonnet 5/Fable reject sampling params entirely); no assistant prefill (use `output_config.format`); system prompts go in the top-level `system` param. Agent tiering: main thread on the strongest available model (Fable 5 / Opus-tier); delegate mechanical, self-contained subtasks to Sonnet/Haiku subagents.

**Per-language specifics:**

| Lang | Rules |
|------|-------|
| **Python** | PEP 8, type hints, docstrings, 120-col (`.flake8`); `ruff` + `black` + `mypy` clean; no god files (~1000-line file / ~300-line fn ceiling); pre-compiled regex on hot paths; no raw `os.getenv` in app code — go through the settings boundary. |
| **Rust** | `cargo fmt` + `cargo clippy` clean; split handlers/modules (no god `main.rs`); typed config (figment); `SecretString` for secrets. |
| **TypeScript / Next.js** | `strict` TS (no leaked `any`), ESLint + Prettier clean; no secrets in client bundles; separate components from state/data logic. |
| **C# / Unity** | Standard C# conventions + analyzers; no magic numbers; keep `MonoBehaviour` thin — delegate logic to testable plain-C# services. |

**Before calling it done:** run the repo's verify gate (`npm run verify` / `pytest` / `cargo test` / `npm run lint`), paste the real output, fix, re-run.
