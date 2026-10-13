#!/usr/bin/env python3
"""Run one anonymous OLX page/variant in a fresh, capped headless Firefox scope."""

import argparse
import collections
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
from urllib.parse import urlparse
import zipfile

from selenium import webdriver
from selenium.webdriver.firefox.options import Options


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
OUTPUT = ROOT.parents[1] / "research/olx/requests.json"
SEARCH = "https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/"
BLOCK_PATHS = [
    r"^https://cdn\.slots\.baxter\.olx\.org/",
    r"^https://tracking\.olx-st\.com/h/",
    r"^https://ninja\.data\.olxcdn\.com/",
    r"^https://laquesis\.data\.olxcdn\.com/",
    r"^https://www\.olx\.ua/app/static/js/newRelic\.[^/]+\.js$",
]


def host(url):
    return (urlparse(url).hostname or "").lower()


def first_party(url):
    hostname = host(url)
    return hostname == "olx.ua" or hostname.endswith(".olx.ua")


def classify(url, destination, variant):
    if variant == "A":
        return None
    if not first_party(url) and destination in ("script", "iframe", "frame"):
        return "third-party script/frame"
    if variant == "C" and destination not in ("image", "imageset"):
        for pattern in BLOCK_PATHS:
            if re.search(pattern, url, re.IGNORECASE):
                return pattern
    return None


