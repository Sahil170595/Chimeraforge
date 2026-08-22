# Changelog

All notable changes to ChimeraForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **The reference rig was specified as a card it is not, so every cross-GPU number was ~29% off.** `REFERENCE_GPU` is the denominator of every bandwidth extrapolation and of `MBU_DEFAULT`, and it carried 556 GB/s / 285 W -- figures belonging to neither the RTX 4080 **Laptop** the corpus was measured on (192-bit, 432 GB/s, 60-150 W TGP per NVIDIA, fetched 2026-08-22) nor the desktop RTX 4080 (717 GB/s, 320 W). The rig is the laptop part: the README says so, CLAUDE.md pairs it with an i9-13900HX mobile CPU, and no desktop RTX 4080 12GB exists. Corrected to 432 GB/s / 150 W.
- **`MBU_DEFAULT` re-derived: 0.65 -> 0.84.** It is back-solved from a single calibration point, so correcting the denominator necessarily moves it -- the rig was achieving 84% of its real bandwidth, not 65% of a bandwidth it does not have. **The reference card's own predictions are unchanged** (`0.65 x 556 == 0.84 x 432`, verified to the digit); every other GPU rises ~29%.

### Added
- **`fitted_models.json` now carries a `_provenance` block** -- `captured_at`, source, method, reference hardware, coverage and limitations. It is the dataset that decides which numbers may say `measured`, and it shipped with none of this while `api_pricing.json` beside it had all of it. Coverage is computed from the file and re-derived by a test, so a drifting claim fails. Recorded plainly: all 23 throughput rows are FP16, the largest model measured is 3.21B, and there are no SGLang rows -- so every quantized number is an FP16 row times a multiplier. No regeneration script was added, because the TR raw artifacts live outside this package and a stub that cannot regenerate anything would be worse than the declared gap.


### Fixed
- **One `measure` run could silently replace the fitted power law with a placeholder.** `fit_power_law` returned `(100.0, 0.5)` when it could not fit, and `merge_fitted_models` writes the result when it `is not None` -- a tuple is not None. The TR133 coefficients (a=72.11, b=0.0888) were overwritten, making a 70B predict **12.0 tok/s instead of 49.5 (-76%)** and a 0.5B **141.4 instead of 76.7 (+84%)**. The summary flag was literally `pl != (100.0, 0.5)`, so the code already knew no fit had happened and reported `power_law_refit: False` while writing the value anyway. Now returns `None`, including on the scipy-unavailable branch, which corrupted the corpus precisely in the environment least likely to notice.
- **`refit` wrote its output where nothing reads it.** It defaulted to platformdirs' `user_data_dir` while `plan`/`suggest`/MCP read `~/.cache/chimeraforge`, so a successful refit printed "Saved to ...", exited 0, and was completely inert. Both sides now use `measured_corpus_path()`, so `$CHIMERAFORGE_CACHE` moves them together.
- **`bench --all-quants` produced rows that differ only by noise.** `quant` reaches the result object but never the backend -- no adapter takes a per-request quantization, because a quant is a property of the loaded artifact. Every row of a sweep was the same served model re-run under a different label, including AWQ/GPTQ which Ollama cannot serve, and those rows flow into `refit` and become per-quant corpus keys reported as `measured`. Each row now carries the same disclosure `run_context_sweep` already emits.
- **`measure` printed a scaling factor the planner does not use as green `(measured)`.** `ScalingModel.predict_eta` has no consumers -- the engine hardcodes `eta = 1.0` deliberately, since replica fan-out is linear. The measurement is real so it stays, but the label now says it is not used by the planner.


### Fixed
- **A 405B tag was sized as an 8B model, with quality reported as `measured`.** `resolve_model` short-circuited on a family with exactly one registry model and returned it "regardless of the parsed size" -- the docstring said so, as though it were a feature. So `llama3.1:405b` resolved to `llama3.1-8b`, and the planner returned **params_b 8.03, VRAM 4.55 GB, quality 0.639 (measured)** for a 405-billion-parameter model, because every gate downstream reads the alias's rows. The size was parsed correctly the whole time and then discarded. Only two families have a single member, which is why it survived. A parsed size is now always honoured, and an unresolvable tag is refused with an actionable message rather than answered with a smaller wrong number.
- **An approximated alias no longer confers `measured` on quality or safety.** Reusing another model's rows for throughput is defensible; quality and safety are properties *of* a model, and reporting another one's as measured attributes a benchmark to weights that never ran.
- **`measure --quant` is verified against the artifact the backend is actually serving.** The label becomes part of the corpus key, and that key is what `plan` later reports as measured -- so an unchecked label attributed one quantization's rate to another permanently. The served artifact now wins, and the swap is disclosed.
- **Cached model specs expire.** The spec cache is consulted ahead of the network, so a repo whose `config.json` changed upstream was answered from the stale copy indefinitely with no way to notice. Entries are stamped and expire after `SPEC_CACHE_TTL_DAYS`; entries written before stamping existed are treated as expired rather than trusted.


## [0.30.0] - 2026-08-22

### Fixed
- **A measured-on-a-different-GPU number was labeled `measured`.** The throughput lookup key is `model|backend|quant` and carries no hardware, but every row in the corpus came off one rig. A key hit set the label, and only afterwards was the value multiplied by `bandwidth_ratio(hardware)` -- so `llama3.2-3b` on a B200 reported **1327.5 tok/s labeled `measured`, a 13.8x extrapolation of a 95.9 tok/s RTX 4080 measurement, with zero warnings**. This is the worst failure this project can have: a crash is visible, a confidently-wrong `measured` badge is not, and it is the field the MCP server hands an assistant and the brief renders as prose.
- **Two honesty checks were disabled by that bug, and re-arm with it.** The fleet's "a mix compounds throughput error across types" warning and `validate.classify()` both keyed off `provenance["throughput"] == "measured"`, so on datacenter GPUs -- which are never the reference rig -- the warning never fired and the audit filed bandwidth-extrapolated cells under `measured-lookup`, the bucket meaning "not an out-of-sample test". The falsification harness could not have detected the bug it was pointed at.
- **The brief gave pure models and pure arithmetic the throughput label.** VRAM, TTFT, TPOT and p95 all rendered as "measured on the TR benchmark corpus"; TTFT is a FLOPs estimate nobody ever measured, and VRAM is arithmetic. VRAM is now `derived`; the latency rows are `estimated` unconditionally, since a queueing model layered on a throughput number cannot be better grounded than the model.
- **The formatter read provenance with a `"measured"` default**, so an absent label failed *open* to the strongest possible claim. It now fails to `unknown`.

### Added
- A fifth provenance value, **`extrapolated`**: a real measurement taken on the reference rig and scaled to this GPU by memory bandwidth. It ranks between `measured` and `estimated` -- better grounded than a pure roofline, but not a measurement of the card in hand -- and every such plan states the factor and names the rig.


## [0.29.0] - 2026-08-22

### Added
- **`plan --fleet "H100 80GB,A100 80GB,L4 24GB"`: heterogeneous fleets.** The planner has always sized N identical replicas of one GPU, which is a constraint on the *answer*, not just the search -- a cheap GPU can be the better buy at loose SLOs and small requests while an expensive one wins at tight SLOs and long requests, so the cheapest fleet is often a mix. Melange (arXiv:2404.14527) measured this across L4/A10G/A100-80G/H100 and reports up to 77% saved in conversational settings. On an 8B at 64 req/s the mix here picks 1x H100 + 1x L4 at $2,160/mo over the best single type (2x A100, $2,304) -- the last 0.9 req/s is cheaper on a small GPU than on a second big one.
- `--fleet` also extends the `--json` wrapper with a `fleet` key, on the same opt-in basis as `--launch` and `--compare-api`, so the default bare-array contract is unchanged.

### Notes
- **This sits on top of the gate search, not inside it.** Each GPU type is priced by running the existing `enumerate_candidates` pipeline against that GPU alone, so every gate and every piece of serving physics applies unchanged and a mixed fleet cannot become a back door around a check the homogeneous path enforces.
- **A mixed fleet needs a router that does not exist.** It presumes traffic is split by GPU capability; vLLM and SGLang do not ship such a router, and the source study explicitly leaves heterogeneous load balancing as future work. Every mixed plan says so and cites the paper.
- **Provenance is the worst across the types used, never the best** -- otherwise one measured GPU would launder several estimated ones. Mixing compounds throughput error across types instead of concentrating it in one, and the plan says that too.
- Savings are quoted against the **best** single GPU type, not an arbitrary one; a badly-chosen baseline inflates the number the way a vendor benchmark does. Where homogeneous is already optimal, the plan says "no saving" rather than manufacturing a mix to justify the flag.
- Private planning docs are now glob-ignored (`ROADMAP_*.md`) rather than listed one by one -- each new one was a single `git add -A` away from being committed.

