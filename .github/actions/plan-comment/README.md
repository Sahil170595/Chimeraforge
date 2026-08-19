# ChimeraForge plan comment (GitHub Action)

Posts a capacity plan as a sticky pull-request comment, so changing a model or a
serving config shows its deployment consequences **in review** rather than after
deploy: VRAM per GPU, fleet size, throughput, p95 latency, monthly cost, and the
effective cost once duty cycle is accounted for.

## Usage

```yaml
name: Deployment plan
on:
  pull_request:
    paths: ["serving/**", "helm/**", "**/model_config.yaml"]

permissions:
  contents: read
  pull-requests: write   # required to post the comment

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: Sahil170595/Chimeraforge/.github/actions/plan-comment@main
        with:
          hardware: "H100 80GB"
          model: "Qwen/Qwen3-8B"
          request-rate: "2.0"
          latency-slo-ms: "5000"
          budget: "5000"
          extra-args: "--duty-cycle 0.3 --compare-api"
          version: "0.21.0"   # pin for reproducible comments
```

## Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
| `hardware` | yes | - | GPU name; see `chimeraforge plan --list-hardware` |
| `model` | no | `""` | Registry name, HF repo, or Ollama tag |
| `model-size` | no | `8b` | Registry size class, used when `model` is empty |
| `request-rate` | no | `1.0` | Requests per second |
| `latency-slo-ms` | no | `5000` | p95 budget |
| `budget` | no | `1000` | Max monthly USD |
| `extra-args` | no | `""` | Passed through verbatim (`--kv-quant q8`, `--tp 4`, ...) |
| `version` | no | `latest` | Pin this so a comment does not change under you |
| `comment` | no | `true` | Set `false` to use the outputs only |
| `fail-on-no-fit` | no | `false` | Off by default: not fitting is information, not a broken build |

## Outputs

`plan-json` (raw `--json` payload), `fits` (`true`/`false`), `monthly-cost`,
`summary` (the markdown, also written to the job summary).

## Notes

- The comment is **sticky**: it is found by a hidden marker and edited in place, so
  a busy PR gets one comment that updates rather than a wall of them.
- Every number carries ChimeraForge's `measured` / `estimated` / `unknown`
  provenance, and the plan's warnings are reproduced in the comment -- an estimate
  is never presented in review as a measurement.
- Posting needs `pull-requests: write`. On a fork PR, GitHub withholds that token,
  so set `comment: false` and consume the outputs instead.
