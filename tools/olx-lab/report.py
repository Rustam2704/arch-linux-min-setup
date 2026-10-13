#!/usr/bin/env python3
"""Summarize the immutable browser observations into the requested English report."""

import collections
import json
from pathlib import Path

from olxlab import BLOCK_PATHS, OUTPUT


REPORT = OUTPUT.with_name("measure.md")


def kib(value):
    return "n/a" if value is None else f"{value / 1024:.1f}"


def classify(url):
    lowered = url.lower()
    if "newrelic" in lowered:
        return "analytics"
    if "ninja" in lowered or "tracking." in lowered:
        return "tracking"
    if "laquesis" in lowered:
        return "A-B testing"
    if "chat" in lowered:
        return "chat"
    if "baxter" in lowered or "prebid" in lowered:
        return "ads"
    if "recommend" in lowered or "similar" in lowered:
        return "recommendations"
    if "/app/static/js/" in lowered and "www.olx.ua" in lowered:
        return "core-site (shared chunk; precise contents unknown)"
    return "unknown"


def group(requests, key):
    summary = collections.defaultdict(lambda: [0, 0, 0, 0])
    for request in requests:
        entry = summary[key(request)]
        entry[0] += 1
        entry[1] += request["transfer_bytes"] or 0
        entry[2] += request["decoded_bytes"] or 0
        entry[3] += request["transfer_bytes"] is None
    return sorted(summary.items(), key=lambda item: (-item[1][1], -item[1][0]))


def table_group(grouped):
    lines = ["| Group | Requests | Transfer KiB* | Decoded KiB* | Missing transfer sizes |", "|---|---:|---:|---:|---:|"]
    for name, (count, transfer, decoded, missing) in grouped:
        lines.append(f"| `{name}` | {count} | {kib(transfer)} | {kib(decoded)} | {missing} |")
    return "\n".join(lines)


