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
for each metrics request. Interval and timeout must fit the platform's supported
wait range. Responses are capped at 2 MiB. Requests use finite
connect/read timeouts and a checked total deadline between incoming chunks;
an in-flight read can take up to the configured timeout to stop. Ctrl+C and an
API `stop_event` cancel the observation. No process remains running afterwards.

The URL must use HTTP(S), without userinfo, query parameters or fragments. A base
URL is normalized to `/metrics`. TLS certificate verification remains enabled.
The monitor provides no authentication-token or unverified-TLS flags.

## What is measured

The metric declarations and observation sites were checked on **2026-10-05** at
the pinned backend versions below. The monitor does not detect the installed
server version: an unrecognized or missing metric stays unknown.

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

## Saved targets and Python use

```bash
chimeraforge plan --model-size 3b --ttft-slo 500 --tpot-slo 50 --save plan.json
chimeraforge monitor --backend vllm --url http://localhost:8000 \
  --model YOUR_EXACT_SERVED_MODEL_NAME --from-plan plan.json --interval 30 --json
```

`--from-plan` loads the saved request's explicit TTFT/TPOT targets, with explicit
CLI targets taking precedence. Backend and served model label remain explicit:
a planner model alias is not evidence of the server's label. Loading does not
replan, access a model repository, or compare observations with predicted values.
A saved plan without explicit targets still needs a CLI target.

```python
from chimeraforge.monitor import MonitorRequest, run_monitor

report = run_monitor(MonitorRequest(
    backend="vllm", url="http://localhost:8000", model="org/served-model",
    ttft_slo=500.0, interval=30.0, windows=1,
))
print(report.to_dict())
```

The regression fixture producer in `tests/test_monitor_slo.py` emits deterministic
synthetic histogram exposition using the sourced metric/label declarations.
It tests real localhost HTTP transport and CLI output, including reset, missing
data, ambiguous labels and cancellation cases. It does not claim to measure GPU
latency. To support a changed backend contract, inspect the new pinned release's
declarations **and observation sites**, update the mapping/semantics and fixture
producer together, and rerun the tests. Do not add a metric alias merely because
its name looks similar.
