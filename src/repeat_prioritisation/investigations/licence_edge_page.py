#!/usr/bin/env python3
"""One HTML page with the evidence of the licence-edge investigation: fire just inside and just outside licence areas, small multiples per KHG, and a map.

  python -m repeat_prioritisation.investigations.licence_edge_page [--out re-peat/reports/licence_edge_investigation.html]

Reads what licence_edge.py wrote, for every KHG folder that has `04_prioritisation/licence_edge/summary.json`:
  band_position.csv, band_year.csv, edge_contrast.csv, cells.csv.gz, summary.json
and writes one self-contained file (D3 and MapLibre inlined; the basemap tiles need internet). Nothing is typed in: rerun after
more KHG have outputs. The high-confidence contrast is computed here from cells.csv.gz with the same block resampling as licence_edge.py,
and the all-confidence contrast is checked against `_khg/licence_edge_contrast.csv`.

Maps: 200 m layers are reprojected to Web Mercator with nearest-neighbour and embedded as class codes (one byte per cell), coloured in the
browser. The fire layer is shown as 1 km blocks (5 x 5 cells, display only: the 200 m counts stay in cells.csv.gz and every chart uses them).
Licence areas are drawn as one dissolved outline, without attributes.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer
from rasterio.transform import Affine
from rasterio.warp import Resampling, calculate_default_transform, reproject

from repeat_common import khg as K
from repeat_prioritisation.investigations import licence_edge as LE

log = logging.getLogger("licence_edge_page")
ASSETS = Path(__file__).resolve().parents[1] / "national" / "assets"
TEMPLATE = Path(__file__).with_name("licence_edge_page.html")
CELL = 200.0

# class edges of the map layers (code 1 is the first class; 0 is no data)
FIRE_EDGES = [0, 1, 3, 10, 30, 100]                  # hotspots per 100 km2 and year, 1 km blocks


def klass(v, edges):
    """Class code 1.. from the edges (left-open), 0 for NaN."""
    v = np.asarray(v, float)
    out = np.searchsorted(np.asarray(edges, float), v, side="left") + 1
    out[~np.isfinite(v)] = 0
    return out.astype(np.uint8)


def label_of(code, edges, unit=""):
    n = len(edges) + 1
    if code == 1:
        return f"< {edges[0]:g}{unit}" if edges[0] != 0 else f"0{unit}"
    if code == n:
        return f"> {edges[-1]:g}{unit}"
    return f"{edges[code - 2]:g} to {edges[code - 1]:g}{unit}"


def edge_contrast(c: pd.DataFrame, col: str):
    """Out/in rate ratio 0-2 km either side of the licence edge per position and canal stratum; col is the per-cell count column."""
    a_km2 = CELL * CELL / 1e6
    rows = []
    c = c.copy()
    c["hs_all"] = c[col]                           # block_ci reads hs_all
    for pos in ["all"] + LE.POS:
        s0 = c if pos == "all" else c[c.position == pos]
        for cn, (ca, cb) in {"all": (0, 1e9), "canal < 1 km": (0, 1000), "canal >= 1 km": (1000, 1e9)}.items():
            s = s0[(s0.canal_m >= ca) & (s0.canal_m < cb)] if s0.canal_m.notna().any() else s0
            inn, out = s[(s.edge_m > -2000) & (s.edge_m <= 0)], s[(s.edge_m > 0) & (s.edge_m <= 2000)]
            if len(inn) < 20 or len(out) < 20:
                continue
            ki, ko = inn.hs_all.sum(), out.hs_all.sum()
            ei, eo = len(inn) * a_km2 * len(LE.YEARS), len(out) * a_km2 * len(LE.YEARS)
            rr = (ko / eo) / (ki / ei) if ki else np.nan
            blo = LE.block_ci(inn, out)
            rows.append({"position": pos, "canal": cn, "inside_km2": len(inn) * a_km2, "outside_km2": len(out) * a_km2, "hotspots_inside": int(ki),
                         "hotspots_outside": int(ko), "rate_ratio_out_over_in": rr, "blocks": int(blo[2]), "lo_block": blo[0], "hi_block": blo[1]})
    return pd.DataFrame(rows)


def clean(v):
    """JSON-safe value: NaN to None, numpy to python."""
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def records(df: pd.DataFrame, cols=None):
    df = df if cols is None else df[cols]
    return [{k: clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def geo(g):
    g = shapely.set_precision(shapely.make_valid(g).simplify(0.0004, preserve_topology=True), 1e-5)
    return json.loads(shapely.to_geojson(g))


def grid_arrays(c: pd.DataFrame, layers: dict[str, np.ndarray]):
    """Place per-cell class codes on the 200 m AEA lattice. Returns arrays [layer,row,col] and the AEA affine."""
    x0, ytop = c.x.min() - CELL / 2, c.y.max() + CELL / 2
    col = np.rint((c.x.to_numpy() - c.x.min()) / CELL).astype(int)
    row = np.rint((c.y.max() - c.y.to_numpy()) / CELL).astype(int)
    h, w = row.max() + 1, col.max() + 1
    out = {}
    for k, v in layers.items():
        a = np.zeros((h, w), np.uint8)
        a[row, col] = v
        out[k] = a
    return out, Affine(CELL, 0, x0, 0, -CELL, ytop), row, col


def to_mercator(arrs: dict, aff: Affine):
    h, w = next(iter(arrs.values())).shape
    left, top = aff.c, aff.f
    right, bottom = left + w * CELL, top - h * CELL
    dst_aff, dw, dh = calculate_default_transform(LE.AEA, "EPSG:3857", w, h, left=left, bottom=bottom, right=right, top=top)
    out = {}
    for k, a in arrs.items():
        d = np.zeros((dh, dw), np.uint8)
        reproject(a, d, src_transform=aff, src_crs=LE.AEA, dst_transform=dst_aff, dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=0, dst_nodata=0)
        out[k] = d
    return out, dst_aff, dw, dh


def enc(a: np.ndarray) -> str:
    return base64.b64encode(gzip.compress(a.tobytes(), 9)).decode()


def fire_blocks(c: pd.DataFrame, col: str, row, col_i):
    """Hotspots per 100 km2 and year in 5 x 5 cell blocks (1 km), written back to the cells of the block that are peat."""
    b = (row // 5).astype(np.int64) * 100000 + (col_i // 5)
    d = pd.DataFrame({"b": b, "n": c[col].to_numpy()})
    g = d.groupby("b").agg(n=("n", "sum"), cells=("n", "size"))
    g["rate"] = np.where(g.cells >= 5, 100 * g.n / (g.cells * (CELL * CELL / 1e6) * len(LE.YEARS)), np.nan)
    return d.b.map(g.rate).to_numpy()


def build_map(code: str, c: pd.DataFrame, folder: Path):
    c = c.reset_index(drop=True)
    hs = c[[f"hs_{y}" for y in LE.YEARS]].sum(axis=1)
    hh = c[[f"hh_{y}" for y in LE.YEARS]].sum(axis=1)
    c["hs_all"], c["hh_all"] = hs, hh
    layers = {"band": np.where(np.isfinite(c.edge_m), LE.band_of(c.edge_m.to_numpy()) + 1, 0).astype(np.uint8),
              "pos": c.position.fillna("").map({"foot": 1, "slope": 2, "crest": 3}).fillna(0).astype(np.uint8).to_numpy()}
    _, aff, row, col_i = grid_arrays(c, {"band": layers["band"]})
    layers["fire"] = klass(fire_blocks(c, "hs_all", row, col_i), FIRE_EDGES)
    layers["fire_h"] = klass(fire_blocks(c, "hh_all", row, col_i), FIRE_EDGES)
    arrs, aff, _, _ = grid_arrays(c, layers)
    arrs, daff, dw, dh = to_mercator(arrs, aff)
    tf = Transformer.from_crs(3857, 4326, always_xy=True)
    w_, n_ = tf.transform(daff.c, daff.f)
    e_, s_ = tf.transform(daff.c + dw * daff.a, daff.f + dh * daff.e)
    inp = folder / "00_inputs"
    import geopandas as gpd
    khg = gpd.read_file(inp / "khg.gpkg").to_crs(4326).geometry.union_all()
    lic = None
    lf = inp / "national" / "izin_usaha_2025.gpkg"
    if lf.exists():
        gl = gpd.read_file(lf).to_crs(4326)
        gl = gl[gl.geometry.notna()]
        if len(gl):
            lic = shapely.union_all(shapely.make_valid(gl.geometry.to_numpy()), grid_size=1e-5)
    return {"w": int(dw), "h": int(dh), "x0": daff.c, "ytop": daff.f, "res": daff.a, "corners": [[w_, n_], [e_, n_], [e_, s_], [w_, s_]],
            "layers": {k: enc(v) for k, v in arrs.items()}, "khg": geo(khg), "lic": geo(lic) if lic is not None else None,
            "bounds": [list(khg.bounds[:2]), list(khg.bounds[2:])]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--khg", nargs="*", default=None, help="folder prefixes to include (default: every folder with licence_edge outputs)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    hub = Path(os.environ.get("REPEAT_HUB") or K.WORKSPACE / "re-peat")
    out = Path(a.out) if a.out else hub / "reports" / "licence_edge_investigation.html"
    names = {r["khg_code"][4:]: (r["name"], r["province"]) for r in K.registry()}
    allc = pd.read_csv(K.root() / "licence_edge_contrast.csv")
    items = []
    for sj in sorted(K.root().glob("*/04_prioritisation/licence_edge/summary.json")):
        folder = sj.parents[2]
        code = folder.name.split("_")[0]
        if a.khg and not any(folder.name.startswith(p) for p in a.khg):
            continue
        d = sj.parent
        summ = json.loads(sj.read_text())
        nm, prov = names.get(code, (folder.name, ""))
        nm = nm.removeprefix("KHG ").replace("Sungai ", "")
        c = pd.read_csv(d / "cells.csv.gz")
        c["position"] = c["position"].fillna("")
        log.info("%s %s", code, nm)
        ec_p = d / "edge_contrast.csv"
        ec = pd.read_csv(ec_p) if ec_p.stat().st_size > 5 else pd.DataFrame()
        item = {"code": code, "folder": folder.name, "name": nm, "province": prov, "peat_km2": summ["peat_km2"], "licence_peat_km2": summ["licence_peat_km2"],
                "licences": summ["licences"], "dem": summ["dem"],
                "bp": records(pd.read_csv(d / "band_position.csv")),
                "by": records(pd.read_csv(d / "band_year.csv"), ["group", "position", "year", "peat_km2", "hotspots", "high_hotspots", "burned_share"])}
        if len(ec):
            ec["reading"] = LE.reading(ec.lo_block, ec.hi_block)
            c = c.assign(hs_sum=c[[f"hs_{y}" for y in LE.YEARS]].sum(axis=1), hh_sum=c[[f"hh_{y}" for y in LE.YEARS]].sum(axis=1))
            hc = edge_contrast(c, "hh_sum")
            hc["reading"] = LE.reading(hc.lo_block, hc.hi_block)
            # parity: the page's own recomputation (all detections) equals the table written by licence_edge.py
            chk = edge_contrast(c, "hs_sum").set_index(["position", "canal"])
            ref = allc[allc.khg_folder == folder.name].set_index(["position", "canal"])
            for col_ in ("rate_ratio_out_over_in", "lo_block", "hi_block"):
                assert np.allclose(ref[col_].reindex(chk.index), chk[col_], equal_nan=True), f"{code}: {col_} differs from licence_edge_contrast.csv"
            item["ec"] = records(ec, ["position", "canal", "inside_km2", "outside_km2", "hotspots_inside", "hotspots_outside", "rate_ratio_out_over_in", "lo_block", "hi_block", "blocks", "reading"])
            item["ec_h"] = records(hc, ["position", "canal", "hotspots_inside", "hotspots_outside", "rate_ratio_out_over_in", "lo_block", "hi_block", "blocks", "reading"])
        item["map"] = build_map(code, c, folder)
        items.append(item)
    style = json.loads((ASSETS / "basemap-positron.json").read_text(encoding="utf-8"))
    data = {"built": str(date.today()), "bands": LE.BAND_LABEL, "pos": LE.POS, "years": LE.YEARS, "dry_years": list(LE.DRY_YEARS), "khg": items,
            "classes": {"fire": [label_of(i, FIRE_EDGES) for i in range(1, len(FIRE_EDGES) + 2)]}, "style": style}
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*ID*/", TEMPLATE.with_name("licence_edge_page_id.js").read_text(encoding="utf-8")).replace("/*APP*/", TEMPLATE.with_name("licence_edge_page.js").read_text(encoding="utf-8"))
    parts = {"/*D3*/": (ASSETS / "d3.v7.9.0.min.js").read_text(encoding="utf-8"), "/*MAPLIBRE_JS*/": (ASSETS / "maplibre-gl.v5.24.0.js").read_text(encoding="utf-8"),
             "/*MAPLIBRE_CSS*/": (ASSETS / "maplibre-gl.v5.24.0.css").read_text(encoding="utf-8")}
    for k, v in parts.items():
        html = html.replace(k, v.replace("</script", "<\\/script"))
    html = html.replace("/*DATA*/", "const DATA=" + json.dumps(data, separators=(",", ":"), allow_nan=False) + ";")
    out.write_text(html, encoding="utf-8")
    log.info("wrote %s (%.1f MB)", out, out.stat().st_size / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