### Fixed
- The allocator's capacity quantisation used float floor-division, and `100.0 // 0.05` is 1999 rather than 2000. That shaved a step off every GPU's capacity, forcing a spurious extra unit and quietly inflating the bill with an answer that looked entirely reasonable. Caught by a hand-computed optimum, and pinned by a test.


## [0.28.0] - 2026-08-21

### Added
- **`chimeraforge workload`: derive plan inputs from real traffic.** `plan` takes a request rate, prompt and output lengths, a traffic-variance preset and a prefix-cache hit rate -- and today all five are typed in by hand. The variance one is picked from a menu of four, which means the queueing tail, the part of the answer people most want, rests on a guess. Every one of them is already being measured by whatever is serving the traffic. `--from-log requests.jsonl` reads a request log; `--from-metrics URL --engine vllm|sglang` scrapes a live `/metrics` endpoint.
- **`plan --workload-profile p.json`** consumes the profile. An explicitly passed flag always wins -- that is a deliberate scenario ("what if traffic tripled"), and overwriting it with yesterday's measurement would answer a different question.

### Notes
- **Metric names are per-engine and explicit; an unknown engine is an error.** vLLM renamed `gpu_cache_usage_perc` to `kv_cache_usage_perc` and `time_per_output_token_seconds` to `inter_token_latency_seconds` between documented versions. A scraper that quietly falls back to a stale name reports a fabricated measurement, which is worse than reporting nothing. Names were read from each project's own metrics reference, a test asserts no renamed vLLM name is referenced, and pointing the wrong `--engine` at an endpoint fails loud instead of returning an empty profile.
- **A log gives `measured`; a histogram gives `estimated`.** Per-request rows carry the real distribution, so mean and variance are both exact. A Prometheus histogram gives sum and count exactly but the spread only through bucket edges, so a CV^2 from one is approximated at bucket midpoints and labeled accordingly.
- **A single scrape is not a rate.** `request_rate` is left absent rather than derived by dividing a counter by a process uptime nobody measured.
- Flag-beats-profile precedence is decided by comparing Click's parameter source **by name**. Typer 0.27 vendors its own Click, so the value is a `typer._click.core.ParameterSource` and an identity test against `click.core.ParameterSource` is False -- which silently made every explicit flag look unset. It passed under Typer 0.25 and failed under 0.27; CI caught it.
- **An absent field never acquires a default.** It stays a required explicit input to `plan`, so a partial profile cannot smuggle a made-up value in under the profile's `measured` badge. The profile records `captured_at`, source, engine and engine version.


## [0.27.0] - 2026-08-21

### Added
- **Multi-LoRA serving: `--lora-adapters N --lora-rank R [--lora-target qv|attn]`.** Serving many fine-tunes off one base model is an established production pattern, and the sizing question ("how many adapters fit") has an exact answer. LoRA factorises a `(d_in x d_out)` weight into `A (d_in x r)` and `B (r x d_out)`, so an adapter costs `r * (d_in + d_out)` per target module per layer. The derivation is pinned to the published PEFT parameter count for Llama-2-7B q/v (`524288 * r`), not to itself.
- **`--hidden-size` manual override.** Needed to size adapters and MoE experts exactly, and previously missing from the override set.
- Launch export emits `--enable-lora --max-loras --max-lora-rank` (vLLM), `--lora-paths --max-loras-per-batch` (SGLang), `--lora-adapters` (TGI). MCP `chimeraforge_plan` takes the same knobs.

### Notes
- **VRAM is exact; the decode cost is not, and they are labeled differently.** The speed penalty comes from one vendor sweep on one engine, one GPU, one model, which published two rank endpoints and *not* the two intermediate ranks it tested. So the multiplier is anchored on those endpoints, interpolated in log2(rank) between them, clamped rather than extrapolated outside them, and every LoRA plan carries a warning naming the source and its scope.
- **Adapter count drives VRAM only.** The same source found throughput near-flat from 2 to 64 adapters, so scaling the decode rate by count would be a fit to nothing; the residual ~10% spread is declared unmodelled rather than fitted to two digits. Per-adapter KV fragmentation is likewise not modelled.
- **A spec without a real `hidden_size` is rejected, not guessed.** Collapsing hidden to the GQA KV width would under-size the adapter, and an under-sized adapter claims a fit that is not there.
- Ollama is not given LoRA flags: llama.cpp merges an adapter into the base weights rather than serving adapters per request, so it gets a note saying so.
- Adapter paths are a `<adapter-path>` placeholder. The planner does not know where they live, and a command that looks runnable while silently serving the wrong adapter is worse than one that visibly needs filling in.


## [0.26.0] - 2026-08-21

### Added
- **`plan --report brief.md`: the plan as a document a team can argue with.** A terminal panel answers "what should I run"; defending a GPU purchase in a meeting needs a dated record of what was assumed, where each number came from, what the alternatives cost, and the exact command that reproduces it. The brief carries all of that, including the planner's warnings verbatim.
- **A fourth provenance class, `derived`.** GPU count and monthly cost are exact arithmetic over the inputs and the GPU price database -- not predictions, and not measurements either. Filing them under `measured` would have cited the TR benchmark corpus as the source of numbers it never measured.

### Notes
- The report **refuses to render** on a stale price snapshot rather than printing an old price in a nicer font: a formatted document reads as more durable than a terminal line, and its reader will not re-derive the arithmetic. It also refuses when no configuration fits, and exits non-zero in both cases so a CI job fails rather than continuing with no file where one was expected.
- Prose is generated *from* the provenance labels rather than written next to them, and a rule test walks the rendered table asserting every row carries a phrase. An unqualified sentence silently outranks the `~` meant to qualify it.

### Fixed
- `--model` is repeatable, so the brief's reproduction command was handed a list where it expected a string and raised `TypeError` at render time -- after the plan had already run. Found by a test that was passing as a skip.


## [0.25.0] - 2026-08-21

### Added
- **Two new MCP tools.** `chimeraforge_suggest` inverts the planning question -- instead of "will this model fit", it ranks what to actually run on a given GPU (from the offline catalog, installed Ollama tags, or the HF Hub). `chimeraforge_compare_api` sizes the cheapest feasible self-host fleet, prices the same traffic through every hosted model in the snapshot, and returns the monthly output-token volume where the two break even.
- **Plan-tool parity with the CLI.** `chimeraforge_plan` now also takes `workload` (queueing variance: steady / chatbot / bursty / agent), `safety_target`, `gpu_price_multiplier`, `allow_offload` and `host_bandwidth_gbps`. A knob the CLI models but the tool cannot pass is invisible to an assistant -- it fails as a missing capability, never as an error -- so a test now walks `run_plan`'s signature and fails if a new one is added without a route through the tool.

### Notes
- API prices are a dated snapshot: `chimeraforge_compare_api` reports the capture date and age in every result and puts STALE in the prose note, not only in a boolean a model may skip over.
- When nothing fits, the comparison returns `comparable: false` with the rejection reason rather than reporting an API win -- with no feasible fleet there is no self-host cost, and "the API is cheaper" would answer a different question.


## [0.24.0] - 2026-08-21

### Added
- **AWQ and GPTQ (W4A16) for vLLM, SGLang and TGI.** These are the 4-bit formats people actually run on the serving backends, and leaving them out meant the planner offered FP16 or FP8 and nothing in between -- while happily suggesting a 4-bit GGUF that those backends do not serve. Effective width is 4.5 bpw (4-bit weights plus per-group scales and zeros at the usual group size), which is the same arithmetic a 4-bit GGUF k-quant lands on, arrived at independently. `--quantization awq` / `--quantize gptq` are emitted in the launch command.

### Notes
- **W4A16 quality is unscreened and says so.** The TR corpus measures GGUF k-quants; a 4-bit GGUF delta is not evidence about AWQ or GPTQ, which use different calibration and make different errors. Reusing the GGUF number would have been the easy move and would have been wrong, so quality resolves through the FP16-baseline path as `estimated` and every W4A16 plan carries an UNSCREENED warning. VRAM stays exact -- it is arithmetic.
- Ollama is not offered W4A16: llama.cpp serves GGUF, not AWQ/GPTQ checkpoints.


