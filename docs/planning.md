# Using the Planner

ChimeraForge answers: **"For my hardware, workload, and budget, what should I
actually deploy?"** It searches (model x quantization x backend x GPU-instance
count) and filters through gates -- VRAM, quality, latency, cost, and an opt-in
safety screen -- then ranks the survivors. Every number carries provenance
(`measured` / `estimated` / `unknown`) so you know which to trust.

## plan -- recommend a configuration

By registry size class (uses the bundled, measured corpus):

```bash
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 1.0 --budget 300
```

For **any** model (the model-agnostic path) -- a Hugging Face repo, an Ollama
tag, or manual overrides:

```bash
# HuggingFace repo: pulls real params + attention geometry from config.json
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"

# Ollama tag: pulls GGUF metadata from a live /api/show
chimeraforge plan --model qwen3:14b --ollama-url http://localhost:11434

# Air-gapped / unreleased: supply the geometry yourself
chimeraforge plan --model my/model-7b --params-b 7 --n-layers 32 --n-kv-heads 8 --d-head 128 --no-network
```

Key inputs (all have explicit units and defaults; see `plan --help`):

| Flag | Meaning | Default |
|------|---------|---------|
| `--request-rate` | requests/sec | 1.0 |
| `--prompt-tokens` | input length (drives prefill / TTFT) | 512 |
| `--avg-tokens` | output length (drives decode / TPOT) | 128 |
| `--latency-slo` | max p95 end-to-end, ms | 5000 |
| `--quality-target` | min composite quality 0-1 | 0.5 |
| `--budget` | max USD/month | 100 |
| `--safety-target` | min refusal rate 0-1 (opt-in gate) | off |
| `--hardware` | GPU name (`plan --list-hardware`) | RTX 4080 12GB |

Reading the output: the **Performance** panel reports N=1 throughput, **TTFT**
(prefill, compute-bound), **TPOT** (per output token, bandwidth-bound), end-to-end
p95, and **max concurrent sequences per GPU** (KV-cache bound). A `~` marks an
estimated number. If nothing fits, the planner names the **binding gate** ("Why
nothing fit"). Add `--json` for machine-readable output (clean for CI / `jq`).

## measure -- plan on real numbers, not estimates

For an off-registry model the throughput starts as a roofline *estimate*. Benchmark
it once and the planner switches to *measured*:

```bash
chimeraforge measure --model qwen3:14b --ollama-url http://localhost:11434
chimeraforge plan --model qwen3:14b --measure   # measure, then plan, in one step
```

`measure` runs the real `bench` machinery (N=1 throughput, service time, and
concurrency scaling) and folds it into a local corpus
(`~/.cache/chimeraforge/fitted_models.json`); `plan`/`suggest` prefer it
automatically afterward. Quality is deliberately not auto-measured -- it stays
labeled `estimated`/`unknown` rather than faking a benchmark composite.

## suggest -- discover and rank models

```bash
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500
chimeraforge suggest --source hf --hf-limit 8 --hardware "RTX 4080 12GB"
chimeraforge suggest --source catalog --hardware "RTX 4080 12GB"   # offline, after `catalog --build`
```

Pulls candidate models from your installed Ollama (`/api/tags`), the HF Hub
(top text-generation), and/or the local catalog; resolves each to real specs;
and shows the best config per model.

## catalog -- a local, offline model set

```bash
chimeraforge catalog --build           # resolve a curated seed (+ --with-ollama), cache specs
chimeraforge catalog                   # list what is cached
```

Once built, `suggest --source catalog` ranks the set with no network.

## How predictions are made (and their limits)

- **VRAM / KV-cache:** first-principles from real architecture -- exact for any model.
- **Throughput:** measured lookup when available; otherwise a memory-bandwidth
  roofline for decode. Roofline is a best-case estimate; use `measure` for real numbers.
- **Quality:** measured composite (registry) or a family prior (`estimated`) or a
  neutral `unknown` -- never a fabricated benchmark.
- **Safety:** lookup-only (TR134/TR142); `unknown` for unscreened models, by design.
- **Cost:** GPU $/hr x instances; `$/1M tokens` is invariant in replica count.

Network resolution (HF / Ollama metadata) needs the `resolve` extra
(`pip install "chimeraforge[resolve]"`). The `--no-network` flag and manual
overrides keep it fully offline.
