#!/usr/bin/env python3
"""Ask the copied uBO to identify source lists for OLX logger rules."""

import json
import os
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from olxubo import WORK, PROFILE, ORIGIN, chrome_navigate, message, prepare


def run():
    logger = json.loads((WORK / "ubo-evidence.json").read_text())["logger"]
    rows = [line.split("\t") for line in logger.splitlines() if "\t" in line]
    filters = {}
    for row in rows:
        if len(row) < 8 or not row[1]:
            continue
        filters[row[1]] = {"url": row[7], "type": row[6]}
    prepare()
    opts = Options()
    opts.binary_location = str(WORK / "firefox-system-access")
    for arg in ("-headless", "-no-remote", "-profile", str(PROFILE)):
        opts.add_argument(arg)
    os.environ.pop("DISPLAY", None)
    os.environ["MOZ_HEADLESS"] = "1"
    driver = webdriver.Firefox(options=opts, service=webdriver.FirefoxService(
        executable_path="/usr/bin/geckodriver", log_output=str(WORK / "gecko-ubo-lookup.log")))
    out = {}
    try:
        chrome_navigate(driver, ORIGIN + "/dashboard.html")
        time.sleep(1.5)
        for raw, details in filters.items():
            if raw.startswith("##"):
                query = {"what":"listsFromCosmeticFilter", "rawFilter":raw,
                         "url":details["url"], "dochn":"www.olx.ua", "tophn":"www.olx.ua"}
            else:
                query = {"what":"listsFromNetFilter", "rawFilter":raw}
            out[raw] = message(driver, "dashboard", query)
        (WORK / "ubo-filter-sources.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print("looked up", len(out), "unique logger rules", flush=True)
    finally:
        driver.quit()


if __name__ == "__main__":
    run()