def make_addon(variant):
    addon = WORK / f"block-{variant}.zip"
    manifest = {"manifest_version": 2, "name": "OLX lab temporary blocker", "version": "1.0",
                "browser_specific_settings": {"gecko": {"id": "olx-lab@temporary.invalid"}},
                "permissions": ["webRequest", "webRequestBlocking", "<all_urls>"],
                "background": {"scripts": ["background.js"]}}
    script = """const variant = VARIANT;
const extraRules = PATTERNS.map(pattern => new RegExp(pattern, 'i'));
browser.webRequest.onBeforeRequest.addListener(details => {
    const url = new URL(details.url);
    const firstParty = url.hostname === 'olx.ua' || url.hostname.endsWith('.olx.ua');
    if (!firstParty && (details.type === 'script' || details.type === 'sub_frame')) {
        return {cancel: true};
    }
    if (variant === 'C' && details.type !== 'image' && extraRules.some(rule => rule.test(details.url))) {
        return {cancel: true};
    }
    return {};
}, {urls: ['<all_urls>']}, ['blocking']);
""".replace("VARIANT", json.dumps(variant)).replace("PATTERNS", json.dumps(BLOCK_PATHS))
    with zipfile.ZipFile(addon, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("background.js", script)
    return addon


def children(parent):
    mapping = collections.defaultdict(list)
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        try:
            fields = (item / "stat").read_text().split(") ", 1)[1].split()
            mapping[int(fields[1])].append(int(item.name))
        except (OSError, IndexError, ValueError):
            pass
    found = []
    pending = [parent]
    while pending:
        current = pending.pop()
        pending.extend(mapping[current])
        found.append(current)
    return found


def processes(parent):
    result = {}
    for pid in children(parent):
        try:
            cmd = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            if "-isForBrowser" not in cmd:
                continue
            rollup = (Path("/proc") / str(pid) / "smaps_rollup").read_text()
            values = {key: int(value) for key, value in re.findall(r"^(Pss|Private_Clean|Private_Dirty):\s+(\d+) kB", rollup, re.M)}
            result[str(pid)] = {"pss_kib": values.get("Pss"), "uss_kib": values.get("Private_Clean", 0) + values.get("Private_Dirty", 0), "command": cmd[:250]}
        except (OSError, ValueError):
            continue
    return result


def select_content(before, after):
    if not after:
        return None
    return max(after, key=lambda pid: (after[pid]["pss_kib"] or 0) - (before.get(pid, {}).get("pss_kib") or 0))


def update_record(record):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        data = json.loads(OUTPUT.read_text())
    else:
        data = {"method": "Firefox WebDriver BiDi network events; response.bytesReceived and response.content.size; /proc smaps_rollup", "runs": []}
    data["runs"] = [run for run in data["runs"] if (run["page"], run["variant"]) != (record["page"], record["variant"])]
    data["runs"].append(record)
    pending = WORK / "requests-pending.json"
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(pending, OUTPUT)


def snapshot(driver, parent, baseline, name):
    pids = processes(parent)
    selected = select_content(baseline, pids)
    return {"step": name, "timestamp": time.time(), "selected_pid": selected, "content": pids.get(selected),
            "all_content_processes": pids, "dom_nodes": driver.execute_script("return document.getElementsByTagName('*').length"),
            "page_height": driver.execute_script("return document.documentElement.scrollHeight")}


def run(args):
    WORK.mkdir(exist_ok=True)
    profile = WORK / f"profile-{args.page}-{args.variant}"
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(exist_ok=True)
    options = Options()
    options.binary_location = "/usr/lib/firefox-developer-edition/firefox"
    options.add_argument("-headless")
    options.add_argument("-no-remote")
    options.add_argument("-profile")
    options.add_argument(str(profile))
    options.set_preference("dom.ipc.processCount", 1)
    options.set_preference("fission.autostart", False)
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.tabs.remote.autostart", True)
    if args.disable_workers:
        options.set_preference("dom.serviceWorkers.enabled", False)
    options.set_capability("webSocketUrl", True)
    env_display = os.environ.pop("DISPLAY", None)
    os.environ["MOZ_HEADLESS"] = "1"
    print(f"Starting {args.page} {args.variant} DISPLAY={env_display!r} profile={profile}", flush=True)
    driver = webdriver.Firefox(options=options, service=webdriver.FirefoxService(executable_path="/usr/bin/geckodriver", log_output=str(WORK / f"gecko-{args.page}-{args.variant}.log")))
    driver.set_page_load_timeout(45)
    if args.variant != "A":
        driver.install_addon(str(make_addon(args.variant)), temporary=True)
        time.sleep(2)
    lock = threading.Lock()
    requests = {}
    sequence = []
    errors = []
    started = time.monotonic()

    def before(event):
        raw = event if isinstance(event, dict) else event.__dict__
        detail = raw.get("request") or {}
        key = detail.get("request")
        url = detail.get("url", "")
        destination = detail.get("destination") or detail.get("initiatorType") or "unknown"
        with lock:
            entry = {"id": key, "url": url, "host": host(url), "party": "first" if first_party(url) else "third", "type": destination,
                     "method": detail.get("method"), "time_s": round(time.monotonic() - started, 3), "phase": "loading",
                     "transfer_bytes": None, "decoded_bytes": None, "blocked": None}
            requests[key] = entry
            sequence.append(entry)

    def response(event):
        raw = event if isinstance(event, dict) else event.__dict__
        detail = raw.get("request") or {}
        response_data = raw.get("response") or {}
        with lock:
            entry = requests.get(detail.get("request"))
            if entry:
                entry["transfer_bytes"] = response_data.get("bytesReceived")
                entry["decoded_bytes"] = (response_data.get("content") or {}).get("size")
                entry["mime_type"] = response_data.get("mimeType")
                entry["status"] = response_data.get("status")
                entry["from_cache"] = response_data.get("fromCache")

    def failed(event):
        raw = event if isinstance(event, dict) else event.__dict__
        detail = raw.get("request") or {}
        with lock:
            entry = requests.get(detail.get("request"))
            if entry:
                entry["error"] = raw.get("errorText")
                if "BLOCKED" in (entry["error"] or "").upper():
                    entry["blocked"] = classify(entry["url"], entry["type"], args.variant)

    try:
        parent = driver.service.process.pid
        network = driver.network
        network.add_event_handler("before_request_sent", before)
        network.add_event_handler("response_completed", response)
        network.add_event_handler("fetch_error", failed)

        baseline = processes(parent)
        url = SEARCH if args.page == "search" else args.ad_url
        for attempt in range(3):
            try:
                driver.get(url)
                if driver.title != "Problem loading page":
                    break
            except Exception as exception:
                errors.append(f"navigation attempt {attempt + 1}: {exception!s}"[:350])
            if attempt < 2:
                time.sleep(4)
        time.sleep(20)
        snapshots = [snapshot(driver, parent, baseline, "settled_20s")]
        actual_url = driver.current_url
        print(f"loaded {actual_url}, {len(sequence)} requests, {snapshots[-1]['dom_nodes']} nodes", flush=True)
        if snapshots[-1]["dom_nodes"] < 100 or driver.title == "Problem loading page":
            raise RuntimeError(f"Invalid page after navigation: {driver.title}: {errors}")
        candidates = driver.execute_script("""return [...document.querySelectorAll('a[href*="/d/"],a[href*="/obyavlenie/"]')].slice(0,70).map(a=>({url:a.href,title:a.innerText.slice(0,90),parent:a.closest('[data-testid]')?.getAttribute('data-testid'),context:a.closest('[data-cy],article,[data-testid]')?.innerText.slice(0,200)}))""")
        stable_bottom = 0
        last_height = 0
        for step in range(40):
            driver.execute_script("window.scrollBy(0, Math.max(420, innerHeight * .72))")
            time.sleep(1.3)
            position = driver.execute_script("return [window.scrollY,innerHeight,document.documentElement.scrollHeight]")
            if position[0] + position[1] >= position[2] - 12 and position[2] == last_height:
                stable_bottom += 1
            else:
                stable_bottom = 0
            last_height = position[2]
            if stable_bottom >= 2:
                break
        time.sleep(4)
        snapshots.append(snapshot(driver, parent, baseline, "after_scroll"))
        with lock:
            idle_index = len(sequence)
            for entry in sequence[idle_index:]:
                entry["phase"] = "idle"
        print(f"scrolled {step+1} steps, {len(sequence)} requests; idling 180s", flush=True)
        time.sleep(180 if not args.probe else 1)
        snapshots.append(snapshot(driver, parent, baseline, "after_idle"))
        with lock:
            for entry in sequence[idle_index:]:
                entry["phase"] = "idle"
            captured = list(sequence)
        checks = driver.execute_script("""return {title:document.title,heading:document.querySelector('h1')?.textContent.trim(),images:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).length, photos:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).slice(0,12).map(i=>({src:i.currentSrc,width:i.naturalWidth,height:i.naturalHeight})),galleryImages:[...document.images].filter(i=>i.currentSrc.includes('apollo.olxcdn.com')&&i.complete&&i.naturalWidth>0).map(i=>({src:i.currentSrc,width:i.naturalWidth,height:i.naturalHeight})), prices:[...document.querySelectorAll('[data-testid*="price"],[data-cy*="price"]')].slice(0,5).map(x=>x.textContent.trim()), sellerControls:[...document.querySelectorAll('button,[role="button"]')].map(x=>({text:x.textContent.trim().slice(0,100),aria:x.getAttribute('aria-label'),testid:x.getAttribute('data-testid')})).filter(x=>/телефон|номер|повідомл|написати|дзвон|phone|chat/i.test([x.text,x.aria,x.testid].join(' '))).slice(0,20),serviceWorker:!!navigator.serviceWorker?.controller, entries:performance.getEntriesByType('resource').map(e=>({url:e.name,decoded:e.decodedBodySize,encoded:e.encodedBodySize,transfer:e.transferSize,kind:e.initiatorType}))}""")
        entries = collections.defaultdict(list)
        for item in checks.pop("entries"):
            entries[item["url"]].append(item)
        for item in captured:
            matches = entries.get(item["url"], [])
            timing = matches.pop(0) if matches else None
            item["performance_decoded_bytes"] = timing["decoded"] if timing else None
            if not item["decoded_bytes"] and timing and timing["decoded"]:
                item["decoded_bytes"] = timing["decoded"]
            if item["transfer_bytes"] is None and timing and timing["transfer"]:
                item["transfer_bytes"] = timing["transfer"]
        record = {"page": args.page, "variant": args.variant, "requested_url": url, "actual_url": actual_url, "snapshots": snapshots,
                  "requests": captured, "idle_count": len(captured) - idle_index, "checks": checks, "ad_candidates": candidates if args.page == "search" else [],
                  "errors": errors, "scroll_steps": step + 1, "probe": args.probe}
        update_record(record)
        print(f"saved {args.page}/{args.variant}: {len(captured)} requests; idle {record['idle_count']}; selected {snapshots[-1]['selected_pid']}", flush=True)
    finally:
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices="ABC", required=True)
    parser.add_argument("--page", choices=("search", "ad"), required=True)
    parser.add_argument("--ad-url")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--disable-workers", action="store_true")
    arguments = parser.parse_args()
    if arguments.page == "ad" and not arguments.ad_url:
        parser.error("--ad-url required for ad page")
    run(arguments)
