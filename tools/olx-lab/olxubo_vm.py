#!/usr/bin/env python3
"""Check whether the owner's copied Violentmonkey state changes the uBO OLX result."""

import json
import os
import shutil
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from olxubo import WORK, PROFILE, OWNER, SEARCH, prepare


VM_ID = "{aecec67f-0d10-4fa7-b7c7-609a2db280cf}"
VM_UUID = "d4d825bb-f08d-4a8b-907e-559992498acc"
UBO_UUID = "45088fc6-40f9-465a-bd1d-d4cbfaa89521"


def run():
    prepare()
    shutil.copy2(OWNER / "extensions" / (VM_ID + ".xpi"), PROFILE / "extensions" / (VM_ID + ".xpi"))
    for suffix in ("", "^userContextId=4294967295"):
        stem = "moz-extension+++" + VM_UUID + suffix
        src = OWNER / "storage/default" / stem
        dst = PROFILE / "storage/default" / stem
        subprocess.run(["rsync", "-a", str(src) + "/", str(dst) + "/"], check=True)
    (PROFILE / "user.js").write_text((PROFILE / "user.js").read_text().replace(
        json.dumps(json.dumps({"uBlock0@raymondhill.net":UBO_UUID})),
        json.dumps(json.dumps({"uBlock0@raymondhill.net":UBO_UUID, VM_ID:VM_UUID}))))

    opts = Options()
    opts.binary_location = str(WORK / "firefox-system-access")
    for arg in ("-headless", "-no-remote", "-profile", str(PROFILE)):
        opts.add_argument(arg)
    os.environ.pop("DISPLAY", None)
    os.environ["MOZ_HEADLESS"] = "1"
    driver = webdriver.Firefox(options=opts, service=webdriver.FirefoxService(
        executable_path="/usr/bin/geckodriver", log_output=str(WORK / "gecko-ubo-vm.log")))
    out = {}
    try:
        driver.set_page_load_timeout(45)
        driver.get(SEARCH)
        time.sleep(8)
        out["initial"] = driver.execute_script("""
          const a=[...document.images].filter(x=>x.currentSrc.includes('apollo.olxcdn.com'));
          return {title:document.title, count:a.length, loaded:a.filter(x=>x.complete&&x.naturalWidth>0).length,
            pageHeight:document.documentElement.scrollHeight,
            lih:[...document.querySelectorAll('img[data-lih-done]')].length};
        """)
        for _ in range(8):
            driver.execute_script("window.scrollBy(0, Math.max(250, innerHeight*.5))")
            time.sleep(.75)
        out["scrolled"] = driver.execute_script("""
          const a=[...document.images].filter(x=>x.currentSrc.includes('apollo.olxcdn.com'));
          return {title:document.title, count:a.length, loaded:a.filter(x=>x.complete&&x.naturalWidth>0).length,
            pageHeight:document.documentElement.scrollHeight,
            lih:[...document.querySelectorAll('img[data-lih-done]')].length};
        """)
        print(out, flush=True)
    finally:
        (WORK / "ubo-with-vm.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        driver.quit()


if __name__ == "__main__":
    run()
