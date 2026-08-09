# Agent-experience & correctness audit — 2026-08-08

> **Status, 2026-08-09.** Section 1's four correctness defects are **fixed** (PR #21), and
> the PyPI/site link gap in section 3 is closed. They are kept below in full rather than
> deleted: the finding, the reproduction and the reasoning are why the fix looks the way it
> does, and a defect report that disappears the moment it is resolved leaves the next reader
> unable to check whether the fix addressed the actual problem. Sections 2 and 3.1–3.3 are
> still open.
>
> One correction to this document's own method, recorded because it misled me once: the
> "33 pre-existing test failures" I reported while working on the fix were an artefact of a
> venv missing the `dev` extra this repo declares. With `pip install -e ".[dev]"` the suite
> is **558 passed, 0 failed**. The repo was green throughout.

Companion to `ROADMAP_RESEARCH_2026-08.md`. That document surveys the market and ranks
features; this one is the **defect half**: what the tool does when it is actually run, and
what happens when an AI assistant — rather than a human who wrote it — is the caller.

**Method.** chimeraforge `0.6.2` installed from PyPI into a clean venv, and `0.12.0` built
from this tree, probed side by side: 48 CLI invocations plus source read from both installs.
Every finding below is quoted from real output. Claims are labelled `[V]` verified by running
it, `[R]` from published research, `[I]` inferred. There are no `[I]` claims in this document.

---

## 0. The finding that reorders the rest

PyPI serves **0.6.2**. This tree is **0.12.0** — six minor releases ahead, carrying tensor
parallelism (0.10.0), pipeline parallelism (0.11.0), the 22-GPU hardware table (0.7.0) and
the MCP server (0.12.0) **[V]**.

Two coverage gaps this audit set out to report were already closed in code no PyPI user can
reach. The largest single lever is therefore not a feature — it is a release.

Everything below is split into **still broken at 0.12.0** (re-verified against the local
build) and **merely unreleased**.

---

## 1. Still open at 0.12.0 — correctness

These four were found on 0.6.2 and re-run against the 0.12.0 build. All four survive.

### 1.1 `--model-size` above 8b silently returns an 8B plan `[V]`

