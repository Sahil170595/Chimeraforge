# Kubernetes inspection protocol evidence

This is editable-source controlled protocol evidence for unreleased 0.85.0,
not installed-distribution, native kubectl/kind, inference or GPU qualification.
[summary.json](summary.json) records the actual timestamp, control rows, owned
process count, source-byte preservation, raw CLI byte parity and source hashes.
It contains no config/resource bodies, credential values or runtime input paths.

Regenerate from the repository using the existing development environment:

```bash
python scripts/ci_kubernetes_inspection.py \
  --record validation/2026-10-30-kubernetes-inspection/summary.json --checkout .
```

The native planner emits original N3 candidates for both supported engines.
Controlled responses travel through real owned Python subprocess pipes and the
actual API/in-process CLI; a separate actual module CLI checks raw missing-tool
stdout bytes. This does not exercise kubectl syntax. Matching status, drift,
pending status, missing Service, unsupported provider and wrong identity retain
all six original resources and ten declared JUnit cases. Completed private
inventory permits paired API/CLI files; incomplete inventory must refuse every
requested file while bounded stdout and typed outcomes remain available.

The existing installed consumer runs this same protocol against each actual
wheel/rebuilt-sdist package with all-loaded-module origin checks. Native pinned
tool syntax, real GPU-declaration/pending-rollout4, restricted authentication,
credential-policy and legacy-home migration controls are separate requirements
in the existing owned kind job. Pure status 0 is not a real GPU-ready result.

The [feature contract](../../docs/kubernetes-inspection.md) states the supported
profile, bounded export/stream/work claims, independent intent, private guards,
complete cases, per-file atomicity and cooperative cleanup limits.
