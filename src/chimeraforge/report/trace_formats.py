"""Static complete diagnostic formats from the closed native projection."""

from __future__ import annotations

from collections.abc import Iterator
import html
import textwrap

from chimeraforge.report.trace_view import TIMES, TIMINGS

WIDTH = 1200
LEFT = 185
PLOT_WIDTH = 970
ROW_HEIGHT = 145
MEMBER_HEIGHT = 30
TEXT_WRAP_CHARS = 150
TITLE_WRAP_CHARS = 40


def escape(value: object) -> str:
    return html.escape(str(value), quote=True).encode("ascii", "xmlcharrefreplace").decode("ascii")


def number(value: object) -> str:
    return "unavailable" if value is None else str(value)


def summary(view: dict) -> Iterator[str]:
    yield f"Kind: {view['kind']}; native exit: {view['exit_code']}; execution: {view['execution']}"
    yield (
        f"Configuration: {view['configuration']}; cleanup: {view['cleanup']}; "
        f"clock: {view['clock']}"
    )
    scope = (
        f"Original members: {len(view['members'])}"
        if view["members"]
        else "Ordinary endpoint scope; no original-fleet declaration"
    )
    yield scope + "; global concurrency: " + str(view["concurrency"])
    yield "Population: " + "; ".join(f"{k}={v}" for k, v in view["counts"].items())
    yield "Native joint SLO: " + "; ".join(f"{k}={v}" for k, v in view["joint"].items())
    yield "Targets (ms; TPOT ms/token): " + "; ".join(
        f"{k}={number(v)}" for k, v in view["targets"].items()
    )
    yield "Goodput: " + "; ".join(f"{k}={number(v)}" for k, v in view["goodput"].items())
    yield f"Source SHA256: {view['sha256']}"
    yield f"Fingerprint: {view['fingerprint']}"
    yield f"Source representation: {view['byte_basis']}; {view['size_bytes']} bytes"


def _row_lines(row: dict) -> list[str]:
    details = [
        f"Member={number(row['member'])}; "
        + "; ".join(f"{k}={number(row['times'][k])}" for k in TIMES),
        "; ".join(f"{k}={number(row['timing'][k])}" for k in TIMINGS),
        f"Tokens={number(row['tokens'])}; cap={row['cap']}; SLO="
        + "; ".join(f"{k}:{v}" for k, v in row["slo"].items()),
        "TPOT basis=" + row["basis"],
    ]
    return [line for detail in details for line in textwrap.wrap(detail, width=TEXT_WRAP_CHARS)]


def _member_lines(member: dict) -> list[str]:
    binding = "/".join(str(member["bindings"][k]) for k in ("matched", "mismatch", "unavailable"))
    line = (
        f"Member {member['ordinal']}: {member['state']}; "
        f"assigned rows={len(member['rows'])}; latency={member['latency']}; "
        f"SLO={member['slo']}; binding matched/mismatch/unavailable={binding}"
    )
    return textwrap.wrap(line, width=TEXT_WRAP_CHARS)


