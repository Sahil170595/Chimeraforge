# Bounded latency SLO monitoring

`chimeraforge monitor` observes existing server traffic through `/metrics`. It
does not send inference requests, change the serving process, or start a daemon.
Each window differences two cumulative histogram scrapes for an exact
`model_name`; lifetime histograms never substitute for the current window.

```bash
chimeraforge monitor --backend vllm --url http://localhost:8000 \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --ttft-slo 500 --tpot-slo 50 --interval 30 --windows 2 --json \
  --prometheus ./chimeraforge-monitor.prom

chimeraforge monitor --backend sglang --url http://localhost:30000/metrics \
  --model Qwen/Qwen3-8B --ttft-slo 500 --interval 30
```

Targets are milliseconds and the requested percentile is P95. At least one
positive, finite target is required. The default is one 30-second window;
`--windows` permits 1 through 10,000 windows. `--timeout` defaults to 10 seconds
for each metrics request and each complete saved-plan metadata observation. Interval and timeout must fit the platform's supported
wait range. Responses are capped at 2 MiB. Requests use finite
connect/read timeouts and a checked total deadline between incoming chunks;
an in-flight read can take up to the configured timeout to stop. Ctrl+C and an
API `stop_event` cancel the observation. No process remains running afterwards.

The URL must use HTTP(S), without userinfo, query parameters or fragments. A base
URL is normalized to `/metrics`. TLS certificate verification remains enabled.
The monitor provides no authentication-token or unverified-TLS flags.

## What is measured

The metric declarations and observation sites were checked on **2026-10-05** at
the pinned backend versions below. Standalone monitoring does not detect the installed
server version. Saved-plan mode separately observes supported serving metadata;
that does not prove that a different runtime version uses the pinned metric semantics.
An unrecognized or missing metric stays unknown.