## [0.23.0] - 2026-08-21

### Added
- **Partial CPU offload (`--allow-offload`).** "It does not fit" and "it runs" are
  both true at once: llama.cpp and Ollama stream the weights that do not fit from
  host RAM. A planner that only ever says "does not fit" loses the argument against
  a machine visibly running the model. The answer is now priced instead of refused
  -- on an RTX 4060 8GB an 8B goes from 5 fitting configs to 11, the best of them
  running FP16 with **61% of weights offloaded at 9.8 tok/s**.
- `--host-bandwidth-gbps` for the host link, defaulting to the GPU's PCIe figure.
- `Candidate.offload_fraction` / `host_bandwidth_gbps`.

### Notes
- **The derate is modelled, not measured.** Decode reads every weight per token, so
  the offloaded share crosses PCIe instead of VRAM and costs the full bandwidth
  ratio (H100 HBM 3352 GB/s against PCIe 5 at 128 GB/s is ~26x). That is why
  offload runs and why it crawls -- and the warning says the number is derived from
  the ratio rather than benchmarked.
- **Only weights spill.** KV and activations must stay resident, so a config whose
  non-weight footprint alone exceeds VRAM is still rejected, with the reason
  "offload cannot help" rather than being pretended into fitting.
- Off by default; every pre-existing result is unchanged.
- **Separate TTFT and TPOT service-level objectives (`--ttft-slo`, `--tpot-slo`).**
  A single blended p95 hides which half of the experience a config fails, and the
  two failures need opposite fixes: a TTFT miss is prefill-bound (more replicas, a
  shorter prompt, a prefix cache), a TPOT miss is usually a batch that is too
  large. Both are checked *inside* the (replicas x batch) search, so a config that
  wins on p95 by ruining per-token latency is rejected rather than recommended.
- Rejections name which bound: `TTFT 166ms > 100ms SLO (prefill-bound; a bigger
  batch will not help)` instead of a generic latency failure.

### Notes
- **This gates a predicted value, not an attainment percentage.** The planner
  models a point estimate, not a latency distribution, so setting either SLO warns
  that it is not a "99% of requests" guarantee. Real goodput attainment needs a
  distribution this planner does not model.
- Both default to off, so every pre-existing number is unchanged.

- **SGLang backend.** `BACKENDS` was `[ollama, vllm, tgi]`, which describes a
  serving market that has moved on: SGLang is now one of the engines people
  actually run, and TGI is fading. SGLang is offered with continuous batching,
  float + FP8 formats (not GGUF), and a real launch command
  (`python -m sglang.launch_server --model-path ... --tp-size N`).
- `ThroughputModel.has_measured_rows(backend)` -- derived from the loaded corpus,
  not a hardcoded list, so a backend added later is honest by default.

### Notes
- **SGLang ships with NO measured rows and says so.** Its throughput comes from the
  same first-principles path any unmeasured model takes, provenance is never
  `measured`, and every SGLang plan carries a warning stating the estimate is
  *deliberately not borrowed from another backend*. Cloning vLLM's coefficients
  would have made the numbers look confident and been a lie; `measure` replaces the
  estimate with a real one.
- A test pins this on `llama3.2-1b`, where vLLM *has* a measured row and SGLang does
  not, so wiring SGLang to vLLM's lookup would make them converge and fail. A
  companion test pins the opposite: on a model nobody has measured, unmeasured
  backends agreeing is correct, not a bug.


## [0.22.1] - 2026-08-21

### Fixed
- **The MCP server reported the SDK's version as its own.** FastMCP takes no
  `version`, so `serverInfo` came back as `chimeraforge 1.29.0` -- the mcp SDK's
  number, shown to every client as ours. Found by probing the container. Now set
  through the low-level server, guarded so a future SDK change leaves the version
  absent rather than wrong, with a test asserting exactly that: ours or nothing,
  never someone else's.

### Added
- **`Dockerfile` for the MCP server.** Installs the published wheel (so the image
  matches what PyPI actually ships), runs as a non-root user, and fails the build
  if `build_server()` cannot be constructed rather than shipping an image that
  breaks on first use. ~60 MB. Run attached, since MCP here speaks stdio:
  `docker run --rm -i chimeraforge`.
- **`scripts/probe_mcp_stdio.py`** performs a real client handshake (initialize ->
  initialized -> tools/list) against any MCP stdio command and asserts the three
  tools come back. Building proves the image installs; this proves it *serves*.
- **CI builds the image and probes it**, so a broken Dockerfile fails the build
  rather than the user.


## [0.22.0] - 2026-08-19

### Added
- **`chimeraforge validate` -- prediction-vs-measured falsification audit.** The
  trust principle was asserted per number ("this one is `estimated`"); this makes
  the claim *checkable*. It runs a pre-registered config matrix through the
  planner, joins each cell to a measurement (live via `bench`, or from a captured
  file), and reports a per-provenance-class error scorecard with a markdown report
  and full raw JSON.

### Why it is built this way
Every published planner accuracy audit is datacenter-only -- Vidur <9% on
A100/H100, DistServe <2% on 32xA100, Splitwise MAPE <3%. None covers consumer
GPUs, PCIe, or per-quantization behaviour, which is the tier this corpus is fit
on. Three ways such an audit lies, and what stops each:

- **Cherry-picking the matrix after seeing results.** The matrix is
  SHA-256 fingerprinted (order-independent, sensitive to any cell edit) and the
  audit records the hash it ran against, so a matrix edited afterwards no longer
  matches the report citing it.
- **Passing in-corpus lookups off as predictions.** A `measured`-provenance cell is
  not a prediction -- the corpus *is* the answer. Cells split into
  `roofline-estimate` / `parallel-estimate` / `measured-lookup`, the report **leads
  with the estimated path**, and the lookup section is explicitly labeled *not an
  out-of-sample test*.
- **Averaging away the embarrassing cells.** Every cell is retained in the raw JSON
  including skips-with-reasons, and each scorecard row carries its own worst case.

Rows built from fewer than 5 cells are labeled an anecdote rather than quoted as a
rate. Positive error means the planner was optimistic. Scoring is pure and offline,
so a published audit can be re-derived from its own raw output without a GPU.

- `examples/validation-matrix.json` is a runnable pre-registered example.


## [0.21.0] - 2026-08-18

### Added
- **GitHub Action: `.github/actions/plan-comment`.** Posts a capacity plan as a
  sticky pull-request comment, so changing a model or a serving config shows its
  deployment consequences *in review* rather than after deploy -- VRAM per GPU,
  fleet size, throughput, p95, monthly cost, and the duty-cycle-effective cost,
  with alternatives and the self-host-vs-API table folded away in `<details>`.
  Outputs `plan-json` / `fits` / `monthly-cost` / `summary` for jobs that want to
  gate on the numbers instead of reading them.

### Notes
- The rendering lives in a real script (`render.py`), not inline YAML, because the
  edge cases -- nothing fits, `--compare-api` wrapping the payload, warnings that
  must survive into review -- are exactly what needs tests. 28 of them.
- The comment is sticky: found by a hidden marker and edited in place, so a busy PR
  gets one updating comment rather than a wall of them.
- `fail-on-no-fit` defaults to **false**. A plan that does not fit is information,
  not necessarily a broken build.
- Plan warnings are reproduced in the comment, so an estimate is never presented in
  review as a measurement.


## [0.20.0] - 2026-08-18

### Added
- **Duty-cycle-aware effective cost (`plan --duty-cycle`).** `cost_per_1m_tok`
  divides the bill by what a *saturated* fleet could serve, which flatters it
  twice: the planner sizes capacity at or above demand, so you pay for headroom,
  and a rented GPU bills for wall-clock, so a fleet sized for a peak it sees part
  of the day still costs the whole month.
  `cost_per_1m_tok_effective` divides the same bill by the tokens the workload
  actually asks for. On an 8B at 2 req/s the at-capacity figure is $0.9152/1M --
  the effective figure is **$2.71/1M at full duty and $9.04/1M at 30%**.
- **`--gpu-price-multiplier`** scales the GPU $/hr for spot, reserved or
  negotiated rates. Price is not physics: throughput, latency and VRAM are
  untouched, but what fits under a budget changes.
- `Candidate` carries `duty_cycle`, `gpu_price_multiplier`,
  `cost_per_1m_tok_effective` and `tokens_served_month`; `duty_cycle` is also an
  argument on the MCP `chimeraforge_plan` tool.
