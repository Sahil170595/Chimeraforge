# Plan-bound request traces

Unreleased 0.82.0 source adds [authenticated active benchmarks and traces](authenticated-active.md)
with runtime-only `connection` settings and matching CLI secure flags. Public
installation remains 0.81.0; existing anonymous defaults and native metrics remain.

Available since **Chimeraforge 0.68.0**.

`trace --from-plan` replays a private workload while retaining a selected frozen
candidate. It validates the saved plan or portable bundle before endpoint contact,
without replanning or substituting current coefficients. Inspect the candidate's
backend and model before running it against your existing serving endpoint.

```bash
chimeraforge trace workload.json --from-plan plan.json --candidate-index 0 --model YOUR_SERVED_MODEL --concurrency 1 --out plan-trace.json --json
```

Every workload row's `max_output_tokens` must equal that candidate's saved
`decode_tokens_per_req`; a mismatch refuses the operation before contact. Arrival
offsets are preserved. The client concurrency and timeouts remain explicit replay
controls. The saved request rate is modeled intent: the operation does not invent
a Poisson schedule or reschedule your requests to match it.

The backend comes from the selected candidate, including the existing llama.cpp
to Ollama wrapper mapping. An optional `--model` supplies the actual served alias
and is recorded as an override. Explicit `--backend` and SLO flags are refused
with `--from-plan`. Only nonnull saved `latency_slo`, `ttft_slo` and `tpot_slo`
inputs become native targets, in milliseconds, milliseconds and milliseconds per
token respectively. Planner defaults and prediction results do not become
observed targets.

```python
from chimeraforge import api

saved = api.load_plan("plan.json")
selected = saved.candidate(0)
workload = [api.TraceRequest("one", "Say hello.", selected.decode_tokens_per_req, 0.0)]
receipt = await api.replay_plan_trace(saved, workload, candidate_index=0)
receipt.save("plan-trace.json")
native = receipt.native_trace.to_dict()
```

The wrapper retains the complete unchanged native trace. Its native raw-file
hash remains null because frozen typed requests were replayed; the wrapper
separately retains the original private workload file hash when supplied and its
ordered prompt commitments. Neither prompts nor completions are added to the
public wrapper.

Only output caps are sent as generation options by native trace replay. Saved
context, parallelism, batching and replica settings are modeled facts; they are
not silently injected or reported as applied. Before/after serving observations
are checked separately. A known disagreement before replay cannot be repaired by
a later matching observation, and a missing phase stays unavailable. Observed
prompt/output token lengths are checked separately from the requested output cap.

Exit `0` means complete native execution with no known binding mismatch, `1`
means incomplete execution or a known binding mismatch, and `2` means invalid
input/output. Native execution and SLO outcomes remain visible independently;
successful execution can contain an SLO breach or unavailable configuration facts.
Output protects the consumed plan, private workload and verified bundle members,
including aliases, before contact through the CLI and again when saving a receipt.

This wrapper has its own kind, `chimeraforge.plan-trace`. Existing native trace
receivers require an explicitly selected `.native_trace` rather than silently
coercing the wrapper. Content consistency does not authenticate served weights,
physical hardware, modifier state, independent executions or planner calibration.
