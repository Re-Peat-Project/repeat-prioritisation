"""Screenshots of the profile map of the national dashboard, served over HTTP so the PMTiles layers load.

  python tests/screenshot_dashboard.py --dir <reports/national_profile> --out <folder> [--khg KHG.16.02.01] [--lat -2.9 --lon 105.64]

Needs playwright and Microsoft Edge. Writes whole-KHG, mid and close zoom views in light and dark, and prints the layer counts
the map found at each zoom. Not a pytest test: it opens a browser.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--khg", default="KHG.16.02.01")
    ap.add_argument("--lon", type=float)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    server = Path(__file__).resolve().parents[2] / "re-peat" / "tools" / "serve_dashboard.py"
    srv = subprocess.Popen([sys.executable, str(server), a.dir, "--port", str(a.port)])
    time.sleep(1.5)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel="msedge", headless=True)
            for theme in ("light", "dark"):
                pg = br.new_page(viewport={"width": 1500, "height": 1000})
                logs = []
                pg.on("console", lambda m: logs.append(m.text) if m.type in ("error", "warning") else None)
                pg.on("response", lambda r: logs.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                pg.goto(f"http://127.0.0.1:{a.port}/dashboard.html#t={theme}&k={a.khg}")
                pg.wait_for_function("window.dashMap&&dashMap()&&dashMap().loaded()", timeout=60000)
                pg.wait_for_timeout(3000)
                pg.locator("#p-map").scroll_into_view_if_needed()
                shots = [("khg", None)]
                if a.lon is not None:
                    shots += [("mid", (a.lon, a.lat, 11)), ("close", (a.lon, a.lat, 13.5))]
                for name, view in shots:
                    if view:
                        pg.evaluate("v=>dashMap().jumpTo({center:[v[0],v[1]],zoom:v[2]})", view)
                    pg.wait_for_function("dashMap().loaded()", timeout=60000)
                    pg.wait_for_timeout(1500)
                    n = pg.evaluate("""()=>Object.fromEntries(["p-peat","p-burn","p-canal-p","p-canal-s","p-canal-t","p-outline"].map(id=>[id,dashMap().queryRenderedFeatures({layers:[id]}).length]))""")
                    print(theme, name, "zoom", round(pg.evaluate("dashMap().getZoom()"), 1), n)
                    pg.locator("#p-map").screenshot(path=str(out / f"{a.khg}_{theme}_{name}.png"))
                if theme == "light":
                    print("console:", logs[:5])
            br.close()
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