- **The self-host-vs-API comparison now scales with duty cycle too.** An idle API
  costs nothing while idle GPUs keep billing, so a low duty cycle correctly moves
  the comparison toward the API rather than flattering self-hosting.

### Notes
- Both dials default to no-op (`1.0`), so every pre-0.20.0 number is unchanged.
- The spot discount is **your input, not a bundled constant** -- it is provider-,
  region- and instance-specific, and the warning notes that spot capacity can be
  reclaimed mid-request.
- `SECONDS_PER_MONTH` moved to `constants.py` so a "month" means the same thing in
  the cost model and the API break-even.


## [0.19.0] - 2026-08-18

### Added
- **Prefix-cache-aware prefill (`plan --prefix-cache-hit-rate`).** vLLM, TGI and
  SGLang skip prefill for a prompt span already resident in cache. Chatbot and
  agent traffic -- the workload presets this planner already ships -- reuse a long
  system prompt and conversation head on nearly every turn, so charging the full
  prompt on every request overstates TTFT and the tail with it. On an 8B at a
  4,096-token prompt, a 90% hit rate takes TTFT from **166.3ms to 16.6ms** and p95
  from **1,355ms to 349ms**. Exposed as `Candidate.prefix_cache_hit_rate` and
  `prefill_tokens_effective`, and as an argument on the MCP `chimeraforge_plan`
  tool.

### Notes
- **Defaults to 0 and is never inferred.** The hit rate is a property of the
  traffic, not of the model, so there is nothing in a spec to read it from -- it
  stays an explicit scenario input, like the reasoning-token ratio.
- **The KV memory a shared prefix saves is deliberately not deducted.** A real
  server does reclaim it, but under-sizing KV is the direction that claims a fit
  that is not there, so the conservative number stands and the warning says so.
- A fully cached prompt still prefills one token: the newest token runs the stack
  either way, so TTFT never reaches zero.


## [0.18.0] - 2026-08-18

### Fixed
- **KV-cache is now sized on the model's actual attention shape.** The planner
  assumed MHA/GQA everywhere -- `2 (K+V) * kv_heads * d_head` per token per layer.
  Two families break that, and 0.14.0's MoE support made the first one reachable:
  - **MLA** (DeepSeek-V2/V3) caches a single compressed latent plus a decoupled
    RoPE key, not per-head K and V. Applying the GQA formula to DeepSeek-V3
    overstated its cache by **57x** -- 30.5 GB against the real 0.54 GB at 8k
    context -- which rejected fleets that would have fit. On an 8x H200 group the
    concurrency ceiling goes from **20 to 503** sequences once the shape is right.
  - **Sliding-window attention** (Gemma-3 and similar) caps local layers at the
    window, so the cache stops growing past it rather than scaling with context.

### Added
- `ModelSpec` carries `kv_lora_rank` / `qk_rope_head_dim` (MLA) and
  `sliding_window` / `swa_global_every` (SWA), with `is_mla` and
  `kv_elems_per_token_per_layer`. The resolver reads them from HF `config.json`,
  including deriving the window pattern from a `layer_types` list.
- Plans on these models warn which cache shape drove the estimate.

### Notes
- **A sliding window is only applied when the layer pattern is known too.** Mistral
  declares a window but no pattern, so it is sized at full context. Applying a
  window we cannot place would *shrink* the estimate, and under-sizing KV is the
  direction that turns "it fits" into an OOM -- so the conservative answer wins.
- Dense MHA/GQA models are unchanged on every path, including bare arch dicts
  passed by library callers and specs cached before 0.18.0.


## [0.17.0] - 2026-08-18

### Added
- **Self-host vs hosted-API break-even (`plan --compare-api`).** Answers the
  question that comes before "which GPU": is self-hosting worth it at all, at this
  volume? Self-hosting is a fixed monthly bill for fixed capacity; an API is a
  per-token charge that scales. The two cross at one volume, and the whole decision
  turns on which side of it you are on. Prices the planned workload against every
  hosted option and reports the crossing point in monthly output tokens.
- **`scripts/build_cost_data.py`** regenerates and validates the bundled price
  snapshot: schema, types, ISO dates, an https source per provider, and sanity
  bounds that fail the build rather than shipping a likely parse error.

### Notes
- **Prices are a dated snapshot, not a live quote.** No vendor publishes a pricing
  API, so `data/api_pricing.json` carries `captured_at` plus a source URL per
  provider, and anything past 90 days is reported as **stale** rather than quoted
  as current. A snapshot with no date at all is treated as stale, never as fresh.
- **A frontier API is not a like-for-like comparison for an 8B you host.** Every
  entry is labeled `open` (same class of open-weights model, hosted) or `frontier`
  (different quality tier), so the number cannot be read as apples-to-apples.
- Prices captured 2026-08-18 from the vendors' own published pages: Together AI
  (hosted open models) and Anthropic.


## [0.16.0] - 2026-08-18

### Fixed
- **Non-ASCII characters removed from source** (4 em-dashes, 2 arrows, 1 delta).
  Three sat in `run_demo.py`'s *rendered report output*, not just comments. They
  render as mojibake on a cp1252 console and twice crashed a plain `print()` of
  tool output during development.

### Added
- **Hidden reasoning-token accounting (`plan --reasoning-tokens N`).** A reasoning
  model (R1, o-series, QwQ) emits thinking tokens the caller never sees, but the GPU
  decodes every one and the KV cache holds them for the life of the request.
  Planning on visible output alone under-counts decode by the reasoning ratio. With
  1000 hidden tokens on an 8B at 2 req/s, decode goes 128 -> 1128 tokens/request and
  p95 goes **363ms -> 6128ms** -- the difference between a plan that meets its SLO
  and one that does not. Exposed on `Candidate` as `reasoning_tokens` and
  `decode_tokens_per_req`, and as a `reasoning_tokens` argument on the MCP
  `chimeraforge_plan` tool.
- A **peak-sequence warning**: when `prompt + visible + reasoning` exceeds
  `--context-length`, the KV cache was sized for a window the request cannot finish
  inside.
- **Convention guards** (`tests/test_repo_conventions.py`): a per-file ASCII-only
  check parametrized over every `src/` and `tests/` Python file, and a version-sync
  check tying `server.json` to `pyproject.toml` and `__version__`, plus the
  registry's 100-char description limit and the README `mcp-name` token. Both rules
  had already been broken more than once, invisibly.
- **The MCP Registry publish is now part of the release workflow.** A new
  `mcp-registry` job runs after the PyPI upload, authenticates with GitHub OIDC (no
  stored secret), waits for the release to be indexed on PyPI -- the registry proves
  ownership by reading the `mcp-name` token out of the published description -- and
  then publishes. It refuses to run if `server.json` disagrees with the tag, which
  is exactly how 0.12.3 shipped with the registry still pointing at 0.12.2.

### Notes
- The reasoning ratio **defaults to 0 and is never inferred**. It is a property of
  the prompt and the workload, not of the weights, so it stays an explicit scenario
  input -- measure it rather than let the planner invent one.

## [0.15.0] - 2026-08-14

### Fixed
- **Backends are only offered formats they actually serve.** The planner enumerated
  every GGUF quant against every backend, so it would recommend "vLLM + Q2_K" -- a
  config vLLM does not serve in the normal path -- and price it with a throughput
  multiplier measured on llama.cpp. The bundled corpus only ever measured **FP16**
  on vLLM/TGI, so those GGUF cells were an extrapolation stacked on a format
  mismatch. GGUF is now Ollama-only; vLLM/TGI take float and FP8. Rejected
  combinations are recorded in the trace, so a 0-result says why.

### Added
- **FP8 quantization** for vLLM/TGI, the format people actually run there. VRAM is
  exact (8 bits/param, no block-scale overhead). Throughput reuses the existing
  nearest-bpw fallback, which lands on the measured 8-bit multiplier rather than
  inventing an FP8 number -- the conservative end of the published 1.3x-2.3x range,
  since the compute-bound gains at high batch are not modelled.
- **`GPUSpec.fp8_supported`.** FP8 is only offered where FP8 tensor cores exist
  (Ada, Hopper, Blackwell, CDNA3). On Ampere (RTX 30, A100) and Turing (T4) it is
  rejected with a stated reason rather than silently costed.
- `plan --launch` emits `--quantization fp8` (vLLM) / `--quantize fp8` (TGI), and
  drops the "serve a native-equivalent checkpoint" note, which no longer applies.

