#!/usr/bin/env python3
"""Inspect OLX using a disposable copy of the owner's uBlock Origin state."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.bidi.log import Log


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
PROFILE = WORK / "ubo-profile"
OWNER = Path.home() / ".config/mozilla/firefox/ay102hg5.dev-edition-default"
UUID = "45088fc6-40f9-465a-bd1d-d4cbfaa89521"
ORIGIN = f"moz-extension://{UUID}"
SEARCH = "https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/"
OUT = WORK / "ubo-evidence.json"


def prepare():
    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    (PROFILE / "extensions").mkdir(parents=True)
    shutil.copy2(OWNER / "extensions/uBlock0@raymondhill.net.xpi",
                 PROFILE / "extensions/uBlock0@raymondhill.net.xpi")
    for suffix in ("", "^userContextId=4294967295"):
        stem = "moz-extension+++" + UUID + suffix
        src = OWNER / "storage/default" / stem
        dst = PROFILE / "storage/default" / stem
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsync", "-a", str(src) + "/", str(dst) + "/"], check=True)
    settings = {
        "extensions.webextensions.uuids": json.dumps({"uBlock0@raymondhill.net": UUID}),
        "dom.ipc.processCount": 1,
        "fission.autostart": False,
        "browser.cache.disk.enable": False,
        "browser.startup.page": 0,
    }
    (PROFILE / "user.js").write_text("".join(
        f'user_pref({json.dumps(k)}, {json.dumps(v)});\n' for k, v in settings.items()))
    wrapper = WORK / "firefox-system-access"
    wrapper.write_text('#!/bin/sh\nexec /usr/lib/firefox-developer-edition/firefox -remote-allow-system-access "$@"\n')
    wrapper.chmod(0o755)


def message(driver, channel, data):
    result = driver.execute_async_script("""
      const done = arguments[arguments.length-1];
      vAPI.messaging.send(arguments[0], arguments[1]).then(
        value => done(JSON.stringify(value)), e => done(JSON.stringify({error:String(e)})));
    """, channel, data)
    return json.loads(result) if result else None


def chrome_navigate(driver, url, new_tab=False):
    driver.set_context("chrome")
    driver.execute_script("""
      const opts = {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()};
      if (arguments[1]) gBrowser.selectedTab = gBrowser.addTab(arguments[0], opts);
      else gBrowser.selectedBrowser.loadURI(Services.io.newURI(arguments[0]), opts);
    """, url, new_tab)
    driver.set_context("content")


def capture_images(driver):
    return driver.execute_script("""
      return {
        url: location.href, title: document.title,
        pageHeight: document.documentElement.scrollHeight,
        scrollY: scrollY,
        images: [...document.images].map(i => ({src:i.currentSrc || i.src,
          complete:i.complete, width:i.naturalWidth, height:i.naturalHeight,
          visible:!!(i.offsetWidth && i.offsetHeight),
          parent:i.closest('[data-cy],[data-testid]')?.getAttribute('data-cy') ||
                 i.closest('[data-cy],[data-testid]')?.getAttribute('data-testid')})),
        adLinks: [...document.querySelectorAll('a[href*="/d/"],a[href*="/obyavlenie/"]')]
          .slice(0,12).map(a=>a.href),
        resources: performance.getEntriesByType('resource').map(e=>({url:e.name,
          type:e.initiatorType, transfer:e.transferSize, decoded:e.decodedBodySize}))
      };
    """)


def run(debug_addons=False, include_local_list=False, probe_gpt=False):
    WORK.mkdir(exist_ok=True)
    prepare()
    opts = Options()
    opts.binary_location = str(WORK / "firefox-system-access")
    opts.add_argument("-headless")
    opts.add_argument("-no-remote")
    opts.add_argument("-profile")
    opts.add_argument(str(PROFILE))
    opts.set_capability("webSocketUrl", True)
    os.environ.pop("DISPLAY", None)
    os.environ["MOZ_HEADLESS"] = "1"
    driver = webdriver.Firefox(options=opts, service=webdriver.FirefoxService(
        executable_path="/usr/bin/geckodriver", log_output=str(WORK / "gecko-ubo.log")))
    evidence = {"uuid": UUID, "profile": str(PROFILE)}
    requests = []
    ids = {}
    console = []

    def before(event):
        raw = event if isinstance(event, dict) else event.__dict__
        req = raw.get("request") or {}
        entry = {"url": req.get("url"), "type": req.get("destination") or req.get("initiatorType"),
                 "id": req.get("request")}
        ids[entry["id"]] = entry
        requests.append(entry)

    def response(event):
        raw = event if isinstance(event, dict) else event.__dict__
        req = raw.get("request") or {}
        entry = ids.get(req.get("request"))
        if entry:
            data = raw.get("response") or {}
            entry.update(status=data.get("status"), mime=data.get("mimeType"),
                         bytes=data.get("bytesReceived"))

    def fail(event):
        raw = event if isinstance(event, dict) else event.__dict__
        req = raw.get("request") or {}
        entry = ids.get(req.get("request"))
        if entry:
            entry["error"] = raw.get("errorText")

    try:
        driver.set_page_load_timeout(45)
        network = driver.network
        network.add_event_handler("before_request_sent", before)
        network.add_event_handler("response_completed", response)
        network.add_event_handler("fetch_error", fail)
        Log(driver._websocket_connection).add_event_handler(
            "entry_added", lambda event: console.append(str(event)[:1500]))
        if debug_addons:
            chrome_navigate(driver, "about:addons")
            time.sleep(2)
            print("ADDONS", driver.current_url, driver.page_source[:15000], flush=True)
            return
        chrome_navigate(driver, ORIGIN + "/dashboard.html")
        time.sleep(3)
        rules = message(driver, "dashboard", {"what":"getRules"})
        lists = message(driver, "dashboard", {"what":"getLists"})
        evidence["dashboard"] = {"title": driver.title, "url": driver.current_url,
                                 "ready": message(driver, "", {"what":"readyToFilter"}),
                                 "rules": {k:rules[k] for k in ("permanentRules", "sessionRules")},
                                 "selectedLists": list(lists["current"]),
                                 "listDetails": {k:{"title":v.get("title"),"off":v.get("off"),
                                    "entryCount":v.get("entryCount")} for k,v in lists["available"].items()
                                    if k in lists["current"]},
                                 "userFilters": message(driver, "dashboard", {"what":"readUserFilters"}),
                                 "cosmetic": lists["parseCosmeticFilters"]}
        if include_local_list:
            local_list = (WORK.parents[2] / "assets/browser/ublock-olx.txt").read_text()
            original = evidence["dashboard"]["userFilters"]["content"]
            message(driver, "dashboard", {"what":"writeUserFilters", "enabled":True,
                                          "content":original + "\n" + local_list, "trusted":False})
            message(driver, "dashboard", {"what":"reloadAllFilters"})
            evidence["localListApplied"] = True
        print("dashboard", json.dumps({k:str(v)[:200] for k,v in evidence["dashboard"].items()}), flush=True)
        driver.execute_script("window.open(arguments[0], '_blank')", ORIGIN + "/logger-ui.html")
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)
        evidence["logger_start"] = {"url": driver.current_url,
                                    "ownerId": driver.execute_script("return self.logger?.ownerId"),
                                    "ready": driver.execute_script("return !!self.logger")}
        print("logger", evidence["logger_start"], flush=True)
        driver.switch_to.window(driver.window_handles[0])
        driver.get(SEARCH)
        time.sleep(8)
        evidence["search_initial"] = capture_images(driver)
        driver.save_screenshot(str(WORK / ("shot-ubo-plus-list.png" if include_local_list else "shot-ubo.png")))
        for _ in range(8):
            driver.execute_script("window.scrollBy(0, Math.max(250, innerHeight*.5))")
            time.sleep(.75)
        evidence["search_scrolled"] = capture_images(driver)
        driver.save_screenshot(str(WORK / ("shot-ubo-plus-list-scrolled.png" if include_local_list else "shot-ubo-scrolled.png")))
        if probe_gpt:
            evidence["gptProbe"] = driver.execute_async_script("""
              const done=arguments[arguments.length-1];
              const s=document.createElement('script');
              let finished=false;
              const finish=state=>{if(finished)return;finished=true;done(state)};
              s.onload=()=>finish('loaded'); s.onerror=()=>finish('error');
              s.src='https://securepubads.g.doubleclick.net/tag/js/gpt.js';
              document.head.appendChild(s);
              setTimeout(()=>finish('timeout'),4000);
            """)
        ad_urls = [u for u in evidence["search_scrolled"]["adLinks"] if "/d/" in u or "/obyavlenie/" in u]
        evidence["ad_url"] = ad_urls[0] if ad_urls else None
        if evidence["ad_url"]:
            driver.get(evidence["ad_url"])
            time.sleep(7)
            evidence["ad"] = capture_images(driver)
        evidence["requests"] = requests
        evidence["console"] = console
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)
        evidence["logger"] = driver.execute_script("""
          document.querySelector('#loggerExport').click();
          document.querySelector('#modalOverlay [data-radio="format"] [data-radio-item="table"]').click();
          document.querySelector('#modalOverlay [data-radio="encoding"] [data-radio-item="plain"]').click();
          return document.querySelector('#modalOverlay textarea.output').value;
        """)
        print("logger chars", len(evidence["logger"]), flush=True)
    finally:
        target = WORK / "ubo-plus-list-evidence.json" if include_local_list else OUT
        target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        driver.quit()
    print("saved", target, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--debug-addons", action="store_true")
    parser.add_argument("--with-local-list", action="store_true")
    parser.add_argument("--probe-gpt", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepare()
    else:
        run(args.debug_addons, args.with_local_list, args.probe_gpt)
