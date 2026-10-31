"""Hosted-only Chromium checks of already-saved installed diagnostic artifacts."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from typing import Any

MAX_PNG_BYTES = 2 * 1024 * 1024


def inspect_page(
    page: Any,
    path: Path,
    *,
    rows: int,
    members: int,
    states: set[str],
    title: str,
    native_exit: int,
    positive: bool,
    zero: bool,
) -> dict:
    errors: list[bool] = []
    page.on("pageerror", lambda _: errors.append(True))
    page.on("console", lambda message: errors.append(True) if message.type == "error" else None)
    page.goto(path.resolve().as_uri(), wait_until="load", timeout=30000)
    assert page.locator("script, img, iframe, foreignObject, a, link").count() == 0
    assert page.locator("[data-row]").count() == rows
    assert page.locator("[data-member]").count() == members
    assert (
        set(page.locator("[data-state]").evaluate_all("els => els.map(el => el.dataset.state)"))
        == states
    )
    assert page.locator("svg > title").text_content() == title
    markup = page.content()
    assert all(
        value not in markup
        for value in ("private-fixture-", "private prompt", "member-0.invalid", "ci/manual-fleet")
    )
    text = page.locator("svg").text_content().lower()
    assert "unavailable" in text and f"native exit: {native_exit}" in text
    assert "not server service" in text
    if members:
        assert "zero_assigned" in text
    if zero:
        assert "tokens=0" in text
    geometry = page.locator("svg").evaluate("""el => {
        const v = el.viewBox.baseVal;
        const boxes = [...el.querySelectorAll('text')].map(x => x.getBBox());
        const widths = [...el.querySelectorAll('rect')].map(x => Number(x.getAttribute('width')));
        return {width:v.width,height:v.height,
            text_inside:boxes.every(b => b.x >= -1 && b.y >= -1 &&
                b.x+b.width <= v.width+1 &&
                b.y+b.height <= v.height+1),
            finite:widths.every(x => Number.isFinite(x) && x >= 0),
            positive:widths.some(x => x > 0)};
    }""")
    assert geometry["text_inside"] and geometry["finite"] and geometry["positive"] is positive, (
        geometry
    )
    last = page.locator(f'[data-row="{rows}"]')
    last.scroll_into_view_if_needed()
    box = last.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0
    assert box["x"] >= -1 and box["x"] + box["width"] <= 1281
    assert box["y"] >= -1 and box["y"] + box["height"] <= 961
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
    )
    assert not errors
    return {
        "rows": rows,
        "members": members,
        "states": len(states),
        "all_text_inside_viewbox": True,
        "finite_chart_geometry": True,
        "has_active_geometry": positive,
        "last_row_visible": True,
        "console_errors": 0,
    }


def accept(directory: Path, screenshots: Path, label: str) -> dict:
    assert not any(
        name == "chimeraforge" or name.startswith("chimeraforge.") for name in sys.modules
    )
    sdk_version = importlib.metadata.version("playwright")
    assert sdk_version == "1.64.1"
    sdk = importlib.import_module("playwright.sync_api")
    traffic: list[bool] = []
    results = []
    screenshots.mkdir(parents=True, exist_ok=True)
    with sdk.sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        browser_version = browser.version
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 960},
                device_scale_factor=1,
                service_workers="block",
            )
            try:

                def refuse(route: Any) -> None:
                    traffic.append(True)
                    route.abort()

                context.route(re.compile(r"^https?://"), refuse)
                from ci_trace_report import TITLE, UNICODE_TITLE

                cases = [
                    (
                        name,
                        6,
                        3,
                        {"completed", "failed", "partial", "cancelled", "not_started"},
                        TITLE,
                        1,
                        True,
                        True,
                    )
                    for name in ("api.html", "cli.html", "api.svg", "cli.svg")
                ]
                cases += [
                    (name, 2, 0, {"completed"}, "Long integer diagnostics", 0, True, False)
                    for name in ("edge-long-api.svg", "edge-long-cli.svg")
                ]
                cases += [
                    (name, 6, 0, {"not_started"}, UNICODE_TITLE, 1, False, False)
                    for name in ("edge-unicode-api.svg", "edge-unicode-cli.svg")
                ]
                for name, rows, members, states, title, exit_code, positive, zero in cases:
                    page = context.new_page()
                    try:
                        result = inspect_page(
                            page,
                            directory / name,
                            rows=rows,
                            members=members,
                            states=states,
                            title=title,
                            native_exit=exit_code,
                            positive=positive,
                            zero=zero,
                        )
                        shot = (
                            "original-html.png"
                            if (label, name) == ("original", "api.html")
                            else "rebuilt-svg.png"
                            if (label, name) == ("rebuilt", "cli.svg")
                            else None
                        )
                        if shot:
                            if name.endswith(".svg"):
                                raw = page.locator("svg").screenshot(
                                    path=str(screenshots / shot), animations="disabled"
                                )
                            else:
                                raw = page.screenshot(
                                    path=str(screenshots / shot),
                                    full_page=True,
                                    animations="disabled",
                                )
                            assert 0 < len(raw) <= MAX_PNG_BYTES
                        results.append({"document": name, **result})
                    finally:
                        page.close()
                assert not traffic
            finally:
                context.close()
        finally:
            browser.close()
    assert not any(
        name == "chimeraforge" or name.startswith("chimeraforge.") for name in sys.modules
    )
    report = {
        "distribution": label,
        "playwright_version": sdk_version,
        "browser_version": browser_version,
        "documents": results,
        "attempted_http_https_requests": len(traffic),
        "scope": (
            "Chromium file rendering and page request interception, "
            "not OS network isolation or inference"
        ),
        "owned_browser_closed": True,
    }
    print(json.dumps({"trace_report_browser": report}))
    return report
