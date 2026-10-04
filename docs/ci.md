# Hosted CI acceptance

Every required job uses GitHub-hosted runners. No GPU, self-hosted runner,
credential, paid model API or production service is required.

`CI required` fails unless every prerequisite succeeded, including cancelled or
unexpectedly skipped jobs. It runs on pull requests, main pushes and merge groups.
The Python matrix covers Linux 3.10–3.14 and Windows/macOS portability. Ruff checks
the shipped package and new CI helpers; mypy currently enforces the metrics and
planner-constant modules. The existing independent validation corpus/error-band
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

Publishing requires a matching version tag reachable from main, consistent MCP
metadata, and the complete reusable CI validation at that tag. The publish job
downloads the validated distributions instead of rebuilding them, creates build
provenance, and uses PyPI OIDC publishing. MCP metadata is validated before the
PyPI upload and its publisher binary is digest-pinned. Ordinary CI never publishes.
Distribution artifacts have a three-day retention and a concrete downstream
consumer; routine test/coverage evidence stays in logs and job summaries.
