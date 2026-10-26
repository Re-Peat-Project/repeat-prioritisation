#!/usr/bin/env python3
"""Look at the inputs of a run before running it, and write what was found as markdown.

  repeat-subkhg-check --config ../re-peat/sites/14.02-04-05.01_kampar_gaung/subkhg.yaml [--out ../re-peat/sites/14.02-04-05.01_kampar_gaung/reports/kampar_gaung_inputs.md]

For the KHG, rasters (peat depth, DTM), vectors (canals, rivers, lakes, blocks) and the water-table stations it reports
the facts that decided settings in the Kampar - Gaung run: canal classes (for outlet_canal_classes), whether the peat
depth raster has a floor value, how many stations lie inside the KHG with enough coverage.
"""
from __future__ import annotations

import argparse
import logging

import numpy as np

from repeat_common import grid as G
from repeat_prioritisation.common import pipeline
from repeat_prioritisation.subkhg.run import PRESET

log = logging.getLogger("prioritas.check")


def _raster(path, scale=1.0, label="raster"):
    import rasterio
    out = [f"### {label}", f"`{path}`", ""]
    with rasterio.open(path) as s:
        step = max(1, int(max(s.height, s.width) / 2500))
        a = s.read(1, out_shape=(1, s.height // step, s.width // step)).astype("float64")
        nod = s.nodata
        ok = np.isfinite(a) & (a > -1e30) & (a < 1e30)
        if nod is not None and np.isfinite(nod):
            ok &= a != nod
        v = a[ok]
        out += [f"- {s.driver}, {s.width} x {s.height} px, resolution {s.res[0]:.6g} {s.res[1]:.6g}, CRS {s.crs}, nodata {nod}",
                f"- valid pixels in a 1/{step} sample: {v.size:,} ({100 * ok.mean():.0f}% of the sample)"]
        if v.size:
            p = np.percentile(v, [0, 1, 5, 25, 50, 75, 95, 100])
            out.append("- percentiles 0 / 1 / 5 / 25 / 50 / 75 / 95 / 100: " + " / ".join(f"{x:.4g}" for x in p))
            floor = float(np.percentile(v, 1))
            share = float((np.abs(v - floor) < 0.1).mean())
            if share > 0.05:
                out.append(f"- **{100 * share:.0f}% of the valid pixels equal {floor:.1f}**: the raster has a floor value there "
                           "(probably a class such as \"up to this value\"). Anything computed from it is cut off at the low end.")
            if scale != 1.0:
                out.append(f"- with `params.peat_depth_scale` {scale}: median {np.median(v) * scale:.2f} m, "
                           f"5th to 95th percentile {np.percentile(v, 5) * scale:.2f} to {np.percentile(v, 95) * scale:.2f} m")
    return out + [""]


def _vector(path, label, poly, cls_field=None, cls_note=None):
    import geopandas as gpd
    g = gpd.read_file(path)
    out = [f"### {label}", f"`{path}`", "", f"- {len(g):,} features, CRS {g.crs}, geometry {g.geometry.iloc[0].geom_type if len(g) else 'none'}"]
    if len(g) and g.geometry.iloc[0].geom_type.startswith("Line"):
        c = poly.centroid
        utm = G.auto_utm(c.x, c.y)
        g = g.assign(_km=g.to_crs(utm).length / 1000)
        out.append(f"- total length {g['_km'].sum():,.0f} km")
        if cls_field and cls_field in g.columns:
            t = g.groupby(cls_field).agg(n=("_km", "size"), km=("_km", "sum")).round(0)
            out += ["", f"By `{cls_field}`:", "", "| class | segments | km |", "|---|---|---|"]
            out += [f"| {i} | {int(r.n):,} | {r.km:,.0f} |" for i, r in t.iterrows()]
            if cls_note:
                out += ["", cls_note]
    elif len(g) and cls_field and cls_field in g.columns:
        out += ["", f"By `{cls_field}`: " + ", ".join(f"{k}: {v}" for k, v in g[cls_field].astype(str).value_counts().head(8).items())]
    return out + [""]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", help="write the markdown here as well")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    import geopandas as gpd
    cfg = pipeline.load_config(a.config, PRESET, "subkhg")
    khg = gpd.read_file(cfg["khg"]).to_crs(4326)
    poly = khg.geometry.union_all()
    c = poly.centroid
    area = gpd.GeoSeries([poly], crs=4326).to_crs(G.auto_utm(c.x, c.y)).area.iloc[0] / 1e6
    md = [f"# Input check: {a.config}", "", f"KHG `{cfg['khg']}`: {area:,.0f} km2, bounds " + ", ".join(f"{b:.3f}" for b in poly.bounds), ""]
    scale = float(cfg["params"].get("peat_depth_scale", 1.0))
    for key, label, sc in (("peat_depth", "Peat depth raster", scale), ("dtm", "DTM", 1.0)):
        p = cfg["rasters"].get(key)
        if p:
            try:
                md += _raster(p, sc, label)
            except Exception as e:
                md += [f"### {label}", f"could not read `{p}`: {e}", ""]
    sub = cfg["units"].get("subkhg") or {}
    for key, label in (("canals", "Canals"), ("rivers", "Rivers"), ("lakes", "Lakes"), ("blocks", "Existing canal blocks")):
        p = cfg["vectors"].get(key)
        if not p:
            continue
        try:
            field = (sub.get("canal_class_field") or cfg["params"].get("ipg_canal_class_field")) if key == "canals" else ("Jenis" if key == "blocks" else None)
            note = (f"`units.subkhg.outlet_canal_classes` in this config: {sub.get('outlet_canal_classes')}. "
                    "The class names are compared in lower case and must match exactly.") if key == "canals" else None
            md += _vector(p, label, poly, field, note)
        except Exception as e:
            md += [f"### {label}", f"could not read `{p}`: {e}", ""]
    tma_path = (cfg.get("tma") or {}).get("path")
    if tma_path:
        try:
            import pandas as pd
            from repeat_common import tma as TMA
            t = TMA.load(cfg, [])
            m = t.groupby("station_id").agg(lon=("lon", "first"), lat=("lat", "first")).reset_index()
            pts = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.lon, m.lat), crs=4326)
            inside = pts[pts.within(poly)]
            days = t[t.station_id.isin(inside.station_id)].groupby("station_id")["date"].nunique()
            md += ["### Water-table stations (SiTMAT)", f"`{tma_path}`", "",
                   f"- {len(inside)} stations inside the KHG with at least {float((cfg['tma'] or {}).get('min_coverage', 0.5)):.0%} coverage "
                   f"in {t['date'].min().date()} to {t['date'].max().date()}; readings per station: median {int(days.median()) if len(days) else 0} days", ""]
        except Exception as e:
            md += ["### Water-table stations (SiTMAT)", f"could not read `{tma_path}`: {e}", ""]
    text = "\n".join(md)
    print(text)
    if a.out:
        from pathlib import Path
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        log.info("written %s", a.out)


if __name__ == "__main__":
    main()
