#!/usr/bin/env python3
"""yt-lab: how a YouTube watch page behaves from the click on a thumbnail.

Setup (06.10.2026 it found uBlock's medium mode blocking YouTube's BotGuard script):
  python3 -m venv ~/.cache/yt-lab/venv && ~/.cache/yt-lab/venv/bin/pip install selenium
  close Firefox, then copy the profile without tabs and cache:
  rsync -a --exclude 'sessionstore*' --exclude cache2 --exclude lock --exclude .parentlock \
        ~/.config/mozilla/firefox/<profile>/ ~/.cache/yt-lab/profile/
  printf 'user_pref("browser.startup.page", 0);\n' >> ~/.cache/yt-lab/profile/user.js
  ~/.cache/yt-lab/venv/bin/python ytlab.py baseline --runs 4
Variants: --prefs 'k=v,...', --uninstall <addon ids>, --ub-add/--ub-remove 'rule;rule'.
Each run copies the profile afresh (work/), so variants never leak into each other.

Runs Firefox (the user's binary) on a copy of the user's profile, on the real display.
Per run: open the home page, wait for thumbnails, click the first video like a person,
then every 100 ms record: is the video playing, how far the title / player / side column
moved since last sample (layout jumps), DOM size. If the video is not playing 3 s after
the click (or after the previous attempt), click play like the user does, up to 5 times.

  ytlab.py <label> [--runs N] [--prefs k=v,...] [--uninstall id,id] [--url URL]
Prints one JSON line per run to stdout and a summary.
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

LAB = os.path.expanduser("~/.cache/yt-lab")
MASTER = os.path.join(LAB, "profile")
WORK = os.path.join(LAB, "work")
BIN = "/usr/lib/firefox-developer-edition/firefox"
UB = "moz-extension://" + os.environ.get("YTLAB_UBLOCK_UUID", "45088fc6-40f9-465a-bd1d-d4cbfaa89521")

SAMPLE_JS = r"""
const q = s => document.querySelector(s);
const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
                  return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
const v = q('#movie_player video') || q('video');
return {
  t: performance.now(),
  url: location.href,
  playing: !!(v && !v.paused && v.currentTime > 0.05 && v.readyState >= 3),
  ct: v ? v.currentTime : -1,
  paused: v ? v.paused : null,
  rs: v ? v.readyState : -1,
  title: r(q('ytd-watch-metadata h1, #title h1')),
  player: r(q('#movie_player')),
  side: r(q('#secondary #related, #secondary')),
  below: r(q('#below')),
  nodes: document.getElementsByTagName('*').length,
  ad: !!q('.ad-showing'),
};
"""


def moved(a, b):
    if a is None or b is None:
        return 0
    return sum(abs(x - y) for x, y in zip(a, b))


def start(args):
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    subprocess.run(["rsync", "-a", MASTER + "/", WORK + "/"], check=True)
    if args.prefs:
        with open(os.path.join(WORK, "user.js"), "a") as f:
            f.write("\n// yt-lab variant\n")
            for kv in args.prefs.split(","):
                k, v = kv.split("=", 1)
                f.write(f'user_pref("{k}", {v});\n')
    opts = Options()
    opts.binary_location = BIN
    opts.add_argument("-profile")
    opts.add_argument(WORK)
    opts.page_load_strategy = "none"
    env = dict(os.environ, MOZ_USE_XINPUT2="1")
    service = Service("/usr/bin/geckodriver", log_output=os.path.join(LAB, "geckodriver.log"), env=env,
                      service_args=["--allow-system-access"])
    d = webdriver.Firefox(options=opts, service=service)
    d.set_window_rect(0, 0, 1280, 1500)
    if getattr(args, "ub_add", None) or getattr(args, "ub_remove", None):
        main_tab = d.current_window_handle
        open_privileged(d, UB + "/dashboard.html#dyna-rules.html")
        time.sleep(2)
        d.switch_to.frame(d.find_element(By.CSS_SELECTOR, "iframe"))
        res = d.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const add = arguments[0], remove = arguments[1];
            vAPI.messaging.send('dashboard', {what: 'modifyRuleset', permanent: true, toAdd: add, toRemove: remove})
              .then(() => vAPI.messaging.send('dashboard', {what: 'modifyRuleset', permanent: false, toAdd: add, toRemove: remove}))
              .then(() => vAPI.messaging.send('dashboard', {what: 'getRules'}))
              .then(r => done(r.sessionRules || r.temporaryRules || r));""",
            (args.ub_add or "").replace(";", "\n"), (args.ub_remove or "").replace(";", "\n"))
        print("ublock session rules now:", [x for x in res if "behind-the-scene" not in x] if isinstance(res, list) else res, file=sys.stderr)
        d.switch_to.default_content()
        d.close()
        d.switch_to.window(main_tab)
    for ext in filter(None, (args.uninstall or "").split(",")):
        try:
            d.uninstall_addon(ext)
        except Exception as e:                       # noqa: BLE001
            print("uninstall failed", ext, e, file=sys.stderr)
    return d


def open_privileged(d, url):
    """Open an extension page (marionette refuses to navigate there) in a new tab and
    switch to it."""
    before = set(d.window_handles)
    with d.context(d.CONTEXT_CHROME):
        d.execute_script("""
            const tab = gBrowser.addTab(arguments[0],
                {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
            gBrowser.selectedTab = tab;""", url)
    for _ in range(50):
        new = set(d.window_handles) - before
        if new:
            d.switch_to.window(new.pop())
            return
        time.sleep(0.1)
    raise RuntimeError("tab did not open")


