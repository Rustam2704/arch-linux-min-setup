#!/usr/bin/env python3
"""Test one uBO setting in a fresh disposable Firefox, then quit."""

import argparse
import json
import os
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.bidi.log import Log

from olxubo import WORK, PROFILE, ORIGIN, SEARCH, chrome_navigate, message, prepare


LISTS = ["user-filters", "ublock-filters", "ublock-badware", "ublock-privacy",
         "ublock-unbreak", "ublock-quick-fixes", "easylist", "easyprivacy",
         "urlhaus-1", "plowe-0"]
DYNAMIC = "* * 3p-script block\n* * 3p-frame block"
BAD_CHUNK_FILTER = "/app/static/js/olxeuweb.ninja~script.$script,domain=olx.ua|olx.pl"


def run(variant):
    prepare()
    opts = Options()
    opts.binary_location = str(WORK / "firefox-system-access")
    for arg in ("-headless", "-no-remote", "-profile", str(PROFILE)):
        opts.add_argument(arg)
    opts.set_preference("dom.ipc.processCount", 1)
    opts.set_preference("fission.autostart", False)
    opts.page_load_strategy = "normal" if variant == "dynamic-off" else "eager"
    os.environ.pop("DISPLAY", None)
    os.environ["MOZ_HEADLESS"] = "1"
    driver = webdriver.Firefox(options=opts, service=webdriver.FirefoxService(
        executable_path="/usr/bin/geckodriver", log_output=str(WORK / f"gecko-ubo-{variant}.log")))
    result = {"variant": variant}
    console = []
    try:
        if variant == "ninja-chunk-only":
            _ = driver.network
            Log(driver._websocket_connection).add_event_handler(
                "entry_added", lambda event: console.append(str(event)[:1800]))
        driver.set_page_load_timeout(45)
        chrome_navigate(driver, ORIGIN + "/dashboard.html")
        time.sleep(1.5)
        result["ready"] = message(driver, "", {"what":"readyToFilter"})
        if variant == "dynamic-off":
            message(driver, "dashboard", {"what":"modifyRuleset", "permanent":False,
                                          "toRemove":DYNAMIC, "toAdd":""})
        elif variant.endswith("-off") and variant[:-4] in LISTS:
            key = variant[:-4]
            message(driver, "dashboard", {"what":"applyFilterListSelection", "toRemove":[key]})
            message(driver, "dashboard", {"what":"reloadAllFilters"})
            result["list_off"] = message(driver, "dashboard", {"what":"getLists"})["available"][key]["off"]
        elif variant == "cosmetic-off":
            message(driver, "dashboard", {"what":"modifyRuleset", "permanent":False,
                                          "toRemove":"", "toAdd":"no-cosmetic-filtering: www.olx.ua true"})
        elif variant == "owner-plus-olx-list":
            existing = message(driver, "dashboard", {"what":"readUserFilters"})["content"]
            local_list = (WORK.parents[2] / "assets/browser/ublock-olx.txt").read_text()
            message(driver, "dashboard", {"what":"writeUserFilters", "enabled":True,
                                           "content":existing + "\n" + local_list, "trusted":False})
            message(driver, "dashboard", {"what":"reloadAllFilters"})
        elif variant == "ninja-chunk-only":
            existing = message(driver, "dashboard", {"what":"readUserFilters"})["content"]
            message(driver, "dashboard", {"what":"writeUserFilters", "enabled":True,
                                           "content":existing + "\n" + BAD_CHUNK_FILTER,
                                           "trusted":False})
            message(driver, "dashboard", {"what":"reloadAllFilters"})
            result["filterPresent"] = BAD_CHUNK_FILTER in message(
                driver, "dashboard", {"what":"readUserFilters"})["content"]
        elif variant != "baseline":
            raise ValueError(variant)
        if variant in ("dynamic-off", "cosmetic-off"):
            rules = message(driver, "dashboard", {"what":"getRules"})
            result["effectiveRules"] = [r for r in rules["sessionRules"] if
                                        r.startswith("* * 3p-") or r.startswith("no-cosmetic-filtering:")]

        driver.get(SEARCH)
        if variant == "dynamic-off":
            time.sleep(8)
        driver.execute_script("window.scrollTo(0, 700)")
        deadline = time.monotonic() + 12
        check_count = 0
        while time.monotonic() < deadline:
            image_data = driver.execute_script("""
              const imgs=[...document.images].filter(x=>x.currentSrc.includes('apollo.olxcdn.com'));
              return {title:document.title, count:imgs.length,
                loaded:imgs.filter(x=>x.complete&&x.naturalWidth>0).length,
                scrollY:window.scrollY,
                urls:imgs.slice(0,5).map(x=>({url:x.currentSrc,complete:x.complete,width:x.naturalWidth}))};
            """)
            if image_data["loaded"] >= 3:
                break
            check_count += 1
            if check_count in (4, 8, 12):
                driver.execute_script("window.scrollBy(0, 350)")
            time.sleep(.5)
        result["images"] = image_data
        result["pageHeight"] = driver.execute_script("return document.documentElement.scrollHeight")
        if variant == "ninja-chunk-only":
            time.sleep(8)
            result["after_eight_seconds"] = driver.execute_script("""
              return {pageHeight:document.documentElement.scrollHeight,
                imageCount:document.images.length,
                loaded:[...document.images].filter(x=>x.complete&&x.naturalWidth>0).length,
                text:document.body.innerText.slice(0,200)};
            """)
            result["console"] = [entry for entry in console if
                                 "olxeuweb.ninja~script" in entry or "ChunkLoadError" in entry]
        if variant == "owner-plus-olx-list":
            driver.save_screenshot(str(WORK / "shot-ubo-plus-list.png"))
        print(variant, image_data["loaded"], "/", image_data["count"], flush=True)
    finally:
        (WORK / f"ubo-variant-{variant}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=["baseline", "dynamic-off", "cosmetic-off", "ninja-chunk-only",
                                            "owner-plus-olx-list"] + [k + "-off" for k in LISTS])
    run(parser.parse_args().variant)