def make():
    data = json.loads(OUTPUT.read_text())
    runs = sorted((run for run in data["runs"] if not run.get("probe")), key=lambda run: (run["page"], run["variant"]))
    lines = ["# OLX Firefox memory and request measurements", "", "## Pages and method", "",
             "- Search: `https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/`."]
    ad = next((run for run in runs if run["page"] == "ad"), None)
    lines.append(f"- Organic ad: `{ad['requested_url'] if ad else 'not measured'}`; first non-promoted link on the search results page.")
    lines += ["- One new anonymous Firefox Developer Edition profile per run, one headless browser at a time, each inside a systemd user scope with `MemoryMax=1300M` and `MemorySwapMax=0`. The owner's browser and profile were untouched.",
              "- Inventory: WebDriver BiDi `network.beforeRequestSent`, `network.responseCompleted`, and `network.fetchError` (including frames, fetches, and failed requests). Blocking: temporary local Manifest V2 Firefox WebExtension using `webRequest.onBeforeRequest` with `blocking`/`cancel`; BiDi remains read-only. Blocked attempts may be absent from BiDi events; request and script counts are **observed events**, not all blocked attempts. Party is relative strictly to `olx.ua`, so `olxcdn.com` is third-party (but OLX-owned). Sizes: BiDi `response.bytesReceived` (transfer) and `response.content.size`, corrected with same-origin PerformanceResourceTiming `decodedBodySize` where Firefox reports zero. Zero/unknown cross-origin decoded sizes are **not** treated as zero-cost; unknown sizes remain unavailable.",
              "- Memory: `/proc/<pid>/smaps_rollup` Pss and Private_Clean + Private_Dirty (USS), for the `-isForBrowser` child with the largest PSS increase from before navigation. These are per-process values, not per-tab allocations; separate Firefox processes and shared resources are outside this metric. DOM nodes are `document.getElementsByTagName('*').length`.",
              "- Times: page load + 20 s; slow incremental scroll to bottom or 40 steps; then 180 s of no interaction. Idle request count starts after the scroll snapshot. Firefox-internal JS/DOM/image heap categories were not available through this unprivileged WebDriver run.", "",
              "## Summary", "", "*Bytes are network transfer bytes; script count includes attempted/blocked requests, but the byte totals count only completed transfers. Decoded sizes are in the per-script inventory below.*", "",
              "| Page | Variant | Requests | Scripts attempted | Script transfer KiB | Image transfer KiB | PSS KiB (load / scroll / idle) | USS KiB (load / scroll / idle) | DOM nodes (load / scroll / idle) | Idle requests |", "|---|---|---:|---:|---:|---:|---|---|---|---:|"]
    for run in runs:
        requests = run["requests"]
        scripts = [item for item in requests if item["type"] == "script"]
        images = [item for item in requests if item["type"] == "image"]
        snapshots = run["snapshots"]
        pss = " / ".join(str(item["content"]["pss_kib"] if item["content"] else "n/a") for item in snapshots)
        uss = " / ".join(str(item["content"]["uss_kib"] if item["content"] else "n/a") for item in snapshots)
        dom = " / ".join(str(item["dom_nodes"]) for item in snapshots)
        lines.append(f"| {run['page']} | {run['variant']} | {len(requests)} | {len(scripts)} | {kib(sum(item['transfer_bytes'] or 0 for item in scripts))} | {kib(sum(item['transfer_bytes'] or 0 for item in images))} | {pss} | {uss} | {dom} | {run['idle_count']} |")
    lines += ["", "### B: largest surviving scripts across both pages", "", "| Script URL | Transfer KiB | Decoded KiB | Class |", "|---|---:|---:|---|"]
    candidates = [item for run in runs if run["variant"] == "B" for item in run["requests"] if item["type"] == "script" and not item["blocked"]]
    by_url = collections.defaultdict(list)
    for item in candidates:
        by_url[item["url"]].append(item)
    for url, items in sorted(by_url.items(), key=lambda pair: -sum(item["transfer_bytes"] or 0 for item in pair[1]))[:30]:
        transfer = sum(item["transfer_bytes"] or 0 for item in items)
        decoded = sum(item["decoded_bytes"] or 0 for item in items)
        lines.append(f"| `{url}` | {kib(transfer)} | {kib(decoded) if decoded else 'n/a'} | {classify(url)} |")
    lines += ["", "## Blocking rules", "", "- A: none.", "- B: third-party scripts and frames (relative strictly to `olx.ua`); other request types, including third-party beacons and images, were allowed.", "- C: B plus these exact regular-expression URL patterns, except images (images are always exempt):"]
    lines += [f"  - `{pattern}`" for pattern in BLOCK_PATHS]
    lines += ["", "## Host and resource-type inventories", ""]
    for run in runs:
        lines += [f"### {run['page']} / {run['variant']}", "", "**Hosts:**", "", table_group(group(run["requests"], lambda item: item["host"])), "", "**Types:**", "", table_group(group(run["requests"], lambda item: item["type"])), ""]
        idle = collections.Counter(item["host"] for item in run["requests"] if item["phase"] == "idle")
        lines.append("Idle hosts: " + (", ".join(f"`{name}` × {count}" for name, count in idle.most_common()) if idle else "none") + ".")
        checks = run.get("checks", {})
        lines += [f"Page checks: heading `{checks.get('heading')}`; {checks.get('images', '?')} loaded images; first prices {checks.get('prices', [])}; seller controls {checks.get('sellerControls', [])}; service worker controls tab: {checks.get('serviceWorker', '?')}.", ""]
        blocked = collections.Counter(item["blocked"] for item in run["requests"] if item["blocked"])
        if blocked:
            lines.append("Blocked requests by reason: " + ", ".join(f"`{name}` × {count}" for name, count in blocked.items()) + ".\n")
    lines += ["## Every script URL", "", "Decoded body sizes below are n/a if neither BiDi nor the Performance API exposed them; multiple requests to one URL are listed once per run with their counts. `transfer` is the sum of known transfer bytes.", ""]
    for run in runs:
        scripts = collections.defaultdict(list)
        for item in run["requests"]:
            if item["type"] == "script":
                scripts[item["url"]].append(item)
        lines += [f"### {run['page']} / {run['variant']}", "", "| Script URL | Count | Decoded KiB | Transfer KiB | Blocked |", "|---|---:|---:|---:|---|"]
        for url, items in sorted(scripts.items(), key=lambda pair: -sum(item["transfer_bytes"] or 0 for item in pair[1])):
            decoded = sum(item["decoded_bytes"] or 0 for item in items)
            lines.append(f"| `{url}` | {len(items)} | {kib(decoded) if decoded else 'n/a'} | {kib(sum(item['transfer_bytes'] or 0 for item in items))} | {'yes' if any(item['blocked'] for item in items) else 'no'} |")
        lines.append("")
    REPORT.write_text("\n".join(lines))
    print(f"Wrote {REPORT} ({len(runs)} full runs)")


if __name__ == "__main__":
    make()