| Backend source | Metric | Interpretation |
| --- | --- | --- |
| [vLLM v0.30.0](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/v1/metrics/loggers.py) | `vllm:time_to_first_token_seconds` | Time to first token |
| Same | `vllm:request_time_per_output_token_seconds` | Per-request mean output-token time, recorded once when the request finishes |
| Same | `vllm:inter_token_latency_seconds` | Gap between streamed output events; informational ITL |
| [SGLang v0.5.20](https://github.com/sgl-project/sglang/blob/v0.5.20/python/sglang/srt/observability/metrics_collector.py) | `sglang:time_to_first_token_seconds` | Time to first token, split by `is_streaming` |
| Same | `sglang:inter_token_latency_seconds` | Event interval divided by new tokens, counted once per token; informational ITL |

SGLang's ITL histogram cannot establish the P95 of per-request mean TPOT. A
SGLang `--tpot-slo` therefore returns **unknown**. A TTFT-only target can pass when
the TTFT histogram provides sufficient evidence. The older vLLM
`time_per_output_token_seconds` name is not accepted as a replacement. vLLM records
request TPOT as zero for requests generating at most one token; this backend
convention remains part of the observed distribution. Its
[calculation site](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/v1/metrics/stats.py)
uses decode time divided by output tokens minus one. vLLM also
documents the [ITL/request-TPOT distinction](https://github.com/vllm-project/vllm/blob/v0.30.0/docs/design/metrics.md).

Counts and buckets are grouped by their complete series labels before taking
deltas. Multiple engine/streaming series for the chosen model are combined only
when their bucket boundaries agree. Other explicitly labeled models are
excluded, and an unlabeled histogram cannot be assigned to the requested model.
The baseline and final series must match; newly appearing series, missing
buckets/counts/sums, contradictory sums, non-monotone deltas, and decreasing
counters make the window unknown. A changed process-start or histogram-created
timestamp also invalidates the window. Histogram lifetime metadata without a
model label is ambiguous and cannot qualify a passing window. Two scrapes cannot detect every restart
if timestamps are absent and all counters have already regrown beyond t0.

## Outcomes and evidence

No within-bucket interpolation is used. The result records the interval
containing the empirical P95, sample count, client-timed gap between completed
scrapes, target,
metric name, measurement semantics, and `confidence: histogram-bound`.
`confidence` describes histogram resolution; it is not a statistical confidence
interval or a guarantee about future requests.

| Evidence | Outcome | Exit code |
| --- | --- | --- |
| Finite P95 upper bucket bound is at or below target | `pass` | 0 |
| P95 lower boundary is at or above target (observations in that bucket exceed it) | `breach` | 3 |
| Bucket straddles target, no traffic, missing/invalid data, unsupported TPOT, or incomplete observation | `unknown` | 4 |
| Invalid request, HTTP failure, invalid plan, or failed output write | Structured error | 1 |

An open-ended `+Inf` tail has no finite upper bound: JSON uses `null`. A lower
bound can still establish a breach when it already exceeds the target. A
completed breach is retained if another window is unknown or the run is
cancelled. The overall report passes only if every requested metric in every
requested window passes. These are observations against operator policy, not a
calibrated test of planner prediction drift or GPU performance qualification.

`--json` prints one aggregate report. `--prometheus PATH` atomically replaces a
Prometheus textfile with aggregate outcome gauges and latest-window metric
gauges. Unknown measurements are omitted instead of filled with zero. Overall
and per-metric outcome gauges explicitly identify unknown results. Model labels
escape quotes, backslashes and newlines; individual request data is not exported.
An operational failure leaves the previous textfile intact, so consumers should
also check its modification time and the process exit status.

## Saved candidate bindings and Python use

```bash
chimeraforge plan --model meta-llama/Llama-3.1-8B-Instruct --ttft-slo 500 --tpot-slo 50 --save plan.json
chimeraforge monitor --backend vllm --url http://localhost:8000 \
  --model meta-llama/Llama-3.1-8B-Instruct --from-plan plan.json \
  --candidate-index YOUR_VLLM_CANDIDATE_INDEX --interval 30 --json
```

`--from-plan` binds the validated, immutable saved fingerprint, producing tool
version and selected candidate identity. Index 0 is the default; select the
candidate whose backend/model you actually serve. The saved request supplies
missing targets; each target records `saved_request`, `explicit_override` or
`not_set`. Explicit targets take precedence even when their values equal the
saved target. A saved plan without targets still needs an explicit target.

Backend and model remain explicit histogram selectors. They must match the
selected candidate, and required endpoint model/backend identity must be observed
both before and after each window. A CLI label alone does not attest serving
identity. Metadata is observed after the baseline scrape and after each completed
window, reusing a boundary between adjacent windows. Supported adapters read
vLLM `/version`, `/v1/models` and structured `/server_info?config_format=json`, or
SGLang `/server_info` (legacy fallback `/get_server_info`) and `/model_info`.
No inference, health-check or model-download request is made. Each entire
metadata call shares the monitor timeout rather than multiplying it by the
number of metadata requests. Cancellation then allows a separate cleanup budget
of `min(timeout, 1 second)` for the supported cooperative HTTPX adapter. A
`resource_cleanup` receipt records the metadata and additional cleanup budgets,
and completion or incomplete closure. A transport whose close exceeds the cleanup
budget is cancelled; its underlying resources are not claimed fully closed.
Custom transports that ignore cooperative cancellation are outside this timing
guarantee. Normal built-in clients close on completion, timeout and cancellation;
no background observation task is retained.
A custom metrics path that cannot establish a serving base URL leaves metadata
unavailable. Refused optional metadata does not erase valid histogram evidence.

JSON keeps the native `outcome` separate from `plan_binding.identity` and
`plan_binding.configuration`. Per-field states and scopes distinguish known
disagreements from unavailable evidence. Known quant/context/TP/PP/configuration
changes are mismatches. Engine DP size is recorded with engine scope; it does not
attest the full endpoint/load-balancer fleet. Missing GPU geometry, live workload
and immutable weights are explicit evidence limits, not universal failures of a
normal passive SLO check. An endpoint identity match does not qualify the full
deployment. Loading never replans, probes hardware or contacts a model repository.
This remains a histogram policy observation, not a calibrated prediction audit.

Partial matching hardware/model facts remain unavailable rather than conflicting
with missing values. A newly observed dimension cannot contradict an unspecified
saved dimension; a known disagreement still does. Hardware price and provenance
dates do not define physical serving geometry.
Documented dense/standard absence is distinct from unknown hidden/vocab
dimensions; introduced MoE/MLA structure cannot be a matched geometry.
Completed native windows are
delivered to `on_window` even if post-window metadata is cancelled. The CLI refuses
Prometheus output that resolves to the saved input artifact.

| Saved-plan evidence | Exit code |
| --- | --- |
| Known candidate/selector/configuration disagreement, including a mid-window change | 5 |
| Valid native SLO breach with no known binding disagreement | 3 |
| Required endpoint identity unavailable, unknown SLO, or incomplete observation | 4 |
| Native SLO pass and observed required model/backend match, with remaining limitations explicit | 0 |
| Invalid input, metrics HTTP failure or output failure | 1 |

Prometheus retains the native SLO gauges and adds independent
`chimeraforge_monitor_plan_identity` and `chimeraforge_monitor_plan_configuration`
state gauges with the saved fingerprint and candidate index. Unknown physical
measurements remain absent. Private raw server configuration is excluded and
diagnostic URL credentials/query tokens are redacted.

```python
from chimeraforge.monitor import MonitorRequest, run_monitor

report = run_monitor(MonitorRequest(
    backend="vllm", url="http://localhost:8000", model="org/served-model",
    ttft_slo=500.0, interval=30.0, windows=1,
))
print(report.to_dict())

from chimeraforge.api import monitor_plan

bound = monitor_plan("plan.json", MonitorRequest(
    backend="vllm", url="http://localhost:8000", model="org/served-model",
    interval=30.0, windows=1,
), candidate_index=0)
print(bound.to_dict(), bound.exit_code)
```

The regression fixture producer in `tests/test_monitor_slo.py` emits deterministic
synthetic histogram exposition using the sourced metric/label declarations.
It tests real localhost HTTP transport and CLI output, including reset, missing
data, ambiguous labels and cancellation cases. It does not claim to measure GPU
latency. `tests/test_plan_monitor.py` also runs the actual vLLM adapter over local
HTTP metadata and histogram endpoints, asserts that only supported passive GETs
occur, checks privacy and input immutability, and exercises total metadata timeout,
cancellation, known changes and unknown geometry. It is protocol acceptance,
not evidence from a live GPU inference engine. To support a changed backend contract, inspect the new pinned release's
declarations **and observation sites**, update the mapping/semantics and fixture
producer together, and rerun the tests. Do not add a metric alias merely because
its name looks similar.
