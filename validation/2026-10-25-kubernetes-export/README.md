# Kubernetes export source controls

Regenerate `functional.json` from the candidate source and its locked environment:

```bash
uv run --locked --all-extras python scripts/ci_kubernetes_export.py \
  --record validation/2026-10-25-kubernetes-export/functional.json
```

The script runs the actual CLI/API with two unmodified native plans, N1 and N3,
for both vLLM and SGLang. It checks all original resources, desired GPU totals,
independent match 0, redacted image drift 5, source-alias refusal 1 and unchanged
source bytes. Metadata records UTC capture time and source hashes. This is
offline synthetic declaration evidence, not API admission or GPU execution.

The same consumer is called by installed original-wheel/rebuilt-sdist acceptance,
using its existing pinned offline checkpoint metadata fixture and N1/N3 plans.
The separate required hosted `kubernetes-admission` job installs the built wheel
and exercises pinned kind/kubectl server validation and owned cleanup. Actual
job logs carry its receipt; this source record does not fabricate hosted results.

Focused behavior and ownership controls can be rerun without a cluster:

```bash
uv run --locked --all-extras pytest tests/test_kubernetes_export.py \
  tests/test_ci_kubernetes_admission.py tests/test_deploy.py \
  tests/test_deploy_fleets.py tests/test_deploy_placement.py \
  tests/test_deployment_verify.py tests/test_repo_conventions.py -q
```

The admission-helper tests use scoped command fixtures, never local Docker/kind.
They retain partial-create/primary-cleanup failures and preserve existing network
identity. Hosted logs separately prove real startup, strict admission, negative
controls, no persisted feature objects and actual closure. These controls do not
qualify engine launch, scheduling, weights, GPUs, performance or readiness.