### Notes
- **FP8 quality is labeled `estimated`, never `measured`.** It is absent from the
  TR quality corpus, so it resolves through the FP16-baseline path with no
  fabricated delta added to the measured data.
- FP8 is likewise outside the TR134/TR142 safety corpus. Under `--safety-target`
  it therefore passes as *unscreened* and carries the existing "safety not
  screened" warning -- the documented lookup-only policy (no extrapolation). A
  test previously asserted that every candidate under a safety target had a known
  refusal rate; that held only because every surviving quant happened to be one
  the GGUF-only corpus covered. It now asserts the actual contract: known-unsafe
  cells are rejected, unscreened cells pass warned.
- Ollama + GGUF planning (the reference path) is unchanged.

## [0.14.0] - 2026-08-14

### Fixed
- **Mixture-of-Experts models are no longer planned as if they were dense.** An MoE
  model keeps every expert resident in VRAM but a decoded token only reads the
  experts it routed to. The planner previously used the *total* parameter count
  everywhere, so it under-predicted MoE throughput by the active/total ratio --
  **3.6x on Mixtral-8x7B, ~18x on DeepSeek-V3** -- and inflated TTFT by the same
  factor. Those are the flagship 2026 models, and the wrong answer looked
  confident. Now VRAM and the concurrency cap size on **total** params (unchanged),
  while the decode roofline, the decode compute ceiling, and prefill/TTFT use
  **active** params.

### Added
- `ModelSpec` carries MoE geometry (`num_experts`, `experts_per_token`,
  `moe_intermediate_size`, `n_dense_layers`) with `is_moe` and `active_params_b`.
  Active params are derived first-principles by subtracting the routed experts a
  token does *not* select -- which avoids having to model attention, embeddings,
  shared experts, or norms at all. Verified against published counts:
  **Mixtral-8x7B 12.9B (exact), DeepSeek-V3 37.5B vs 37B, Qwen3-30B-A3B 3.32B vs 3.3B.**
- The resolver reads MoE fields from HF `config.json` across family spellings
  (Mixtral `num_local_experts`, DeepSeek `n_routed_experts` + `first_k_dense_replace`,
  Qwen `num_experts`).
- `Candidate.active_params_b` exposes the split, and an MoE plan warns which count
  drove which prediction.

### Notes
- When the expert geometry is incomplete, `active_params_b` falls back to the
  **total** count. An under-informed guess would *inflate* predicted throughput,
  so the conservative dense answer is the honest one.
- Expert parallelism and routing load-imbalance are still not modelled (the
  imbalance ratio is workload-dependent and would have to be measured, not
  assumed) -- the MoE warning says so.
- Dense models are byte-identical to 0.13.0: `active == total` on every path.

## [0.13.0] - 2026-08-09

### Added
- **Launch-command export (`plan --launch`) — the plan now tells you how to run it.**
  Emits a copy-paste `vllm serve` / `ollama run` / TGI `docker run` command for the
  recommended config, with the flags *derived from the plan itself*: context length
  (`--max-model-len` / `--max-total-tokens` / `num_ctx`), tensor-parallel degree
  (`--tensor-parallel-size` / `--num-shard`), pipeline-parallel degree, concurrent
  batch (`--max-num-seqs` / `--max-concurrent-requests` / `OLLAMA_NUM_PARALLEL`), and
  KV-cache dtype. These are precisely the values that are error-prone to hand-compute
  from a plan, and they are the last gap between "here's the config" and a running
  server. New `planner/launch.py` (`build_launch_command`, `LaunchCommand`).
- **The MCP `chimeraforge_plan` tool returns the same command** in a new `launch`
  field, so an assistant answering "what GPU do I need" can also answer the
  question that always follows it without inventing flags.

### Changed
- `plan --json --launch` emits one document, `{"candidates": [...], "launch": {...}}`.
  Without `--launch`, `--json` still emits the bare candidate array exactly as before,
  so the 0.12.3 JSON contract is unchanged for every existing consumer.

### Notes
- The exporter refuses to fake what it cannot derive, matching the planner's
  provenance principle: a model whose source doesn't match the backend's expected
  identifier format (an Ollama tag handed to `vllm serve`) yields a `<placeholder>`
  plus an explaining note rather than a plausible-but-wrong id; a GGUF quant level
  (`Q4_K_M`) becomes a note to serve the native-equivalent checkpoint rather than a
  fabricated `--quantization Q4_K_M` flag; `--gpu-memory-utilization` is labeled a
  starting point; and where a backend's smallest KV dtype (fp8) is coarser than the
  quantization the plan modeled (q4), the note says real VRAM will exceed the plan.

## [0.12.3] - 2026-08-09

Four correctness defects, found by probing the published package the way an outside
user meets it rather than by reading the source. All four produced a confident answer
that was wrong, or no answer with no reason — the two outcomes a planner can least
afford, because neither looks like a failure. Full findings and reproductions in
[`docs/ax-audit-2026-08.md`](docs/ax-audit-2026-08.md).

### Fixed
- **`--model-size` substituted silently instead of refusing.** `find_models_for_size`
  fell back to the single *nearest* registry model when nothing matched within 50%,
  and to *every* model when the string would not parse. The registry tops out at
  8.03B, so every request above roughly 12B took the first path: `--model-size 70b`
  answered with llama3.1-8b's 8.03B parameters and 4.55 GB of VRAM, and
  `--model-size banana` planned happily across 129 rows. Nothing in the output said
  the request had been changed. Both paths now raise `ResolverError`, and the message
  names the registry's span and both escape hatches — `--model` for a real HF/Ollama
  resolve, `--params-b` to override — because a refusal that does not say what would
  work is a dead end.
- **`--json` was not a contract.** Human-readable text went to the same stream as the
  payload, so output stopped being JSON while the exit code still said success. Fixed
  in four places: the unknown-hardware warning, `catalog`'s empty-state message, and
  `--list-hardware` / `--list-models`, which ignored `--json` entirely and printed
  box-drawing tables. `--list-hardware` mattered most — it is the only way to discover
  a valid `--hardware` value, so it is the listing an automated caller most needs to
  read. Diagnostics now go to a stderr console.
- **An empty result did not explain itself.** `summarize_trace()` already existed and
  already said why nothing fit; it was gated behind `not output_json`, so the
  explanation was withheld from exactly the caller that cannot infer it. The commonest
  case is the default `--budget` of 100 USD/month excluding every datacenter GPU — an
  H100 at the DB's own $2.50/hr is about $1,825/month. It now prints to stderr under
  `--json`, so stdout stays exactly one array and `| jq` keeps working:
  `blocked at budget gate - ollama: $1800/mo (N=1) > $100`.
- **An unknown `--hardware` was substituted, not refused.** It warned and then planned
  on RTX 4080 12GB specs, returning a full result set about a GPU nobody asked for —
  and because the warning went to stdout, a caller stripping non-JSON lines to recover
  the payload got those rows with nothing recording the substitution. Now refused,
  with the known GPUs listed.

### Changed
- `[project.urls]` `Homepage` now points at <https://chimeraforge.vercel.app> rather
  than the repository, and `Changelog` and `Issues` were added. The site and the
  package did not link to each other in either direction, so a reader arriving from
  `pip install` had no way to find it.
- Five tests were rewritten because they specified the defect: one asserted that
  `"100b"` returns `llama3.1-8b`, another that `"abc"` returns every model. The
  instinct behind them — "should not crash" — is right, and a clean refusal satisfies
  it while a wrong number does not. The replacements assert the refusal, that the
  message names the way forward, and that the size classes the registry *does* hold
  still resolve.

## [0.12.2] - 2026-08-08

### Fixed
- **MCP server launch via `uvx` now installs the `mcp` extra.** The documented
  `uvx chimeraforge mcp` created an ephemeral environment with only the core
  dependencies, so `build_server()`'s `from mcp.server.fastmcp import FastMCP`
  raised and the server never started. The README client configs (Claude Code,
  Claude Desktop / Cursor) and the MCP registry manifest now use
  `uvx --from "chimeraforge[mcp]" chimeraforge mcp` — expressed in `server.json`
  via `runtimeArguments` so registry clients compose the identical command.

## [0.12.1] - 2026-08-08

### Added
- **MCP registry manifest (`server.json`) and `mcp-name` ownership token** in the
  README, so the package can be claimed and listed on
  registry.modelcontextprotocol.io under `io.github.Sahil170595/chimeraforge`.

