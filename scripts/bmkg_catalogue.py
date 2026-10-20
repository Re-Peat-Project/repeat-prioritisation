#!/usr/bin/env python3
"""Question: what does BMKG publish as data that the prioritisation could use (HTH, fire danger, drought code)?

Supports the BMKG section of docs/data_sources.md. BMKG's GIS server is an open ArcGIS REST service; its hosts answer
`curl` but refuse Python's urllib (HTTP 403), so this script calls curl.

  python scripts/bmkg_catalogue.py list --pattern "hth|tanpa|dry|kering|fire|drought|hujan"
  python scripts/bmkg_catalogue.py layer Pusat_Meteorologi_Publik/Observation_Index_Fire_Danger_Rating_System/MapServer/31 \\
         --bbox 101.2,0.04,101.29,0.127
  python scripts/bmkg_catalogue.py layer Forecast_Index_Drought_Code/MapServer/51 --bbox 101.2,0.04,101.29,0.127

`list` counts all services and prints those whose name matches. `layer` shows the fields and legend of one layer and, with
--bbox (lon0,lat0,lon1,lat1), the values of its `gridcode` (the index value) inside that box. The layers have no date.
"""
import argparse
import json
import re
import subprocess

BASE = "https://gis.bmkg.go.id/arcgis/rest/services"


def get(path, **params):
    q = "&".join(f"{k}={v}" for k, v in {"f": "json", **params}.items())
    url = f"{BASE}/{path}?{q}" if path else f"{BASE}?{q}"
    r = subprocess.run(["curl", "-s", "-L", "--max-time", "60", url], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": r.stdout[:200] or "no answer"}


def list_services(pattern):
    root = get("")
    svc = [(s["name"], s["type"]) for s in root.get("services", [])]
    for f in root.get("folders", []):
        svc += [(s["name"], s["type"]) for s in get(f).get("services", [])]
    print(f"{len(svc)} services at {BASE}")
    rx = re.compile(pattern, re.I)
    for n, t in svc:
        if rx.search(n):
            print(f"  {n} [{t}]")


def layer(path, bbox):
    li = get(path)
    if "error" in li:
        raise SystemExit(li["error"])
    print("name:", li.get("name"), "| geometry:", li.get("geometryType"), "| fields:", [f["name"] for f in li.get("fields", [])])
    r = (li.get("drawingInfo") or {}).get("renderer") or {}
    for ci in (r.get("classBreakInfos") or r.get("uniqueValueInfos") or []):
        print("  legend class:", ci.get("label"))
    if bbox:
        q = get(f"{path}/query", geometry=bbox, geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
                outFields="gridcode", returnGeometry="false", where="1=1")
        codes = [f["attributes"].get("gridcode") for f in q.get("features", [])]
        codes = [c for c in codes if c is not None]
        print(f"cells in {bbox}: {len(codes)}", f"| gridcode min {min(codes)} max {max(codes)}" if codes else f"| {q.get('error', 'none')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list")
    s.add_argument("--pattern", default=r"hth|tanpa|dry|kering|fire|drought|hujan|rain|aws")
    s = sub.add_parser("layer")
    s.add_argument("path", help="service layer, e.g. Forecast_Index_Drought_Code/MapServer/51")
    s.add_argument("--bbox")
    a = ap.parse_args()
    list_services(a.pattern) if a.cmd == "list" else layer(a.path, a.bbox)


if __name__ == "__main__":
    main()
