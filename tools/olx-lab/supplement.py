#!/usr/bin/env python3
"""Get public JavaScript decoded sizes where Firefox hides cross-origin timing."""

import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse

from olxlab import OUTPUT, WORK


def fetch_size(url):
    if not urlparse(url).path.lower().endswith((".js", ".mjs")):
        return None
    try:
        response = subprocess.run(
            ["curl", "--compressed", "--location", "--fail", "--silent", "--show-error",
             "--max-time", "12", "--max-filesize", "8000000", "--output", "-", url],
            capture_output=True, timeout=15, check=True,
        )
        return len(response.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def main():
    data = json.loads(OUTPUT.read_text())
    urls = {item["url"] for run in data["runs"] for item in run["requests"]
            if item["type"] == "script" and not item["blocked"] and not item["decoded_bytes"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        sizes = dict(zip(urls, pool.map(fetch_size, urls)))
    for run in data["runs"]:
        for item in run["requests"]:
            if item["type"] == "script" and not item["blocked"] and not item["decoded_bytes"]:
                item["decoded_bytes"] = sizes.get(item["url"])
                if item["decoded_bytes"] is not None:
                    item["decoded_source"] = "anonymous curl --compressed refetch (not in-browser measurement)"
    WORK.mkdir(exist_ok=True)
    pending = WORK / "supplement-pending.json"
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(pending, OUTPUT)
    print(f"Fetched decoded sizes for {sum(value is not None for value in sizes.values())}/{len(urls)} unique public script URLs")


if __name__ == "__main__":
    main()