def svg(view: dict, title: str) -> Iterator[str]:
    title_lines = textwrap.wrap(title, width=TITLE_WRAP_CHARS) or [title]
    summary_lines = [
        piece for line in summary(view) for piece in textwrap.wrap(line, width=TEXT_WRAP_CHARS)
    ]
    legends = [
        "Legend: scheduler lag (gray); client queue (amber); "
        "client active interval (blue); first output (red dot).",
        "All times use the shared client clock; active includes server queue, "
        "transport and cancellation drain, NOT server service time.",
        "TPOT is the native per-request mean/basis, NOT every-token latency. "
        "Missing endpoints produce no invented bars.",
    ]
    legend_lines = [
        piece for line in legends for piece in textwrap.wrap(line, width=TEXT_WRAP_CHARS)
    ]
    member_lines = [_member_lines(member) for member in view["members"]]
    row_lines = [_row_lines(row) for row in view["rows"]]
    member_heights = [max(MEMBER_HEIGHT, len(lines) * 16 + 14) for lines in member_lines]
    row_heights = [max(ROW_HEIGHT, 30 + len(lines) * 16 + 18) for lines in row_lines]
    summary_y = 54 + (len(title_lines) - 1) * 24
    legend_y = summary_y + len(summary_lines) * 18 + 16
    content_y = legend_y + len(legend_lines) * 20 + 12
    height = content_y + sum(member_heights) + sum(row_heights) + 60
    yield (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="report-title" '
        'style="width:100%;height:auto;background:#fff;color:#142536">\n'
    )
    yield f'<title id="report-title">{escape(title)}</title>\n'
    yield (
        "<style>text{font-family:monospace;font-size:11px;fill:#142536}"
        ".heading{font-size:21px;font-weight:bold}.state{font-size:13px;font-weight:bold}"
        ".schedule{fill:#7c8194}.queue{fill:#d49413}.active{fill:#2172a5}"
        ".first{fill:#a33450}.baseline{stroke:#c2cad5;stroke-width:1}</style>\n"
    )
    for index, line in enumerate(title_lines):
        yield f'<text x="20" y="{30 + index * 24}" class="heading">{escape(line)}</text>\n'
    for index, line in enumerate(summary_lines):
        yield f'<text x="20" y="{summary_y + index * 18}">{escape(line)}</text>\n'
    for index, line in enumerate(legend_lines):
        yield f'<text x="20" y="{legend_y + index * 20}">{escape(line)}</text>\n'
    y = content_y
    for member, lines, step in zip(view["members"], member_lines, member_heights):
        yield f'<g data-member="{member["ordinal"]}">\n'
        for index, line in enumerate(lines):
            yield f'<text x="20" y="{y + 18 + index * 16}">{escape(line)}</text>\n'
        yield "</g>\n"
        y += step
    scale = max(
        (value for row in view["rows"] for value in row["times"].values() if value is not None),
        default=0,
    )

    def x(value: float) -> float:
        return LEFT + (value / scale) * PLOT_WIDTH if scale > 0 else LEFT

    for row, lines, step in zip(view["rows"], row_lines, row_heights):
        y += 10
        yield f'<g data-row="{row["ordinal"]}" data-state="{row["state"]}">\n'
        yield (
            f'<text x="20" y="{y + 12}" class="state">Row {row["ordinal"]}: {row["state"]}</text>\n'
        )
        yield (
            f'<line x1="{LEFT}" x2="{LEFT + PLOT_WIDTH}" y1="{y + 8}" '
            f'y2="{y + 8}" class="baseline"/>\n'
        )
        for start, end, label in (
            ("scheduled_s", "arrival_s", "schedule"),
            ("arrival_s", "start_s", "queue"),
            ("start_s", "terminal_s", "active"),
        ):
            a, b = row["times"][start], row["times"][end]
            if a is not None and b is not None:
                width = max(0, (b / scale - a / scale) * PLOT_WIDTH) if scale > 0 else 0
                yield (
                    f'<rect data-segment="{label}" x="{x(a):.6f}" y="{y}" '
                    f'width="{width:.6f}" height="14" class="{label}"/>\n'
                )
        if row["times"]["first_output_s"] is not None:
            first = x(row["times"]["first_output_s"])
            yield f'<circle cx="{first:.6f}" cy="{y + 7}" r="3" class="first"/>\n'
        for index, line in enumerate(lines):
            yield f'<text x="20" y="{y + 30 + index * 16}">{escape(line)}</text>\n'
        yield "</g>\n"
        y += step - 10
    yield (
        f'<text x="20" y="{height - 24}">Descriptive client diagnostics only; '
        "no GPU, physical member independence, served-file or performance "
        "qualification.</text>\n</svg>\n"
    )


def markdown_text(value: str) -> str:
    text = html.escape(value, quote=True)
    for char in "\\`*_{}[]()#+.!|":
        text = text.replace(char, "\\" + char)
    return text.encode("ascii", "xmlcharrefreplace").decode("ascii")


def markdown(view: dict, title: str) -> Iterator[str]:
    yield f"# {markdown_text(title)}\n\n"
    yield "\n\n".join(summary(view)) + "\n\n"
    yield (
        "Client active interval includes transport/server queue and drain; "
        "it is not server service time. Native first output includes scheduling/client queue. "
        "TPOT is a named per-request mean, not every-token latency. "
        "Missing values remain unavailable; zero remains zero.\n\n"
    )
    yield (
        "## Original members\n\n| Member | State | Row ordinals | Latency | SLO | "
        "Binding matched/mismatch/unavailable |\n|---|---|---|---|---|---|\n"
    )
    for m in view["members"]:
        cells = [
            m["ordinal"],
            m["state"],
            ", ".join(map(str, m["rows"])) or "none",
            m["latency"],
            m["slo"],
            "/".join(str(m["bindings"][k]) for k in ("matched", "mismatch", "unavailable")),
        ]
        yield "| " + " | ".join(map(str, cells)) + " |\n"
    yield (
        "\n## Complete request population\n\n| Row | Member | State | "
        + " | ".join(TIMES + TIMINGS)
        + " | Tokens | Cap | Latency SLO | First output SLO | TPOT SLO | "
        "Joint SLO | TPOT basis |\n|---|---|---|" + "---|" * (len(TIMES) + len(TIMINGS) + 7) + "\n"
    )
    for row in view["rows"]:
        fields = [
            row["ordinal"],
            row["member"],
            row["state"],
            *row["times"].values(),
            *row["timing"].values(),
            row["tokens"],
            row["cap"],
            *row["slo"].values(),
            row["basis"],
        ]
        yield "| " + " | ".join(number(v) for v in fields) + " |\n"
    yield (
        "\nDescriptive client diagnostics only; no GPU, physical member independence, "
        "served-file authentication or performance qualification.\n"
    )


def chunks(view: dict, title: str, fmt: str) -> Iterator[str]:
    if fmt == "markdown":
        yield from markdown(view, title)
        return
    if fmt == "html":
        yield (
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
        )
        yield (
            "<title>"
            + escape(title)
            + "</title><style>body{margin:0 auto;padding:16px;max-width:1260px;background:#eef2f8}"
            "svg{display:block;max-width:100%}</style></head><body>\n"
        )
    yield from svg(view, title)
    if fmt == "html":
        yield "</body></html>\n"