### Changed
- **README rewritten as the PyPI/GitHub shopfront** for the current 0.12.0 feature
  set: leads with the provenance/trust principle (`measured`/`estimated`/`unknown`
  on every number), documents all 11 commands including `mcp`, tensor/pipeline
  parallelism, KV-cache quantization, and energy modeling, and adds zero-install
  `uvx`/`pipx run` quickstarts plus an MCP setup section (Claude Code one-liner and
  a Claude Desktop / Cursor config snippet).
- **PyPI metadata refreshed**: `keywords` expanded (vram, gpu-sizing, quantization,
  ollama, vllm, llama-cpp, gguf, capacity-planning, mcp), classifier moved from
  `Development Status :: 3 - Alpha` to `4 - Beta`, and a `Documentation` URL added
  under `[project.urls]`. No functional/code changes.

## [0.12.0] - 2026-08-07

### Added
- **MCP server — ChimeraForge is now callable by Claude / GPT / Cursor and any MCP
  client.** `chimeraforge mcp` runs a stdio server (new `mcp` extra:
  `pip install "chimeraforge[mcp]"`) exposing three tools: `chimeraforge_plan`
  (the full gate search), `chimeraforge_resolve_model` (grounds a model's real
  params/architecture), and `chimeraforge_list_hardware`. GPU-sizing is exactly
  where assistants fail — stale training-cutoff prices/specs plus error-prone KV/
  batching arithmetic — so the tools let an assistant answer "what GPU do I need /
  will it fit / how much will it cost" from measured data instead of guessing.
  Every result surfaces the `provenance` (measured/estimated/unknown) contract, and
  the tool descriptions tell the model to prefer the tool over its own knowledge.
- **Shared planning core (`planner/service.py: run_plan`).** The CLI and the MCP
  server now go through one presentation-free orchestration path (load → resolve →
  gate search → pareto) instead of duplicating logic — the MCP tools call it
  in-process, not by shelling out to the CLI.

### Fixed
- **`plan --json` now emits `{"error": ...}` on failure paths** instead of
  Rich-styled text, so an automated consumer parsing stdout gets valid JSON on
  errors too (previously validation/resolution errors printed markup regardless of
  `--json`, breaking `json.loads`).

## [0.11.0] - 2026-08-07

