# Real request-trace replay

Unreleased 0.82.0 source adds [authenticated active benchmarks and traces](authenticated-active.md)
with runtime-only `connection` settings and matching CLI secure flags. Public
installation remains 0.81.0; existing anonymous defaults and native metrics remain.

Chimeraforge 0.63.0 adds [saved trace regression gates](trace-regression-gate.md)
through `gate --kind trace`.
Chimeraforge 0.64.0 adds [serial campaigns](trace-campaign.md) over
the same native replay route, with one held workload and complete replica populations.

Chimeraforge 0.60.0 executes actual requests against an existing endpoint. Install `pip install "chimeraforge[bench]==0.60.0"`. The introduced implementation passed [hosted source acceptance](https://github.com/Sahil170595/Chimeraforge/actions/runs/37955012604); each release separately qualifies its versioned artifacts. It does not launch a server or download a model.
Prompts are private inputs sent to the selected endpoint.

```python
import asyncio
from chimeraforge.api import TraceRequest, TraceSLO, replay_trace

receipt = asyncio.run(replay_trace([
    TraceRequest("first", "Explain KV caching briefly.", 32, 0),
    TraceRequest("second", "List three primary colors.", 16, 0.1),
], model="llama3.2-3b", backend="ollama", concurrency=1,
   request_timeout=60, trace_timeout=90,
   slos=TraceSLO(latency_ms=2000, first_output_ms=500, tpot_ms=50)))
receipt.save("trace.json")
print(receipt.to_dict()["goodput"])
```

The JSON file accepted by the CLI and API is a list of objects with exactly
`request_id`, `prompt`, `max_output_tokens` and `arrival_offset_s`. Arrival offsets
are relative to the replay origin, after preflight and initial metadata. Input
order is retained in the receipt; arrival offsets need not be sorted.

```bash
chimeraforge trace workload.json --model llama3.2-3b --backend ollama \
  --base-url http://localhost:11434 --concurrency 1 \
  --request-timeout 60 --trace-timeout 90 \
  --latency-slo 2000 --first-output-slo 500 --tpot-slo 50 \
  --out trace.json --json
```

The typed API also accepts a workload path. `TraceReplay.to_dict()` returns a
defensive copy. `save()` atomically writes JSON and refuses paths or hardlink
aliases of the input workload. CLI stdout and `--out` contain the same receipt.

## Bounds and execution

- 1-1,024 requests; at most 8 MiB of input/canonical JSON.
- Unique request IDs: 1-80 ASCII letters, digits, dots, underscores or hyphens.
- Nonempty UTF-8 prompts, at most 64 KiB each; integer output caps 1-32,768.
- Finite nonnegative arrival offsets up to 3,600 seconds, within the trace deadline.
- Integer concurrency 1-64. Positive request/trace timeouts up to 3,600 seconds;
  defaults 300/600 seconds. SLO values are positive finite milliseconds.

The adapter must identify the named engine and accept the served model before
replay. Each preflight or metadata operation is separately bounded by the request
timeout; the trace timeout covers the scheduled replay phase only. Backend cleanup
is cooperative through the existing lifecycle and may extend the observed end
of a timeout. A hung external adapter is not guaranteed to close by the deadline.
Metadata does not authenticate actual file bytes, fleet topology or hardware.

Requests wait for their absolute scheduled arrival, then for a concurrency slot.
High-resolution monotonic `time.perf_counter()` records timestamps as offsets;
the receipt records its resolution. Early timer wakeups are rechecked before
admission. Request timeout covers generation after acquiring a slot. The whole
trace deadline cancels waiting and running requests and drains owned tasks.

Passing `stop_event=asyncio.Event()` permits a graceful stop with a complete
population receipt, including while preflight or metadata is pending: the owned
probe is cancelled and drained before adapter cleanup. CLI Ctrl-C sets that event. External asyncio cancellation
closes the backend, drains tasks and propagates `CancelledError` to the caller;
it does not fabricate a completed receipt. Adapter cleanup failure is explicit.

## Native timing and complete outcomes

Each request contains scheduled arrival, actual arrival, generation start,
actual first output when supported, and terminal offsets in seconds. Derived
client values in milliseconds are:

| Field | Basis |
| --- | --- |
| `scheduler_lag_ms` | actual arrival minus scheduled arrival |
| `client_queue_ms` | generation start minus actual arrival |
| `latency_ms` | client terminal minus scheduled arrival; includes scheduler lag and queue |
| `first_output_ms` | observed first client output minus scheduled arrival; includes lag and queue |
| `tpot_ms` | explicitly named per-request mean decode basis |

Ollama uses actual streamed output frames for first output, not
`prompt_eval_duration`. Its final `eval_duration / eval_count` is the native
mean server decode ms/token. Server prefill duration remains a separate native
field with `ttft_basis=server-prefill-duration`. Thinking-only content is not
treated as first visible output. Callbacks outside the active generation are
ignored; first-output qualification requires an observed start-to-terminal
timestamp and cannot mutate a completed receipt. Native final token counts are retained only
when observed; incomplete streams keep counts unknown rather than estimate
tokens from text or chunks.

The native NDJSON parser caps response bytes at 16 MiB, scans each frame without
copying the unconsumed tail, and yields between batches of 32 frames so cancellation
and deadlines can run even when many frames arrive in one network chunk.
Independent checkpoints every 32 native chunks or 64 KiB also cover fragmented
frames with no newline yet. It keeps
native chunk delivery rather than coalescing first output until a fixed buffer fills.

Chimeraforge **0.62.0** adds native observations for vLLM, SGLang and TGI to
the same CLI and typed API. vLLM/SGLang request `return_token_ids=true`, one
choice, `echo=false` and final stream usage. TGI exposes one native token per
event, including final/control tokens. Native ID coverage must equal the final
server output count and respect the actual outgoing output cap. Visible first
output remains separate from native control/EOS arrivals.

`client-first-to-last-native-output/(server-output-count-1)` qualifies only
with complete IDs, one token at the first wire arrival, at least two output
tokens, and distinct first/last arrivals. All frames completing in one transport
packet share its arrival time; parser calls cannot invent elapsed decode time.
Missing IDs, an initial multi-token batch, a one-token completion, or entirely
buffered output leaves mean decode timing/rate unavailable while preserving
valid completion, counts and observed visible first output. Missing cache counts
remain unknown. Server prefill duration is unavailable for these observations.
The legacy `bench` rate interface refuses unavailable timing explicitly.

SSE parsing bounds each frame to 64 KiB, the stream to 8 MiB and 16,384 frames,
including keep-alives, and yields for cancellation. Successful OpenAI completion
requires a stop/length finish, exactly one final usage event and DONE. TGI requires
successful final details and normal EOF. Errors, invalid counters/IDs, cap
violations and incomplete frames refuse completion and close the response.
Different mean bases must not be pooled. Arbitrary plugin bases remain
unavailable. None of these means proves every-token latency.

`execution` records planned, attempted, completed, failed, partial, cancelled
and not-started counts. Partial means first output was observed before failure;
unobserved output does not imply no tokens were produced. Terminal latency can
remain known for a failed request, but it cannot qualify. Requested output caps
and actual output counts are separate, with exceeded/within-cap/unknown states.
Repeated prompts may warm caches; no cold-run independence is claimed.

## Joint-target goodput and exit behavior

Each requested target is `pass`, `breach` or `unknown`. The joint outcome is
`not_completed` for failed/incomplete requests, otherwise `breach` if a known
target is breached, `unknown` if required timing is unavailable, and `pass` only
when all requested targets pass. No SLOs means `not_requested` and no goodput
qualification.

Goodput is joint-passing completed requests divided by the complete horizon:
the maximum of the final planned arrival and observed replay elapsed time.
Future not-started requests remain in the population and planned horizon; no
survivor-only percentile or denominator is substituted. If preflight fails or
the operation is already stopped, there is no replay origin, measured horizon
or measured rate. The planned horizon is still visible as input context.

Exit 0 means all requests completed and lifecycle succeeded, even when targets
were breached or unknown. Exit 1 means failed, partial, cancelled or incomplete
execution. CLI exit 2 means invalid input/options or output failure. Inspect
`goodput.joint_outcomes` for SLO results, rather than interpreting exit 0 as a pass.

## Privacy and proof limits

The receipt binds canonical validated workload content, plus the original file
SHA256 when present. Descriptors hold prompt SHA256/UTF-8 byte length, IDs, caps
and arrivals; prompts and completions are not serialized. Provider errors retain
only closed categories/stages, and endpoint credentials/query values are removed.
Hashes are content integrity, not authentication or anonymization of low-entropy
prompts. Choose non-sensitive request IDs and model names.

Before/after supported serving metadata and stability are informational. This
receipt measures a contacted endpoint and client workload; it cannot qualify
planned GPU geometry, actual served weight/tokenizer bytes or an independently
cold deployment. Hosted acceptance runs the installed CLI against the existing
pinned CPU Ollama/Smol endpoint, verifies timing arithmetic and actual native
counts, and preserves SLO outcomes without imposing shared-runner speed limits.
Candidate installed consumers additionally exercise explicitly synthetic native
SSE fixtures through the public CLI on Linux, Windows and macOS. This qualifies
artifact/protocol behavior, not execution of the native GPU engines.

Native contracts were checked on 2026-10-12 against pinned
[vLLM 0.30.0](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/entrypoints/openai/completion/serving.py),
[SGLang 0.5.20](https://github.com/sgl-project/sglang/blob/94602c9c2b7cbdb8efd5c52802dac6a1c180089e/python/sglang/srt/entrypoints/openai/serving_completions.py),
and [TGI 3.3.7](https://github.com/huggingface/text-generation-inference/blob/dfb3fbe78e0d1d69251bd33065591c61bafdfaa8/router/src/server.rs).

The timing contract follows Python's [performance-counter API](https://docs.python.org/3.12/library/time.html#time.perf_counter)
and Ollama's [generate API](https://docs.ollama.com/api/generate), checked on
2026-10-09 against the existing pinned Ollama 0.35.1 response types.
