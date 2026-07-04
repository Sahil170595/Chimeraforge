---
name: verify
description: Run Chimeraforge's canonical verification gate end-to-end and report the real output before claiming work done or committing. Failing output gets pasted, fixed, and re-run — never summarized away.
---

# Verify — Chimeraforge

Honesty rules: paste actual command output (not a summary), fix failures, re-run until green,
and state explicitly anything you could NOT verify (live-stack-only paths, GPU-gated paths).
A skipped step is reported as skipped, never implied as passing.

## Gate

1. `python -m pytest` (CLI + capacity planner tests).
2. Scene work: `main` autodeploys to chimeraforge.vercel.app — WIP scenes go on a branch, and static gates passing does NOT prove visual correctness; check the rendered scene.
