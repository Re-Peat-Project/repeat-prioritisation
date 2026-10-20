#!/usr/bin/env python3
"""Question: does a generated HTML page draw correctly and run without JavaScript errors?

Renders a page with headless Chrome or Edge to a PNG and prints any console errors, so the explanatory pages
(docs/process/subkhg_process.html, docs/process/neraca_air_process.html) can be checked without opening a browser.

  python scripts/render_html.py docs/process/subkhg_process.html data_local/shots/subkhg.png --height 3600
  python scripts/render_html.py docs/process/neraca_air_process.html data_local/shots/neraca_dark.png --dark
  python scripts/render_html.py docs/process/subkhg_process.html data_local/shots/map.png --crop 30,1740,960,2330

--crop x0,y0,x1,y1 cuts a region (pixels of the full render) out of the screenshot. Needs Chrome or Edge installed.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

BROWSERS = ["C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html")
    ap.add_argument("png")
    ap.add_argument("--width", type=int, default=1300)
    ap.add_argument("--height", type=int, default=3200)
    ap.add_argument("--dark", action="store_true", help="render with prefers-color-scheme: dark")
    ap.add_argument("--crop", help="x0,y0,x1,y1 in pixels")
    a = ap.parse_args()
    exe = next((b for b in BROWSERS if os.path.exists(b)), None)
    if not exe:
        sys.exit("no Chrome or Edge found; edit BROWSERS in this script")
    Path(a.png).parent.mkdir(parents=True, exist_ok=True)
    url = Path(a.html).resolve().as_uri()
    cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={a.width},{a.height}", "--virtual-time-budget=6000",
           "--enable-logging=stderr", "--v=0", f"--screenshot={Path(a.png).resolve()}", url]
    if a.dark:
        cmd.insert(2, "--blink-settings=preferredColorScheme=1")
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [ln for ln in r.stderr.splitlines() if "CONSOLE" in ln or "Uncaught" in ln or "Page load failed" in ln]
    print(f"rendered {a.png}" + ("" if not errs else f" with {len(errs)} console message(s):"))
    for e in errs[:10]:
        print("  ", e[:220])
    if a.crop and Path(a.png).exists():
        from PIL import Image
        x0, y0, x1, y1 = (int(v) for v in a.crop.split(","))
        Image.open(a.png).crop((x0, y0, x1, y1)).save(a.png)


if __name__ == "__main__":
    main()