### Added
- **Pipeline parallelism.** New `plan --pipeline-parallel {N|auto}` (alias `--pp`):
  split a model's *layers* into N sequential stages across N GPUs — another way to
  fit a model too big for one GPU. Complements 0.10.0's tensor parallelism; the two
  suit different interconnects.
  - **VRAM**: weights and each stage's KV shard 1/N with **no attention-head cap**
    (unlike TP), so PP scales past `n_kv_heads` for GQA models.
  - **Throughput** (`ThroughputModel.pp_decode_tps`): N stages give ~N× aggregate
    HBM bandwidth, and PP's only comms is a **small point-to-point activation pass**
    (no all-reduce) — so PP barely degrades on slow PCIe where TP collapses (per
    vLLM's own guidance). The cost is the **GPipe pipeline bubble**: a decode step
    traverses every stage, so PP needs enough in-flight sequences to stay full
    (efficiency `batch/(batch+pp-1)`) — near-ideal at high batch, poor at batch 1.
    Warns when under-filled. First-principles **estimate** (bubble modelled, not
    measured).
  - `auto` picks the smallest PP degree that *fits* (fewest GPUs); a high-throughput
    load may need a higher explicit degree. `Candidate` gains `pipeline_parallel`.
  - **TP and PP cannot be combined yet** (MVP) — setting both above 1 errors cleanly.
  - `pp=1` (the default) reproduces the pre-0.11.0 single-GPU results exactly.

## [0.10.0] - 2026-08-07

### Added
- **Multi-GPU tensor parallelism.** New `plan --tensor-parallel {N|auto}` (alias
  `--tp`): the planner can now size a model that does not fit one GPU by splitting
  it across `N` GPUs. Weights shard 1/N and KV shards across attention heads
  (`VRAMModel.predict`/`max_concurrent_seqs` gained a `tp` arg), so e.g. a 70B FP16
  fits on 4x H100 or 2x B200. `auto` picks the smallest TP degree that fits.
  - **Comms-modelled throughput** (`ThroughputModel.tp_decode_tps`): a TP group of
    `N` GPUs gets ~N x aggregate HBM bandwidth, minus Megatron all-reduce overhead
    (2 per layer, ring `2(N-1)/N` bytes, FP16 activations) scaled by the GPU's
    interconnect bandwidth. So TP is near-ideal on NVLink at low batch but erodes on
    PCIe or at high batch, matching the literature (Pope et al. 2022; vLLM docs).
    Throughput is a first-principles **estimate** (comms modelled, not measured) and
    is flagged as such; PCIe interconnects and crossing the NVLink domain also warn.
  - `GPUSpec` gains `interconnect_gbps` for all 22 GPUs (NVLink 3/4/5, AMD Infinity
    Fabric, or PCIe 4/5). Cost and energy scale with the full fleet (`N replicas x
    TP GPUs`); `Candidate` carries `tensor_parallel` and `gpus_total`.
  - `tp=1` (the default) reproduces the pre-0.10.0 single-GPU results exactly.

## [0.9.0] - 2026-08-05

### Added
- **KV-cache quantization modeling.** New `plan --kv-quant {fp16,q8,q4}`. Backends
  can quantize the KV cache independently of the weights (llama.cpp
  `--cache-type-k`, vLLM fp8 KV); the planner now models it (q8 = 1 byte, q4 = 0.5
  byte per element vs FP16's 2). A quantized cache **lowers VRAM and raises the
  KV-bound concurrency cap** — largest at long context, where KV dominates.
  `VRAMModel.predict` / `kv_cache_gb` / `max_concurrent_seqs` take a `kv_bytes`
  argument (default FP16, so existing results are byte-identical).
  - Only VRAM/concurrency are modelled; KV-quant's (small) **quality impact is NOT
    screened** (no bundled measurements) — `plan` warns when it is enabled and
    never reports a fabricated quality delta.

### Changed
- **Dependency ranges refreshed** against verified-passing versions (the full
  suite runs green on all of these): runtime `rich` cap widened `<14.0` → `<16.0`
  (the old cap force-downgraded rich in users' environments); dev tools
  `pytest` → `<10.0`, `pytest-cov` → `<8.0`, `pytest-asyncio` → `<2.0`.

## [0.8.0] - 2026-08-05

### Added
- **Energy & power cost modeling.** `GPUSpec` gains `tdp_watts` (board power, from
  vendor datasheets) for all 22 GPUs, and `plan` now reports, per configuration:
  monthly electricity cost, a `$/1M-tok (+energy)` figure, and throughput
  efficiency (**tok/s per watt**). New `--electricity-rate` flag ($/kWh, default
  the US commercial average). Power draw is modelled as `tdp_watts x 0.85`
  (sustained decode rarely holds full TDP; the factor is the named constant
  `POWER_UTILISATION`).
  - Energy is reported as a **separate** line, deliberately NOT folded into the
    hardware cost or the budget gate: a cloud `$/hr` rate already bundles power
    (folding it in would double-count), while an amortised consumer-card cost
    does not -- so the energy figure is most meaningful for self-hosted hardware.
  - `perf_per_watt` and the per-token energy cost are invariant in replica count
    (both the aggregate throughput and the total power scale with N).

## [0.7.0] - 2026-08-05

### Added
- **7 current-generation GPUs in `GPU_DB` (15 -> 22).** Consumer Blackwell
  (RTX 5070 / 5070 Ti / 5080 / 5090, GDDR7), datacenter NVIDIA (H200 141 GB,
  B200 180 GB), and the first AMD entry (Instinct MI300X 192 GB). Every VRAM /
  bandwidth / `fp16_tflops` figure is sourced from vendor datasheets on the
  table's existing basis (dense FP16 Tensor Core, FP32-accumulate, non-sparse):
  consumer Blackwell = 2x FP32 shader (= the whitepaper's FP32-accumulate row);
  H200 shares H100's GH100 compute (989); B200 dense = datasheet 4500-with-
  sparsity / 2; MI300X 1307 from AMD's dense-FP16 figure. This also sharpens the
  roofline throughput path for *any* off-registry model on the new hardware.
- **Newer model families recognised** in identifier parsing: `qwen3`,
  `llama3.3`, `gemma3`, `smollm` (joining `qwen2.5` / `llama3.x` / `phi` /
  `gemma2` / `mistral`), so tags like `qwen3:8b` parse their family correctly
  when resolved via a live backend. No bundled measurements exist for these, so
  they resolve to **estimated / roofline** numbers with honest provenance -- never
  a "measured" masquerade (a regression test locks this in).
- **9 newer models in the offline catalog seed** (`model_catalog.json`, 10 -> 19):
  Qwen3 (0.6B-14B), Phi-4 + Phi-4-mini, SmolLM3-3B, Mistral-7B-Instruct-v0.3.
  All verified publicly ungated so `catalog build` resolves them to real specs
  tokenless; gated repos (Gemma, Llama) are deliberately excluded.

## [0.6.2] - 2026-07-25

### Fixed
- **`quality_tier` and the quality float now agree for `llama3.1-8b` FP16**
  (#4 follow-up). 0.6.1 fixed `quality_tier` but left `estimate()` / `predict()`
  on the old baseline chain, so the FP16 config reported quality `0.5` with
  provenance `unknown` -- ranking the *highest-precision* option below `Q2_K`
  (`0.59`) -- while its tier said `negligible`. All three methods now share one
  `_fp16_baseline` resolver (measured FP16 -> the model's highest measured quant
  -> family mean), so quality, provenance, and tier can never diverge. FP16 now
  reports `0.635` (estimated), consistent with its `negligible` tier.

## [0.6.1] - 2026-07-04

### Fixed
- **Clean errors for missing extras.** `bench` / `measure` / `safety` (and
  `plan --measure`) now fail with a clear `install "chimeraforge[bench|safety]"`
  message instead of a raw `ModuleNotFoundError` traceback when the serving
  backends' `httpx` dependency is absent (the backends import it at module load).
- Install-hint error messages no longer have their `[extra]` swallowed by Rich
  markup (the resolver hint rendered as `pip install chimeraforge`, dropping
  `[resolve]`); dynamic error text is now escaped.
- **`quality_tier` no longer returns `unknown` for `llama3.1-8b`** (#4). Its FP16
  was never measured (16 GB exceeds the RTX 4080), so TR125 used Q8_0 as the
  baseline; `quality_tier` now mirrors that, anchoring to the model's
  highest-precision measured quant when no FP16 baseline exists.
- **Quick-start install fixed** (#5): `docs/quick_start.md` used
  `pip install -r requirements.txt` (a comment-only stub that installs nothing),
  so the agent demo failed with `ModuleNotFoundError: httpx`. It now installs
  `-e ".[bench]"` (which provides `httpx`) and points the clone at the real repo.

### Changed
- **`httpx` is now a core dependency**, so the network-facing commands
  (model-agnostic `plan --model`, `suggest`, `catalog`, `measure`, `safety`,
  `bench`) work on a plain `pip install chimeraforge` instead of erroring until an
  extra is added. The `[resolve]`/`[safety]` extras are kept as no-op back-compat
  aliases. Thanks @sumaiya1303 (#6).
- **Corrected optional-dependency groups.** `[bench]` dropped `psutil`, `pyyaml`,
  and `structlog` (none are imported by the shipped `chimeraforge` package) and
  added `pynvml` (used for GPU environment metadata, previously undeclared, so
  `[bench]` silently lacked it). `psutil` and `structlog` moved to `[dev]` (they
  are test-only, for the `banterhearts` monitoring subsystem the suite exercises);
  `pyyaml` removed entirely (unused). `[refit]` added `platformdirs` (used by its
  output-path resolution). `[all]` no longer pulls the `dev` tools (pytest/ruff)
  onto end users; CI installs `.[all,dev]`.

## [0.6.0] - 2026-06-25

State-of-the-art serving model: the planner now reflects how LLM inference
actually behaves (per the literature - PagedAttention, continuous batching,
prefill/decode disaggregation, goodput/Pareto), not replicas-of-single-stream.

### Added
- **Continuous-batching throughput.** vLLM/TGI are modelled with per-GPU
  continuous batching instead of single-stream replicas: aggregate decode
  throughput rises with batch size up to the KV-cache cap, anchored to the
  measured/roofline single-stream rate so it stays quant-correct. One GPU can now
  replace several Ollama replicas (e.g. a 7B at 3 req/s on a 4090: Ollama 5 GPUs
  vs vLLM 1 GPU at batch 8). `Candidate.effective_batch`.
- **Prefill/decode split.** Separate **TTFT** (prefill, compute-bound, from GPU
  FP16 TFLOPS) and **TPOT** (decode, bandwidth-bound); end-to-end p95 now includes
  prefill. `GPUSpec.fp16_tflops` for all GPUs; `plan --prompt-tokens`.
- **KV-cache-bound max concurrency** per GPU (`max_concurrent_seqs`), the real
  concurrency limiter for batched backends.
- **Pareto frontier** (`plan --pareto`): the non-dominated cost/latency/quality
  trade-off menu (tags cheapest / fastest / best-quality), not a single pick.
- **Variance-aware queueing** (`plan --workload steady|chatbot|bursty|agent`):
  two-moment wait so high-variance/agent workloads inflate the tail and carry a
  "validate with a load test" warning - analytical queueing otherwise silently
  approves fleets that miss SLOs for heavy-tailed traffic.
- Numerical accuracy tests pinning throughput, the roofline calibration anchor,
  the VRAM formula, TTFT, and batching invariants to ground truth (falsifiability).

### Changed
- **Throughput scales linearly across GPU replicas** (replaced the Amdahl
  serial-fraction model, which capped total throughput at ~1.8x regardless of
  instance count and rejected models >=7B). Per-GPU batching is modelled
  separately (above).
- **`cost_per_1m_tok` no longer understated by the instance count** (uses N-GPU
  cost with N-GPU throughput; $/token is invariant in replica count).
- Broader quant support (legacy + i-quants: `Q4_0`, `Q5_1`, `IQ4_XS`, ...) with
  effective bits-per-weight, so a model's native quant is costed correctly.
- Docs realigned to the planner product (research guides moved to an archive
  section); ASCII-only source.

### Fixed
- **Activation memory is now O(context), not O(context^2).** The quadratic term
  diverged unphysically at long context (~130 GB at 32k for a 3B model), which
  spuriously failed the VRAM gate and zeroed `max_concurrent_seqs` (killing
  batching) at >=8k context. Flash/paged attention never materialises the
  attention matrix, so it scales linearly; coefficient re-pinned to preserve the
  calibrated 2k value. (Found by a blind code audit.)
- **`--json` is now valid when piped** for `bench`, `refit`, `compare`, and
  `report` (added `highlight=False, soft_wrap=True`, matching the other six
  commands). Rich previously reflowed long string values at width 79 and produced
  invalid JSON for `... --json | jq`.
- **`refit --validate` is a real gate**: validation runs *before* the write, so
  invalid coefficients are no longer persisted ahead of the failing exit.
- **Quality tier is family-aware** for off-registry models (consistent with the
  reported quality), so the "concerning drop" advisory can fire instead of the
  tier silently collapsing to `unknown`.
- **Per-key confidence weighting in `refit`**: each entry is blended by its own
  successful-run count, not the global run total (which over-trusted
  lightly-measured configs in a multi-config refit).
- Measured-corpus staleness warning: `plan`/`suggest` now warn (instead of
  silently shadowing) when the cached corpus predates the installed version.
- Robust error handling: `measure` surfaces an unknown `--backend` cleanly;
  backend `check_model` handles timeouts/HTTP errors (not just connect); the
  resolver/discovery raise `ResolverError` (not a raw traceback) on a non-JSON
  200 response; a degenerate `...0b` identifier no longer raises ZeroDivisionError.
- `bench --context ... --quant Q` no longer drops the quant label; non-Ollama
  context sweeps warn that the per-request context override was not applied.
- Roofline throughput is bandwidth-correct above FP16 (e.g. FP32 ~ 0.5x FP16);
  Ollama `F16`/`F32` native-quant strings are normalised to `FP16`/`FP32`.
- `eval --fp16-baseline` exposes tier classification (previously always
  `unknown` from the CLI). Build floor corrected to `setuptools>=77` (PEP 639).

### Notes
- Per-backend MFU/MBU *calibration* is deferred: the `measure` loop already
  supersedes the roofline estimate with real measurements for any benchmarked
  model, which is stronger than tuning a global constant.
- Known minor limitations (low impact, deferred): VRAM mixes decimal-GB weight
  with binary-GiB KV (~7.4%, conservative); ambiguous partial GPU names (e.g.
  "RTX 4080") resolve to the first DB match by VRAM; a genuine 0.0 BERTScore is
  treated as "unavailable".

## [0.5.0] - 2026-06-24

### Added
- **Model-agnostic planning.** `plan --model <id>` accepts any model identifier —
  a registry name, an Ollama tag (`ollama:NAME` / colon tags), or a Hugging Face
  repo (`org/name`) — and resolves real parameters + attention geometry instead
  of being limited to the bundled registry. Sources (priority order): manual
  overrides (`--params-b/--n-layers/--n-kv-heads/--d-head`), registry, on-disk
  spec cache, Ollama `/api/show`, HF `config.json` + `safetensors` param count,
  then offline family/size approximation (`planner.resolver`).
- **`suggest`** — discover and rank deployable models from a live Ollama
  (`/api/tags`), the HF Hub (top text-generation), and/or the local catalog,
  through the same gate search (`planner.discovery`).
- **`catalog`** — build a persisted spec catalog from a curated seed
  (`catalog --build`) so `suggest --source catalog` ranks models fully offline.
- **`measure`** / **`plan --measure`** — benchmark a live model (real N=1
  throughput, service time, and concurrency scaling → serial fraction) and fold
  it into a local `fitted_models.json` via the `refit` loop, so plans run on
  measured numbers (provenance: `measured`) rather than estimates.
- **Per-prediction provenance** (`measured` / `estimated` / `unknown`) on every
  candidate, surfaced in output (`~` markers) and as warnings.
- **Rejection diagnostics** — `plan` reports the binding gate ("Why nothing fit")
  on an empty result.
- Roofline throughput estimate for off-registry models (memory-bandwidth bound).
- Broader quant support: legacy and i-quants (`Q4_0`, `Q5_1`, `IQ4_XS`, …) are
  recognised with effective bits-per-weight, so a model's native quant is costed
  correctly instead of silently defaulting to FP16.
- `resolve` extra (`httpx`) for network metadata resolution.

### Fixed
- **Throughput scaling across instances is now linear.** `n_agents` counts
  independent GPU replicas (VRAM and cost are per-GPU), so total throughput scales
  linearly; the previous Amdahl serial-fraction model wrongly capped it at ~1.8×
  regardless of instance count, rejecting essentially every model ≥7B. (Per-GPU
  batching throughput is intentionally future work.)
- **`cost_per_1m_tok` no longer understated by the instance count** — it now uses
  the N-GPU cost to match the N-GPU throughput, so adding identical replicas
  leaves $/token unchanged (was N× too low).

### Changed
- `plan` / `suggest` prefer a measured corpus
  (`~/.cache/chimeraforge/fitted_models.json`) over bundled coefficients when present.

## [0.4.1] - 2026-06-22

### Added
- CI matrix now covers Python 3.13 and 3.14 (was 3.10–3.12); added the 3.14
  classifier.

### Fixed
- `safety` and `eval` `--json` emit plain JSON (Rich syntax-highlighting disabled
  via `highlight=False`), so `--json | jq` is clean and parsing is robust when
  colour is forced (e.g. on CI).
- Hardened the `safety --help` test to strip ANSI before matching option names —
  the v0.4.0 CI failure (Rich colourises `--help`, so `--prompts` was not a
  literal substring of the raw output).

## [0.4.0] - 2026-06-19

### Added
- `chimeraforge safety` — live refusal screen. Runs user-provided probe prompts
  against a running model, classifies refusals (rule-based, the TR134 regex
  baseline), and reports the measured refusal rate against the bundled gate data
  (expected, drift, RTSI tier); exits 1 below `--safety-target`. Behind the
  `chimeraforge[safety]` extra. Ollama backend (vLLM/TGI not yet); no attack
  corpus is bundled — bring your own benchmark.
- `Backend.generate_text()` returning response text (used by the safety screen).
- Model-identity resolution (`planner.identity`): maps Ollama tags / HF paths to
  registry models by architecture-family + parameter count (not exact name), so
  `safety`'s bundled-data comparison works against live backend model tags.

## [0.3.0] - 2026-06-16

### Added
- Planner safety gate (Gate 5): `plan --safety-target` rejects configs whose
  refusal rate (TR134/TR142) falls below the bar. Opt-in; off by default.
- `SafetyModel` exposing per-(model, quant) refusal rate + RTSI risk tier,
  bundled in `fitted_models.json` (GGUF quants only, lookup-only — no
  extrapolation, since safety does not generalise across cells per TR142/TR146).
- Safety surfaced in `plan` output: refusal rate + RTSI risk in the
  recommendation panel, Safety column in the alternatives table, and
  `safety_refusal` + `rtsi_risk` fields in `--json`.
- `scripts/build_safety_data.py` ETL plus vendored TR142 source CSVs under
  `data/safety/tr142/`.

### Changed
- Split the monolithic `cli.py` (863 lines) into per-command modules under
  `chimeraforge/commands/`; `cli.py` is now a thin Typer registrar.
- Split the `test_bench.py` and `test_planner.py` god files into focused
  per-concern modules; moved the `bundled_models` fixture to `conftest.py`.

### Fixed
- CLI commands fail loud (clean message + exit 1) instead of leaking a raw
  traceback on: missing/malformed `--models-path` (plan), malformed or
  non-result JSON (report/compare/refit), and unknown `--backend` (bench).
- `plan --latency-slo` rejects non-positive values (previously accepted).
- `report` rejects JSON that is not a bench result (e.g. `{}`) instead of
  emitting an empty report.
- `bench` no longer crashes with a UnicodeEncodeError when stdout is a
  non-UTF-8 pipe/redirect on Windows (progress spinner disabled when not a TTY).

## [0.2.0] - 2026-03-08

### Added
- `chimeraforge bench` CLI — live LLM inference benchmarking (Ollama, vLLM, TGI)
- `chimeraforge eval` CLI — quality evaluation (exact match, ROUGE-L, BERTScore, coherence)
- `chimeraforge report` CLI — Markdown/HTML report generation with statistical analysis
- `chimeraforge compare` CLI — diff benchmark results across runs with delta analysis
- `chimeraforge refit` CLI — Bayesian blending to update planner coefficients from bench data
- Backend adapter pattern: OllamaBackend, VLLMBackend, TGIBackend
- Three workload profiles: single, batch, server (Poisson arrivals)
- Quantization sweep and context-length sweep modes
- CV-based stability detection with automatic warnings
- Error-resilient runner (partial failures preserved)
- GPU metrics collection via pynvml
- JSON result serialization with environment metadata
- 10-check validation suite for fitted_models consistency (`--validate` flag)
- 3 built-in eval tasks: general_knowledge, summarization, code
- Composite quality scoring with tier classification (negligible/acceptable/concerning/unacceptable)
- Hardware offset computation and power-law refitting from bench data
- Self-contained HTML reports with inline CSS and XSS prevention
- Shared test fixtures via `tests/helpers.py` and `tests/conftest.py`
- GitHub Actions CI (Python 3.10/3.11/3.12 matrix)
- Published to PyPI: `pip install chimeraforge`
- 292 tests (80 planner + 73 bench + 42 eval + 26 report + 47 refit + 19 compare + 5 monitoring)
- Technical reports TR117-TR133

### Fixed
- Planner: ZeroDivisionError in find_models_for_size("0b")
- Planner: N-search now checks both throughput AND latency per N
- Planner: LatencyModel zero-service-time fallback (mu=1e6 not 0.001)
- Planner: QualityModel FP16 baseline inference from lookup
- Planner: formatter uses asdict() instead of manual dict
- CLI: input validation for all numeric parameters
- Narrowed all `except Exception` to specific exception types
- Proper `Console` typing via `TYPE_CHECKING` (removed all `type: ignore` suppressions)
- Extracted magic numbers to named constants in refit module

## [0.1.0] - 2025-01-15

### Added
- `chimeraforge plan` CLI — predictive capacity planner
- 4-gate pipeline: VRAM, quality, latency, budget
- 6 predictive models: VRAM, throughput, scaling, quality, cost, latency
- Hardware DB with 15 GPUs
- Pre-fitted coefficients from TR133 (fitted_models.json)
- Python single-agent benchmarking (BaselineAgent, ChimeraAgent)
- Python multi-agent benchmarking (asyncio.gather, ResourceCoordinator)
- Rust single-agent (Tokio, reqwest streaming)
- Rust multi-agent (5 runtime features)
- 16-module monitoring subsystem
- Technical reports TR108-TR116
- Comprehensive documentation (18 guides)
- Dual Ollama instance support
- Multiple async runtime support (Tokio, async-std, smol)

---

**Note**: For detailed change history, see the git commit log.
