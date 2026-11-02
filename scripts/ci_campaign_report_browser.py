"""Hosted-only static whole-campaign checks; no application import or engine call."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_campaigns(
    context: Any, directory: Path, screenshots: Path, label: str, *, png_cap: int
) -> list[dict]:
    from ci_campaign_report import TITLE
    from ci_trace_report import UNICODE_TITLE

    results = []
    for case, count, rows, members in (
        ("serial-complete", 3, 2, 0),
        ("serial-failed", 2, 2, 0),
        ("fleet-complete", 3, 6, 3),
        ("fleet-mixed", 3, 6, 3),
    ):
        title = UNICODE_TITLE if case == "serial-failed" else TITLE
        for mode in ("api", "cli"):
            for fmt in ("html", "svg"):
                name = f"campaign-{case}-{mode}.{fmt}"
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda _: errors.append(True))
                page.on(
                    "console",
                    lambda message: errors.append(True) if message.type == "error" else None,
                )
                try:
                    page.goto(
                        (directory / name).resolve().as_uri(), wait_until="load", timeout=30000
                    )
                    assert page.locator("script,img,iframe,foreignObject,a,link").count() == 0
                    assert page.locator("[data-execution]").count() == count
                    assert page.locator("[data-row]").count() == count * rows
                    assert page.locator("[data-member]").count() == count * members
                    outer = page.locator('svg[aria-labelledby="campaign-title"]')
                    assert outer.count() == 1
                    assert (
                        page.locator('svg[aria-labelledby="campaign-title"] > title').text_content()
                        == title
                    )
                    assert page.locator("[id]").evaluate_all(
                        "els=>new Set(els.map(e=>e.id)).size===els.length"
                    )
                    assert page.locator("[aria-labelledby]").evaluate_all(
                        "els=>els.every(e=>e.getAttribute('aria-labelledby').split(/\\s+/)"
                        ".every(id=>document.getElementById(id)))"
                    )
                    geometry = outer.evaluate("""root=>{
                        const r=root.getBoundingClientRect();
                        const text=[...root.querySelectorAll('text')]
                            .map(e=>e.getBoundingClientRect());
                        const panels=[...root.querySelectorAll('[data-execution] > svg')];
                        const boxes=panels.map(e=>({y:Number(e.getAttribute('y')),
                            h:Number(e.getAttribute('height'))}));
                        const rects=[...root.querySelectorAll('rect')];
                        return {allTextInside:text.every(b=>b.left>=r.left-1&&b.right<=r.right+1
                                &&b.top>=r.top-1&&b.bottom<=r.bottom+1),
                            serialPanels:boxes.every((b,i)=>Number.isFinite(b.y)&&b.h>0
                                &&(!i||boxes[i-1].y+boxes[i-1].h<=b.y)),
                            geometryFinite:rects.every(e=>['x','y','width','height']
                                .every(k=>Number.isFinite(Number(e.getAttribute(k)))
                                    &&Number(e.getAttribute(k))>=0)) };
                    }""")
                    assert all(geometry.values()), geometry
                    text = outer.text_content().lower()
                    assert "no pooled" in text and "server service time" in text
                    assert "private-fixture-" not in text and "member-0.invalid" not in text
                    if case == "fleet-mixed":
                        assert (
                            "tokens=0" in text
                            and "zero_assigned" in text
                            and "declared rows=0" in text
                        )
                    last = page.locator(f'[data-execution="{count}"] [data-row="{rows}"]')
                    last.scroll_into_view_if_needed()
                    box = last.bounding_box()
                    assert box and box["width"] > 0 and box["height"] > 0
                    assert box["x"] >= -1 and box["x"] + box["width"] <= 1281
                    assert box["y"] >= -1 and box["y"] + box["height"] <= 961
                    assert page.evaluate(
                        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"
                    )
                    assert not errors
                    shot = (
                        "campaign-original-html.png"
                        if (label, case, mode, fmt) == ("original", "serial-failed", "api", "html")
                        else "campaign-rebuilt-svg.png"
                        if (label, case, mode, fmt) == ("rebuilt", "fleet-mixed", "cli", "svg")
                        else None
                    )
                    if shot:
                        raw = outer.screenshot(
                            path=str(screenshots / shot), animations="disabled", timeout=30000
                        )
                        assert 0 < len(raw) <= png_cap
                    results.append(
                        {
                            "document": name,
                            "executions": count,
                            "rows_per_execution": rows,
                            "original_members_per_execution": members,
                            "whole_geometry": True,
                            "unique_ids_and_references": True,
                            "last_panel_last_row_visible": True,
                            "console_errors": 0,
                        }
                    )
                finally:
                    page.close()
    return results
