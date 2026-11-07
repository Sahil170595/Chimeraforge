# Native chat trace replay

Chimeraforge 0.92.0 adds explicit plain-text chat histories to the existing
trace commands and Python
receivers. It contacts a server you already operate; it does not start an engine,
download a model, orchestrate dependent turns or flatten roles into a prompt.

Create a private `chat.json` containing synthetic or authorized input:

```json
[
  {
    "request_id": "first",
    "mode": "chat",
    "messages": [
      {"role": "system", "content": "Answer briefly."},
      {"role": "user", "content": "Explain KV caching."}
    ],
    "max_output_tokens": 32,
    "arrival_offset_s": 0,
    "temperature": 0.0
  }
]
```

Each JSON chat row has exactly those six fields; each message has exactly `role`
and `content`. `system`, `user` and `assistant` roles retain their original order
and text. A row is one independent static history, including any supplied earlier
assistant turns. The tool does not append generated answers to subsequent rows.
The legacy four-field prompt format remains supported, including mixed workloads.

```bash
# Requires Chimeraforge 0.92.0 and an existing served model.
chimeraforge trace chat.json --model my-served-model --backend ollama \
  --base-url http://localhost:11434 --concurrency 1 \
  --request-timeout 60 --trace-timeout 90 --out chat.trace.json --json

# Same source and existing saved-candidate receiving path.
chimeraforge trace chat.json --from-plan private-plan.json --candidate-index 0 \
  --base-url http://localhost:8000 --out saved-chat.trace.json --json

# Serial independent executions of the held history workload.
chimeraforge trace-campaign chat.json --model my-served-model --backend vllm \
  --base-url http://localhost:8000 --replicates 3 --out chat.campaign.json --json
```

The typed API uses frozen `ChatMessage` and `ChatTraceRequest` values. Messages
are a tuple; `mode="chat"` is fixed rather than a constructor override:

```python
import asyncio
from chimeraforge import api

rows = [api.ChatTraceRequest(
    "first",
    (api.ChatMessage("system", "Answer briefly."),
     api.ChatMessage("user", "Explain KV caching.")),
    max_output_tokens=32, arrival_offset_s=0, temperature=0.0,
)]
receipt = asyncio.run(api.replay_trace(
    rows, model="my-served-model", backend="vllm",
    base_url="http://localhost:8000", request_timeout=60, trace_timeout=90,
))
receipt.save("private-chat.trace.json")
```

The same typed rows or private JSON path work with `replay_plan_trace`,
`replay_fleet_trace`, `replay_trace_campaign` and `replay_fleet_trace_campaign`.
Existing [fleet endpoint/routing declarations](fleet-trace.md), original member
populations and global concurrency remain explicit; chat does not allocate hosts.
[Saved gates](trace-regression-gate.md), [campaign gates](trace-campaign-gates.md),
[finite-load envelopes](trace-envelope.md) and [static diagnostics](trace-diagnostics.md)
receive the new descriptor variant through their existing strict native loaders.
Old receivers that do not know that variant refuse it.

## Admission, privacy and evidence

The whole workload is admitted before backend construction or health/model/metadata
contact. There are 1–1,024 requests, 1–128 messages per chat request, at most 64 KiB
of UTF-8 message content per request and at most 8 MiB of input/canonical JSON.
Output caps are integers 1–32,768; explicit temperature is finite in `[0, 2]`.
The existing ID, schedule, concurrency, timeout and protected-output rules apply.
These are client admission/transport limits, not model heap or inference limits.
Admitted input size does not guarantee that expanded commitments fit a receipt.
Chat descriptor expansion that alone cannot fit the native profile is refused
before backend construction. Actual whole output is admitted before copies or
publication: ordinary/saved/native-child receipts use 8 MiB, serial campaigns
16 MiB and outer fleet receipts 32 MiB. The existing pretty writer is counted with
its portable CRLF newline upper bound; output bytes/format remain unchanged.
Oversized output raises a categorical refusal without truncating, deduplicating,
creating a target or emitting a partial JSON result. Fleet-campaign exports retain
their existing 16 MiB profile. These are representation bounds, not heap bounds
or a promise that every input at the input ceiling can be exported.
Backends without an explicit chat implementation refuse before contact; there is
no completion/plugin flattening fallback.

Receipts contain mode/profile, ordered role/content-byte-count/content-SHA256
commitments, temperature, requested cap and schedule. They omit message text,
generated text and credentials. Workload fingerprints and source hashes are
consistency/provenance bindings, not authenticated engine or model execution.
Gates bind all new fields; copied numeric temperature spellings do not create a
new semantic measurement. Private input files still contain the full messages.
Use the existing [TLS/authentication options](authenticated-active.md) for sensitive
traffic. Cleanup/cancellation retains the same cooperative ownership limits.

The `native-text-chat-v1` output profile accepts assistant text only. Role-only
chunks do not start first-output timing. Tool/function calls, reasoning/thinking,
audio, image/refusal content, unsupported finishes and explicitly positive
generated reasoning/audio usage are refused categorically. Absent optional usage
is unknown, not zero or a count of chunks. Explicit zero non-text usage is allowed;
neither absent nor zero usage proves hidden computation is disabled.

Prompt counts come from the server and may include its chat template. Provided
counts must fit the receiving domain, and a known cached count cannot exceed the
known total prompt count. Missing counts stay null. Native zero durations remain
zero while unavailable derived rates stay unknown. OpenAI-shaped adapters request
final usage, but do not inject completion `echo` or token-ID controls. Without native
output-token timing they do not invent TPOT. Ollama can retain its labeled native
evaluation-duration basis. Client-visible first-output timing is not server TTFT.

## Pinned interface basis and limits

The tagged primary definitions were read on **2026-11-01**:

- [vLLM 0.30.0 chat protocol](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/entrypoints/openai/chat_completion/protocol.py)
  and [serving](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/entrypoints/openai/chat_completion/serving.py).
- [SGLang 0.5.20 protocol](https://github.com/sgl-project/sglang/blob/v0.5.20/python/sglang/srt/entrypoints/openai/protocol.py)
  and [chat serving](https://github.com/sgl-project/sglang/blob/v0.5.20/python/sglang/srt/entrypoints/openai/serving_chat.py).
  Its streaming path rejects token-ID flags; they are omitted.
- [TGI 3.3.7 router](https://github.com/huggingface/text-generation-inference/blob/v3.3.7/router/src/lib.rs).
  Its chat request model field is metadata, not checkpoint-selection proof.
- [Ollama 0.35.1 types](https://github.com/ollama/ollama/blob/v0.35.1/api/types.go)
  and [routes](https://github.com/ollama/ollama/blob/v0.35.1/server/routes.go).
  The request sends `think:false`, `truncate:false`, `shift:false` rather than
  silently accepting native history truncation/shift defaults. This preserves
  wire intent; it does not authenticate templates, attention or model consumption.

The [dated source functional record](../validation/2026-11-01-native-chat-trace-replay/README.md)
uses controlled native HTTP and actual CLI processes. Synthetic protocol/security
checks are distinct from the existing hosted pinned CPU Ollama integration, GPU
serving, model quality or performance qualification. No local engine/image/parser
or browser installation is required to reproduce the controlled record.