> **RESOLVED (#21).** `find_models_for_size` now raises `ResolverError` for both the
> unparseable and the out-of-span case, naming the registry's span and both escape
> hatches. Five tests that had specified the substitution were rewritten.


The registry holds 1b, 3b and 8b. Everything else — including a nonsense value — falls
through to `llama3.1-8b` and reports its numbers, with an empty `warnings` array, empty
stderr and **exit 0**. Not rescued by network resolution.

```
$ chimeraforge plan --model-size <SIZE> --hardware "A100 80GB" --budget 5000 --json

  size | rows | model        | params_b | vram_gb | quant
    1b |   18 | llama3.2-1b  |     1.24 |    2.98 | FP16
    3b |   72 | llama3.2-3b  |     3.21 |    4.12 | Q8_0
    8b |   21 | llama3.1-8b  |     8.03 |    4.55 | Q3_K_S
   13b |   21 | llama3.1-8b  |     8.03 |    4.55 | Q3_K_S   <-- wrong
   30b |   21 | llama3.1-8b  |     8.03 |    4.55 | Q3_K_S   <-- wrong
   70b |   21 | llama3.1-8b  |     8.03 |    4.55 | Q3_K_S   <-- wrong
  405b |   21 | llama3.1-8b  |     8.03 |    4.55 | Q3_K_S   <-- wrong
banana |  129 | llama3.1-8b  |     8.03 |    4.55 | Q3_K_S   <-- accepted
```

The offline model path degrades the same way while keeping the requested name, which is
worse — the output reads as a specific answer about a specific model:

```
$ chimeraforge plan --model meta-llama/Llama-3.1-70B-Instruct --no-network --json
  model=meta-llama/Llama-3.1-70B-Instruct  params_b=8.03  vram_gb=4.55
  model_source=registry-approx
```

`registry-approx` is an honest label carrying a number wrong by ~9x, on the one field the
tool exists to get right.

**Patch.** Resolve `--model-size` against the registry and exit non-zero when the class has
no entry, naming the classes that do. Apply a tolerance to `registry-approx`: an
approximation that changes the parameter count by more than a set factor is not an
approximation, it is a different model.

### 1.2 `--json` is not a contract — prose lands on stdout `[V]`

> **RESOLVED (#21).** Diagnostics moved to a stderr console; `--list-hardware` and
> `--list-models` now honour `--json`; the empty catalog emits a valid empty document.


All ten commands accept `--json`, which is a good foundation. But human-readable text goes
to the same stream, so output stops being JSON while the exit code still says success.
Three confirmed cases at 0.12.0:

```
$ chimeraforge plan --hardware "totally-bogus-gpu" --json
exit=0, json=BROKEN :: "Warning: 'totally-bogus-gpu' not in hardware DB, using default RTX 408..."

$ chimeraforge catalog --json
exit=0, json=BROKEN :: "Catalog is empty. Run chimeraforge catalog --build to populate it."

$ chimeraforge plan --list-hardware --json
exit=0, json=BROKEN :: "                 Available GPUs                  ┌────..."
```

`--list-hardware` is the one command an agent most needs machine-side: it is the only way to
discover valid `--hardware` values.

**Patch.** Under `--json`, stdout carries exactly one JSON document and nothing else; every
warning, notice and empty-state message goes to stderr. One test per command asserting
`json.loads(stdout)` succeeds on the happy path, the empty path and the warning path.

### 1.3 "Nothing fits" is indistinguishable from "you asked wrong" `[V]`

> **RESOLVED (#21).** `summarize_trace()` already existed and was gated behind
> `not output_json`. It now prints to stderr under `--json`, so stdout stays exactly one
> array: `blocked at budget gate - ollama: $1800/mo (N=1) > $100`.


The default `--budget` is 100 USD/month. The hardware DB prices an H100 at $2.50/hr, about
**$1,825/month** at full uptime. So the most obvious question a user can ask returns an empty
array and exit 0, with no indication that an unset default is rejecting every candidate.

```
$ chimeraforge plan --model-size 70b --hardware "H100 80GB" --budget $B --json
  --budget   100  exit=0  rows=0     <- the default
  --budget   500  exit=0  rows=0
  --budget  2000  exit=0  rows=21    <- $1,825/mo is the real floor
  --budget  5000  exit=0  rows=21
```

This is not hypothetical harm. Researching this audit, I recorded that `"H100 80GB"` was not
in the hardware DB. It is. The empty result told me nothing, so I inferred a cause and was
wrong — the exact inference an assistant will make and report to a user as fact.

**Patch.** Return a rejection ledger rather than an empty list: candidates generated, how
many each gate eliminated (`vram: 0, budget: 21, latency: 0`), and the cheapest constraint
relaxation that would admit one. Reserve a distinct exit code for "searched, nothing
qualified" so a caller can tell it from success.

### 1.4 An unknown GPU name is substituted, not refused `[V]`

> **RESOLVED (#21).** Refused with the known-GPU list; no substitution.


`--hardware "totally-bogus-gpu"` warns once and plans on RTX 4080 12GB specs, returning a
full result set. Because the warning goes to stdout (1.2), a caller that strips non-JSON
lines to recover the payload gets 21 rows about a GPU nobody asked for, with nothing in the
JSON recording the substitution. Lookup is a case-insensitive partial match, so near-misses
usually resolve to *something*.

**Patch.** Exit non-zero on an unresolvable GPU and list near matches. If a fallback stays,
put it in the JSON — `hardware_requested` alongside `hardware_resolved` — so the substitution
survives into whatever reads it.

---

## 2. Still open at 0.12.0 — coverage

### 2.1 Mixture-of-Experts: zero awareness `[V]` `[R]`

Grepping the installed 0.12.0 package for `moe|mixture.of.expert|active_param|num_experts`
returns **0 hits**. MoE is the dominant open-model shape of 2026: total parameters set
memory, active parameters set speed `[R]`. Chimeraforge resolves total params from HF, so
VRAM lands by luck — but throughput is modelled from parameter count, so a Qwen3-30B-A3B,
which decodes like a ~3B, will be predicted roughly 10x too slow.

### 2.2 Self-host vs API break-even: absent `[V]` `[R]`

Grepping for `break.?even|api_price|vs.?api` returns **0 hits**. The consensus economic
metric is cost per million tokens, and the decision people actually make is self-host versus
API — break-even near 2-5M tokens/day against frontier APIs, essentially never against budget
open-weight APIs `[R]`. `cost_per_1m_tok` is already emitted; this is a comparison table, not
a model.

### 2.3 Hardware table: two holes left `[V]`

0.7.0 took the table from 15 to 22 GPUs, adding RTX 5090, H200, B200 and MI300X. Apple
silicon and RTX PRO remain absent. `REFERENCE_GPU` is still `RTX 4080 12GB` and every other
card's throughput is a bandwidth-ratio extrapolation from it — correctly reported by the
`provenance` block as `estimated`.

---

## 3. The assistant path

### 3.1 Nothing about this tool is retrievable `[V]` `[R]`

Searching *"chimeraforge LLM deployment planner CLI"* returns no result about Chimeraforge.
The top hit is `chimera-cli` — a **different** PyPI package for cluster communication and
Docker builds `[V]`. The repo is 2 stars, 1 fork, 0 subscribers `[V]`. There is no
`llms.txt` `[V]`.

An assistant asked about Chimeraforge therefore has three options and two are bad: say it
doesn't know, confidently describe `chimera-cli` instead, or invent flags. Across 576,000
generated samples from 16 models, 19.7% of recommended packages did not exist at all `[R]` —
fabrication under this kind of information vacuum is the measured default, not an edge case.

### 3.2 The MCP server inherits every defect in section 1 `[V]`

0.12.0 adds `chimeraforge mcp`, exposing `plan` to assistants directly. That is the right
move and it removes flag-guessing entirely. But the tool it exposes is the same one that
answers `model_size="70b"` with 8B numbers, and an MCP client has *less* recourse than a
shell caller: no stderr to read, no exit code to inspect, just a result object that looks
authoritative.

This inverts the sequencing. Section 1 was worth fixing before the MCP server existed; now it
is worth fixing **first**, because the MCP path turns a wrong number into a wrong number an
agent states on your behalf.

### 3.3 What a fresh assistant got wrong on first contact `[V]`

Each of these was invited by the surface, so each will repeat:

- **Missed `--list-hardware`** — `plan --help` was piped through `head -50` and the flag sits
  below the cut. Agents truncate help constantly. The `--hardware` description says "GPU name
  from hardware DB" without naming the flag that lists it.
- **Concluded H100 was unsupported** — see 1.3.
- **Mis-attributed a UTF-8 BOM to the tool** — it came from PowerShell's redirect, caught only
  by checking raw bytes. A faster assistant files a bug that does not exist.
- **Failed to parse `--json` twice** before understanding that streams are mixed. The natural
  next step is to conclude the tool is broken.

Against that, the fundamentals are strong: `--help` is clean and complete, all ten commands
take `--json`, `--version` is parseable, and when an agent meets an unfamiliar CLI the first
thing it runs is `--help` `[R]`. The failures are all one layer in — where the tool answers.

**Patch.** Ship `llms.txt` and `llms-full.txt` on a docs URL; Cursor, Windsurf, Claude Code,
Copilot, Cline and Aider all fetch them by convention `[R]`, and none speaks MCP to a package
it has never heard of. Add a **usage**-facing agent skill: `AGENTS.md` today is a
*contributor* contract, which helps an agent modify this repo and does nothing for an agent
trying to use the tool. State the package name prominently against the `chimera-cli`
collision.

---

## 4. What is already right, and worth defending `[V]`

The network model path is the template the rest should be fixed toward. A gated repo produces
a clean, actionable failure instead of a guess, and an off-registry model is labelled rather
than silently approximated:

```
$ chimeraforge plan --model meta-llama/Llama-3.1-70B-Instruct --json
exit=1  Error resolving: HF repo is gated; set HF_TOKEN (or pass --hf-token).

$ chimeraforge plan --model Qwen/Qwen3-30B-A3B --json
  params_b=30.53  vram_gb=27.31  model_source=hf
  warnings=["off-registry model (hf): throughput is a roofline estimate, not measured",
            "quality unscreened (neutral 0.5 prior, not measured)"]
```

Every row carries per-dimension provenance —
`{vram: measured, throughput: estimated, quality: measured, safety: unknown}` — a stronger
honesty guarantee than any surveyed competitor ships. That is the asset. Every finding in
section 1 is a place where the tool *stops* doing this.

---

## 5. Reproduction

None of these needs a GPU or a network.

```bash
# 1.1 - size classes above 8b silently degrade
for s in 1b 3b 8b 13b 30b 70b 405b banana; do
  chimeraforge plan --model-size $s --hardware "A100 80GB" --budget 5000 --json --no-network \
    | python -c "import json,sys; r=json.load(sys.stdin); print('$s', r[0]['model'], r[0]['params_b'])"
done

# 1.2 - --json is not a contract
chimeraforge plan --hardware "totally-bogus-gpu" --json | python -m json.tool
chimeraforge catalog --json                             | python -m json.tool
chimeraforge plan --list-hardware --json                | python -m json.tool

# 1.3 - the default budget rejects every datacenter GPU
for b in 100 500 2000 5000; do
  chimeraforge plan --model-size 70b --hardware "H100 80GB" --budget $b --json --no-network \
    | python -c "import json,sys; print('$b', len(json.load(sys.stdin)))"
done

# 2.1 / 2.2 - MoE and break-even awareness
python - <<'PY'
import pathlib, re, chimeraforge as c
p = pathlib.Path(c.__file__).parent
for label, pat in (("MoE", r"moe|mixture.of.expert|active_param|num_experts"),
                   ("break-even", r"break.?even|api_price|vs.?api")):
    n = sum(bool(re.search(pat, l, re.I))
            for f in p.rglob("*.py")
            for l in f.read_text(encoding="utf-8", errors="replace").splitlines())
    print(f"{label}: {n} hits")
PY
```
