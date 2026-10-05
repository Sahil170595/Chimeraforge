"""Synthetic traffic exercises sourced vLLM/SGLang histogram contracts, not GPUs."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from typer.testing import CliRunner

from chimeraforge.monitor import (
    MonitorError,
    MonitorRequest,
    evaluate_window,
    prometheus_text,
    run_monitor,
)


MODEL = "org/model"
TTFT_EDGES = (0.1, 0.5, 1.0)
DECODE_EDGES = (0.01, 0.02, 0.1)


def histogram(name, observations, edges, *, model=MODEL, extra=""):
    # Declarations: vLLM v0.30.0 loggers.py, SGLang v0.5.20 metrics_collector.py.
    labels = f"model_name={json.dumps(model)}{extra}"
    rows = [f"# TYPE {name} histogram"]
    for edge in edges:
        count = sum(x <= edge for x in observations)
        rows.append(f'{name}_bucket{{{labels},le="{edge}"}} {count}')
    rows.extend(
        [
            f'{name}_bucket{{{labels},le="+Inf"}} {len(observations)}',
            f"{name}_count{{{labels}}} {len(observations)}",
            f"{name}_sum{{{labels}}} {sum(observations)}",
        ]
    )
    return "\n".join(rows) + "\n"


def scrape(backend="vllm", *, ttft=(), tpot=(), itl=(), model=MODEL):
    prefix = backend + ":"
    extra = ',engine="0"' if backend == "vllm" else ',is_streaming="true"'
    text = histogram(
        prefix + "time_to_first_token_seconds", ttft, TTFT_EDGES, model=model, extra=extra
    )
    if backend == "vllm":
        text += histogram(
            prefix + "request_time_per_output_token_seconds",
            tpot,
            DECODE_EDGES,
            model=model,
            extra=',engine="0"',
        )
    text += histogram(
        prefix + "inter_token_latency_seconds",
        itl,
        DECODE_EDGES,
        model=model,
        extra=',engine="0"' if backend == "vllm" else "",
    )
    return text


def window(first, second, **kwargs):
    return evaluate_window(
        first,
        second,
        backend=kwargs.pop("backend", "vllm"),
        model=kwargs.pop("model", MODEL),
        seconds=30.0,
        **kwargs,
    )


def pair(backend="vllm", *, ttft=0.05, tpot=0.015, itl=0.08):
    first = scrape(backend, ttft=[0.05] * 100, tpot=[0.015] * 100, itl=[0.08] * 100)
    second = scrape(
        backend,
        ttft=[0.05] * 100 + [ttft] * 20,
        tpot=[0.015] * 100 + [tpot] * 20,
        itl=[0.08] * 100 + [itl] * 20,
    )
    return first, second


def test_window_is_not_lifetime_and_tpot_is_not_itl():
    first, second = pair(ttft=0.7)
    result = window(first, second, ttft_slo=400, tpot_slo=25)
    assert result.outcome == "breach"
    assert result.metrics["ttft"].samples == 20
    assert result.metrics["ttft"].p95_lower_ms == 500
    assert result.metrics["ttft"].p95_upper_ms == 1000
    assert result.metrics["tpot"].outcome == "pass"
    assert result.metrics["tpot"].metric == "vllm:request_time_per_output_token_seconds"
    assert result.metrics["itl"].p95_upper_ms == 100
    assert result.metrics["tpot"].unit == "ms"
    assert result.metrics["tpot"].confidence == "histogram-bound"


def test_sglang_ttft_is_supported_but_itl_does_not_prove_request_tpot():
    first, second = pair("sglang")
    result = window(first, second, backend="sglang", ttft_slo=150, tpot_slo=25)
    assert result.metrics["ttft"].outcome == "pass"
    assert result.metrics["tpot"].outcome == "unknown"
    assert "request TPOT" in result.metrics["tpot"].reason
    assert result.metrics["itl"].samples == 20
    assert result.outcome == "unknown"


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_ttft_only_passes(backend):
    result = window(*pair(backend), backend=backend, ttft_slo=150)
    assert result.outcome == "pass"
    assert result.metrics["ttft"].p95_upper_ms == 100


def test_no_traffic_is_unknown():
    first, _ = pair()
    result = window(first, first, ttft_slo=150)
    assert result.outcome == "unknown"
    assert "no observations" in result.metrics["ttft"].reason


def test_missing_metric_cannot_pass():
    first, second = pair()
    second = "\n".join(x for x in second.splitlines() if "request_time_per_output" not in x)
    result = window(first, second, ttft_slo=150, tpot_slo=25)
    assert result.outcome == "unknown"
    assert result.metrics["ttft"].outcome == "pass"
    assert result.metrics["tpot"].p95_upper_ms is None


def test_coarse_bucket_does_not_invent_a_percentile():
    result = window(*pair(ttft=0.3), ttft_slo=300)
    metric = result.metrics["ttft"]
    assert (metric.p95_lower_ms, metric.p95_upper_ms) == (100, 500)
    assert metric.outcome == "unknown"
    assert "straddles" in metric.reason


@pytest.mark.parametrize("target,expected", [(900, "breach"), (1200, "unknown")])
def test_unbounded_tail(target, expected):
    result = window(*pair(ttft=2.0), ttft_slo=target)
    assert result.metrics["ttft"].p95_upper_ms is None
    assert result.metrics["ttft"].p95_lower_ms == 1000
    assert result.outcome == expected
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize("suffix", ["_bucket", "_count", "_sum"])
def test_reset_cannot_pass(suffix):
    first, second = pair()
    rows = second.splitlines()
    index = next(
        i
        for i, row in enumerate(rows)
        if row.startswith("vllm:time_to_first_token_seconds" + suffix)
    )
    rows[index] = rows[index].rsplit(" ", 1)[0] + " 0"
    result = window(first, "\n".join(rows), ttft_slo=150)
    assert result.outcome == "unknown"
    assert result.metrics["ttft"].confidence == "unknown"


@pytest.mark.parametrize("bad", ["NaN", "+Inf", "-1", "1.5"])
def test_invalid_counts_are_unknown(bad):
    first, second = pair()
    second = second.replace('le="0.1"} 120', f'le="0.1"}} {bad}', 1)
    assert window(first, second, ttft_slo=150).outcome == "unknown"


def test_missing_duplicate_or_changed_buckets_are_unknown():
    first, second = pair()
    row = next(
        x for x in second.splitlines() if x.startswith("vllm:time_to_first_token_seconds_bucket")
    )
    assert window(first, second.replace(row + "\n", ""), ttft_slo=150).outcome == "unknown"
    assert window(first, second + row + "\n", ttft_slo=150).outcome == "unknown"
    assert (
        window(first, second.replace('le="0.5"', 'le="0.6"', 1), ttft_slo=150).outcome == "unknown"
    )


def test_model_selection_does_not_pool_another_model():
    first, second = pair()
    other_first = scrape(ttft=[0.7] * 100, model="other")
    other_second = scrape(ttft=[0.7] * 120, model="other")
    result = window(first + other_first, second + other_second, ttft_slo=150)
    assert result.outcome == "pass"
    assert result.metrics["ttft"].samples == 20
    missing_labels = second.replace('model_name="org/model",', "")
    assert window(first, missing_labels, ttft_slo=150).outcome == "unknown"


def test_absent_baseline_is_unknown():
    _, second = pair()
    assert window(scrape(model="other"), second, ttft_slo=150).outcome == "unknown"


def test_process_restart_cannot_pass():
    first, second = pair()
    result = window(
        first + "process_start_time_seconds 100\n",
        second + "process_start_time_seconds 200\n",
        ttft_slo=150,
    )
    assert result.outcome == "unknown"
    assert "restart" in result.metrics["ttft"].reason


@pytest.mark.parametrize("value", ["NaN", "-1", "99"])
def test_finished_request_counter_reset_or_invalid_is_unknown(value):
    first, second = pair()
    name = f'vllm:request_success_total{{model_name="{MODEL}",finished_reason="stop"}} '
    result = window(first + name + "100\n", second + name + value + "\n", ttft_slo=150)
    assert result.outcome == "unknown"


def test_sum_inconsistent_with_buckets_cannot_pass():
    first, second = pair()
    rows = second.splitlines()
    index = next(
        i for i, x in enumerate(rows) if x.startswith("vllm:time_to_first_token_seconds_sum")
    )
    rows[index] = rows[index].rsplit(" ", 1)[0] + " 100"
    assert window(first, "\n".join(rows), ttft_slo=150).outcome == "unknown"


def test_model_labels_escape_commas_quotes_and_newlines():
    model = 'org/comma,quote"slash\\newline\nmodel'
    first, second = pair()
    first = first.replace(json.dumps(MODEL), json.dumps(model))
    second = second.replace(json.dumps(MODEL), json.dumps(model))
    assert window(first, second, model=model, ttft_slo=150).outcome == "pass"


def test_unrepresentable_millisecond_boundary_is_unknown():
    first, second = pair()
    first = first.replace('le="0.1"', 'le="1e308"')
    second = second.replace('le="0.1"', 'le="1e308"')
    result = window(first, second, ttft_slo=150)
    assert result.outcome == "unknown"
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ttft_slo": float("nan")},
        {"tpot_slo": -1},
        {"interval": float("inf")},
        {"interval": 0},
        {"windows": 0},
        {"windows": True},
        {"timeout": -1},
        {"backend": "ollama"},
        {"model": ""},
        {"url": "file:///metrics"},
        {"url": "http://user:secret@localhost/metrics"},
        {"ttft_slo": True},
        {"interval": None},
        {"timeout": None},
        {"backend": []},
        {"interval": 10**1000},
    ],
)
def test_invalid_requests_fail_before_network(kwargs):
    defaults = dict(backend="vllm", url="http://localhost:8000", model=MODEL, ttft_slo=150)
    defaults.update(kwargs)
    with pytest.raises(MonitorError):
        MonitorRequest(**defaults).validate()


def test_explicit_target_required():
    with pytest.raises(MonitorError, match="target"):
        MonitorRequest("vllm", "http://localhost:8000", MODEL).validate()


@contextmanager
def metrics_server(responses, *, status=200):
    payloads = iter(responses)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/metrics"
            payload = next(payloads)
            body = payload.encode() if isinstance(payload, str) else payload
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def test_live_bounded_windows_and_prometheus(tmp_path):
    first, second = pair()
    third = scrape(ttft=[0.05] * 140, tpot=[0.015] * 140, itl=[0.08] * 140)
    with metrics_server([first, second, third]) as url:
        report = run_monitor(
            MonitorRequest("vllm", url, MODEL, ttft_slo=150, interval=0.01, windows=2)
        )
    assert report.outcome == "pass"
    assert len(report.windows) == 2
    assert all(x.seconds > 0 for x in report.windows)
    text = prometheus_text(report)
    assert 'chimeraforge_monitor_outcome{backend="vllm",model="org/model",outcome="pass"} 1' in text
    assert "chimeraforge_monitor_p95_upper_ms" in text


def test_cancelled_run_does_not_pass():
    stop = threading.Event()
    stop.set()
    report = run_monitor(
        MonitorRequest("vllm", "http://localhost:1", MODEL, ttft_slo=150), stop_event=stop
    )
    assert report.cancelled
    assert report.outcome == "unknown"
    assert report.windows == []


def test_interrupt_wait_cannot_pass(monkeypatch):
    first, _ = pair()
    event = threading.Event()
    monkeypatch.setattr(event, "wait", lambda timeout: (_ for _ in ()).throw(KeyboardInterrupt()))
    with metrics_server([first]) as url:
        report = run_monitor(MonitorRequest("vllm", url, MODEL, ttft_slo=150), stop_event=event)
    assert report.cancelled and report.outcome == "unknown"


def test_prometheus_escapes_model_and_omits_unknown_value():
    from dataclasses import replace

    first, _ = pair()
    with metrics_server([first, first]) as url:
        report = run_monitor(MonitorRequest("vllm", url, MODEL, ttft_slo=150, interval=0.01))
    report = replace(report, model='x"\\\ny')
    text = prometheus_text(report)
    assert 'model="x\\"\\\\\\ny"' in text
    assert 'outcome="unknown"} 1' in text
    assert "chimeraforge_monitor_p95_upper_ms{" not in text


@pytest.mark.parametrize(
    "ttft,exit_code,outcome", [(0.05, 0, "pass"), (0.7, 3, "breach"), (0.3, 4, "unknown")]
)
def test_cli_actual_http_json_and_exit_codes(ttft, exit_code, outcome, tmp_path):
    from chimeraforge.cli import app

    output = tmp_path / "monitor.prom"
    with metrics_server(pair(ttft=ttft)) as url:
        result = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                MODEL,
                "--ttft-slo",
                "300",
                "--interval",
                "0.01",
                "--json",
                "--prometheus",
                str(output),
            ],
        )
    assert result.exit_code == exit_code, result.output
    assert json.loads(result.output)["outcome"] == outcome
    assert output.read_text().startswith("# HELP")


def test_cli_transport_error_is_operational_exit_one():
    from chimeraforge.cli import app

    with metrics_server(["unavailable"], status=503) as url:
        result = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                MODEL,
                "--ttft-slo",
                "150",
                "--json",
            ],
        )
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)


def test_cli_saved_plan_imports_explicit_targets_without_replanning(tmp_path, monkeypatch):
    from chimeraforge.api import PlanRequest, plan
    from chimeraforge.cli import app

    path = tmp_path / "plan.json"
    plan(PlanRequest(ttft_slo=150, allow_network=False)).save(path)
    monkeypatch.setattr(
        "chimeraforge.planner.service.run_plan",
        lambda **kwargs: pytest.fail("loading a plan must not replan"),
    )
    with metrics_server(pair()) as url:
        result = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                MODEL,
                "--from-plan",
                str(path),
                "--interval",
                "0.01",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["windows"][0]["metrics"]["ttft"]["target_ms"] == 150


def test_cli_human_output_and_failed_output_write(tmp_path):
    from chimeraforge.cli import app

    with metrics_server(pair(ttft=0.7)) as url:
        result = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                MODEL,
                "--ttft-slo",
                "300",
                "--interval",
                "0.01",
            ],
        )
    assert result.exit_code == 3 and "P95 upper bound 1000 ms" in result.output
    with metrics_server(pair()) as url:
        result = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                MODEL,
                "--ttft-slo",
                "300",
                "--interval",
                "0.01",
                "--prometheus",
                str(tmp_path / "absent" / "out.prom"),
                "--json",
            ],
        )
    assert result.exit_code == 1 and "cannot write" in json.loads(result.output)["error"]


@pytest.mark.parametrize(
    "payload,reason",
    [(b"\xff", "UTF-8"), ("x" * (2 * 1024 * 1024 + 1), "size limit")],
    ids=["invalid-utf8", "oversized-body"],
)
def test_live_invalid_or_unbounded_response_is_operational_error(payload, reason):
    with metrics_server([payload]) as url:
        with pytest.raises(MonitorError, match=reason):
            run_monitor(MonitorRequest("vllm", url, MODEL, ttft_slo=150, interval=0.01))


def test_cancellation_after_completed_window_is_unknown_and_stops_scraping():
    event = threading.Event()
    with metrics_server(pair()) as url:
        report = run_monitor(
            MonitorRequest("vllm", url, MODEL, ttft_slo=150, interval=0.01, windows=2),
            stop_event=event,
            on_window=lambda result: event.set(),
        )
    assert len(report.windows) == 1
    assert report.cancelled and report.outcome == "unknown"