def content_cpu():
    t = 0
    for p in subprocess.run(["pgrep", "-f", "firefox-developer-edition/firefox"],
                            capture_output=True, text=True).stdout.split():
        try:
            st = open(f"/proc/{p}/stat").read().split()
            t += int(st[13]) + int(st[14])
        except OSError:
            pass
    return t


def one_run(d, args, n):
    d.get(args.home)
    time.sleep(2.5)                                  # the home page settles, as for a person
    href, t0, cpu0 = None, None, None
    deadline = time.time() + 30
    while time.time() < deadline and t0 is None:
        try:
            els = [e for e in d.find_elements(By.CSS_SELECTOR, "ytd-rich-item-renderer a[href^='/watch']")
                   if e.is_displayed()]
            if len(els) > 2 * n + 1:
                thumb = els[2 * n + 1]
                href = thumb.get_attribute("href")
                cpu0 = content_cpu()
                t0 = time.time()
                thumb.click()
        except Exception:                            # noqa: BLE001 - the grid re-rendered
            t0 = None
        time.sleep(0.3)
    if t0 is None:
        return {"error": "no thumbnails"}
    samples, clicks, last_try = [], 0, t0
    timeline, last_state = [], None
    last_ct, ct_since = None, time.time()
    playing_at = loaded_at = None
    while time.time() - t0 < args.seconds:
        try:
            s = d.execute_script(SAMPLE_JS)
        except Exception:                            # noqa: BLE001 - navigation in progress
            time.sleep(0.1)
            continue
        s["wall"] = round(time.time() - t0, 2)
        samples.append(s)
        state = (s["paused"], s["rs"], s["ct"] > 0.05, s["ad"])
        if state != last_state:
            timeline.append([s["wall"], "paused" if s["paused"] else ("play" if s["paused"] is False else "-"),
                             s["rs"], round(s["ct"], 2)])
            last_state = state
        if s["playing"] and playing_at is None:
            playing_at = s["wall"]
        if s["rs"] >= 1 and loaded_at is None and "watch" in s["url"]:
            loaded_at = s["wall"]
        # click like a sensible person: when the video is paused, or "playing" but not
        # moving for 3 s - never while it is about to start
        if s["ct"] != last_ct:
            last_ct, ct_since = s["ct"], time.time()
        stuck = s["paused"] is True or (time.time() - ct_since > 3)
        if playing_at is None and stuck and time.time() - last_try > 3 and clicks < 5 and "watch" in s["url"]:
            try:
                btn = d.find_element(By.CSS_SELECTOR, "#movie_player .ytp-play-button")
                if btn.is_displayed():
                    btn.click()
                    clicks += 1
                    timeline.append([round(time.time() - t0, 2), "CLICK"])
            except Exception:                        # noqa: BLE001
                pass
            last_try = time.time()
        if playing_at is not None and time.time() - t0 > playing_at + 4:
            break
        time.sleep(0.1)
    cpu = (content_cpu() - cpu0) / os.sysconf("SC_CLK_TCK")
    try:
        d.save_screenshot(os.path.join(LAB, f"shot-{args.label}-{n}.png"))
    except Exception:                                # noqa: BLE001
        pass
    jumps = {k: 0 for k in ("title", "player", "side", "below")}
    jump_px = {k: 0 for k in jumps}
    jump_log = []
    for a, b in zip(samples, samples[1:]):
        for k in jumps:
            m = moved(a[k], b[k])
            if m > 4:
                jumps[k] += 1
                jump_px[k] += m
                jump_log.append([b["wall"], k, a[k], b[k]])
    first = {k: next((s["wall"] for s in samples if s[k]), None) for k in ("title", "player", "side")}
    return {"label": args.label, "run": n, "video": href.split("v=")[-1][:11] if href else None,
            "loaded_at": loaded_at, "playing_at": playing_at, "play_clicks": clicks,
            "ad": any(s["ad"] for s in samples),
            "jumps": jumps, "jump_px": jump_px, "first_seen": first,
            "nodes_end": samples[-1]["nodes"] if samples else None,
            "cpu_s": round(cpu, 2), "samples": len(samples), "timeline": timeline, "jump_log": jump_log}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--seconds", type=float, default=25)
    ap.add_argument("--prefs")
    ap.add_argument("--uninstall")
    ap.add_argument("--ub-add", help="uBlock dynamic rules to add, ';'-separated")
    ap.add_argument("--ub-remove", help="uBlock dynamic rules to remove, ';'-separated")
    ap.add_argument("--home", default="https://www.youtube.com/")
    args = ap.parse_args()
    d = start(args)
    out = []
    try:
        time.sleep(4)                                # extensions start up
        for n in range(args.runs):
            res = one_run(d, args, n)
            out.append(res)
            print(json.dumps(res, ensure_ascii=False), flush=True)
    finally:
        d.quit()
    ok = [r for r in out if "error" not in r]
    pa = [r["playing_at"] for r in ok if r["playing_at"] is not None]
    print(json.dumps({"summary": args.label,
                      "played": f"{len(pa)}/{len(ok)}",
                      "median_play_s": statistics.median(pa) if pa else None,
                      "loaded_at": [r["loaded_at"] for r in ok],
                      "clicks": [r["play_clicks"] for r in ok],
                      "jumps_title": [r["jumps"]["title"] for r in ok],
                      "jumps_player": [r["jumps"]["player"] for r in ok],
                      "jumps_side": [r["jumps"]["side"] for r in ok],
                      "cpu_s": [r["cpu_s"] for r in ok]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
