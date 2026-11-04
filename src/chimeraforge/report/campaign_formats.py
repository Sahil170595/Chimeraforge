"""Complete static campaign panels; native child scales remain per-execution."""

from __future__ import annotations

from collections.abc import Iterator
import textwrap

from chimeraforge.report import trace_formats as native

SCOPE = (
    "Every declared execution is retained. Native child metrics use separate client clocks; "
    "no pooled latency/percentile/goodput, regression-gate verdict or independence claim. "
    "Missing native receipts retain declared rows/member routing only, not observed zeros."
)


def summary(view: dict) -> Iterator[str]:
    outcome = f"native exit: {view['exit_code']}; state: {view['state']}"
    yield f"Whole campaign: {view['kind']}; {outcome}"
    yield "Declared population: " + "; ".join(f"{k}={v}" for k, v in view["population"].items())
    yield "Native execution coverage: " + "; ".join(
        f"{k}={v}" for k, v in view["execution"].items()
    )
    yield (
        f"Native stop reason: {view['stop_reason'] or 'none'}; outer cleanup: {view['cleanup']}; "
        f"campaign client elapsed_seconds: {view['elapsed_seconds']}"
    )
    yield f"Source SHA256: {view['sha256']}"
    yield f"Fingerprint: {view['fingerprint']}"
    yield f"Manifest fingerprint: {view['manifest_fingerprint']}"
    yield f"Source representation: {view['byte_basis']}; {view['size_bytes']} bytes"
    yield SCOPE


def _title(panel: dict, count: int) -> str:
    return f"Execution {panel['ordinal']}/{count}: {panel['state']}"


def _facts(panel: dict) -> str:
    evidence = (
        "returned native receipt"
        if panel["native_present"]
        else "declared-only; observations unavailable"
    )
    return (
        f"Evidence: {evidence}; campaign-relative start_s={native.number(panel['start_s'])}; "
        f"end_s={native.number(panel['end_s'])}"
    )


def svg(view: dict, title: str) -> Iterator[str]:
    wrapped = [
        *textwrap.wrap(title, width=native.TITLE_WRAP_CHARS),
        *(
            piece
            for line in summary(view)
            for piece in textwrap.wrap(line, width=native.TEXT_WRAP_CHARS)
        ),
    ]
    y = 40 + len(wrapped) * 18
    positions = []
    for panel in view["panels"]:
        facts = textwrap.wrap(_facts(panel), width=native.TEXT_WRAP_CHARS)
        positions.append((y, facts))
        y += (
            len(facts) * 18
            + native.layout(panel["view"], _title(panel, len(view["panels"])))["height"]
            + 24
        )
    height = y + 36
    yield (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {native.WIDTH} {height}" role="img" aria-labelledby="campaign-title" '
        'style="width:100%;height:auto;background:#fff;color:#142536">\n'
    )
    yield f'<title id="campaign-title">{native.escape(title)}</title>\n'
    yield "<style>text{font-family:monospace;font-size:11px;fill:#142536}</style>\n"
    for index, line in enumerate(wrapped):
        yield f'<text x="20" y="{24 + index * 18}">{native.escape(line)}</text>\n'
    for panel, (offset, facts) in zip(view["panels"], positions):
        yield f'<g data-execution="{panel["ordinal"]}" data-execution-state="{panel["state"]}">\n'
        for index, line in enumerate(facts):
            yield f'<text x="20" y="{offset + 14 + index * 18}">{native.escape(line)}</text>\n'
        yield from native.svg(
            panel["view"],
            _title(panel, len(view["panels"])),
            prefix=f"execution-{panel['ordinal']}-",
            y=offset + len(facts) * 18,
        )
        yield "</g>\n"
    yield (
        f'<text x="20" y="{height - 16}">Whole declared campaign; '
        "descriptive client diagnostics only.</text>\n</svg>\n"
    )


def chunks(view: dict, title: str, fmt: str) -> Iterator[str]:
    if fmt == "markdown":
        yield f"# {native.markdown_text(title)}\n\n"
        yield "\n\n".join(summary(view)) + "\n\n"
        for panel in view["panels"]:
            yield f"## {_title(panel, len(view['panels']))}\n\n{_facts(panel)}\n\n"
            yield from native.markdown(panel["view"], "Native execution diagnostics", level=3)
        return
    if fmt == "html":
        yield (
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{native.escape(title)}</title><style>body{{margin:0 auto;padding:16px;"
            "max-width:1260px;background:#eef2f8}svg{display:block;max-width:100%}</style></head><body>\n"
        )
    yield from svg(view, title)
    if fmt == "html":
        yield "</body></html>\n"
