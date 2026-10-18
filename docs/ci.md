# Hosted CI acceptance

Every required job uses GitHub-hosted runners. No GPU, self-hosted runner,
credential, paid model API or production service is required.

`CI required` fails unless every prerequisite succeeded, including cancelled or
unexpectedly skipped jobs. It runs on pull requests, main pushes and merge groups.
The Python matrix covers Linux 3.10–3.14 and Windows/macOS portability. Ruff checks
the shipped package and CI helpers; mypy enforces metrics, planner constants,
signed contributions/replay, prediction scoring, campaign receipt validation/gates,
plan-bound trace replay/CLI and the native registry bootstrap boundary. The
independent validation corpus/error-band
tests remain part of the full suite.

`uv.lock` contains the universal dependency resolution and distribution hashes.
PR/release jobs refuse a stale lock. Build tooling is included in the lock and
distributions are built without a second isolated, live dependency resolution.
Dependabot updates the uv lock and immutable Action references. The separate daily
`Dependency drift` workflow deliberately resolves supported ranges against the
current index, runs the full suite and SDK calls, and audits that environment.

The build job creates one wheel and one sdist. Linux, Windows and macOS acceptance
install the wheel with hash-locked dependencies into a fresh temporary environment,
outside the checkout. They also rebuild the sdist and repeat acceptance in another
environment. Isolated subprocesses assert import origin, package/version identity,
bundled data resources, offline CLI behavior and actual MCP client tool/error calls.
The candidate Docker target consumes that same wheel and locked dependencies;
the default published-image target retains its PyPI installation behavior.

The consumer composite action is exercised with a candidate wheel for a successful
plan and an expected no-fit failure. It posts no comment during acceptance.
Focused mutation testing requires a passing unmutated baseline, exact mutation
anchors, assertion failures and no setup/collection errors. Hypothesis checks use
independent unit and statistical derivations rather than shared implementation
constants.

Coverage is measured with branches enabled. The first baseline on main source
`9a72f7050442c7786ad3f4ce93b11faee81861f1`, using CPython 3.12.13 on Windows,
was 89.1058% lines and 82.7088% branches (2,792 passing tests). The global floors
are 89% lines and 82% branches. Critical metrics enforce 94% lines/90% branches;
planner constants enforce 95%/90%. Missing critical-module evidence fails.
The metrics baseline exposed untested NVML byte/string conversion and cleanup;
the added CPU unit tests cover those paths. Floors are ratchets, not targets to
lower when a change fails.

Real CPU acceptance pins Ollama and a small public GGUF by SHA256/revision, forces
CPU execution, and verifies generation, streaming, interrupted-request recovery,
benchmark JSON, reports and measured workload consumption. It exercises missing
model, wrong-engine and malformed-metrics failures. It proves this CPU integration
path; it establishes no GPU speed, GPU compatibility, detector sensitivity or
general planner accuracy. Shared-runner token-rate thresholds are deliberately
absent. Downloads, startup and operations have explicit time limits.

Installed wheel/sdist consumers exercise checkpoint save/check/export with an
offline protocol fixture. The existing Linux CPU consumer additionally performs
anonymous metadata/config reads for SmolLM2-135M-Instruct at
`12fd25f77366fa6b3b4b768ec3050bf629380bac`, checks its declared LFS identity, then
executes the installed CLI loop and an explicit network recheck. This adds no
weight download. Receipts distinguish the offline fixture, real Hub metadata,
config-byte verification and unverified loaded/weight-byte identity; neither path
qualifies a serving engine's revision handling or GPU performance.

Publishing requires a matching version tag reachable from main, consistent MCP
metadata, and the complete reusable CI validation at that tag. The publish job
downloads the validated distributions instead of rebuilding them, creates build
provenance, and uses PyPI OIDC publishing. MCP metadata is validated before the
PyPI upload and its publisher binary is digest-pinned. Ordinary CI never publishes.
Public registry readiness checks exact non-yanked file hashes and launches the
actual pinned uv registry command through the supported MCP SDK stdio transport.
One original deadline covers visibility, launch attempts, waits and conversation.
A fresh launch is permitted only after the native process has exited with the
exact pinned root-package absence diagnostic, emitted no raw stdout, and supplied
a complete argv-bound cleanup receipt. Unknown or combined resolver failures,
timeouts, cancellation, malformed receipts and application failures are terminal.
The installed-distribution job exercises this native path against the candidate
wheel. It does not use a separate pip resolver as evidence of uv readiness.
Private native stderr is bounded and reduced to categorical diagnostics; raw
clauses, URLs, paths and response bodies are omitted. SDK cancellation and process
cleanup are exercised separately from a successful MCP application conversation.
Whole-campaign gate consumers also run from the installed wheel and rebuilt sdist.
Synthetic protocol fixtures check decision arithmetic and invalid populations;
the existing CPU consumer gates its already-produced native campaigns without
loading another model. Categorical CPU replay diagnostics are emitted before
assertions, retaining safe counts, binding states and missing/invalid numeric fields.
Plan-bound trace consumers reuse that installed SSE protocol fixture with an
explicit modeled-Linux candidate on each host OS. They qualify package/protocol
portability, not a GPU engine or deployment platform. The actual CPU consumer
adds one short request on its already-loaded model and retains known CPU/GPU
binding mismatch separately from successful native execution and SLO outcomes.
Distribution artifacts have a three-day retention and a concrete downstream
consumer; routine test/coverage evidence stays in logs and job summaries.
