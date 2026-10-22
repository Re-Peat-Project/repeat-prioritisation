#!/usr/bin/env python3
"""Stage 3 of the national profile: the cloud-data layers for the shortlisted KHG.

  python -m national.stage3 select    --config CFG [--top 25]   # top-N boundaries from the operational ranking
  python -m national.run              --config CFG --fetch-only # engine: TerraClimate deficit and rain, WorldCover, JRC water
  python -m national.stage3 summarize --config CFG              # stage3_profile.csv and stage3_yearly.csv

CFG is configs/examples/national_stage3.yaml (the engine's config plus the keys below). Dry spells from ERA5 are not used:
the hourly store is slow to read and 25 km is too coarse to tell neighbouring KHG apart.

Added config keys:  stage3: {profile: <dir with operational/profile.gpkg>, top: 25, peat_extent: <GFW tif>,
                             peat_global: <Global Peatland Map tif>}
"""
from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
import shapely.ops
import yaml
from rasterio.features import geometry_mask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "repeat-common" / "src"))
from national import profile as P  # noqa: E402

log = logging.getLogger("prioritas.stage3")

WORLDCOVER = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare", 70: "snow", 80: "water",
              90: "wetland", 95: "mangrove", 100: "moss"}
DEFAULT = {"stage3": {"top": 25, "peat_extent": None, "peat_global": None, "profile": None}}


def load_cfg(path):
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, copy.deepcopy(DEFAULT))
    P._merge(cfg, yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    base = Path(cfg["out"]).parent          # .../national_profile/stage3
    cfg["_dir"] = base
    cfg["stage3"].setdefault("profile", None)
    return cfg


def profile_dir(cfg):
    return Path(cfg["stage3"]["profile"] or Path(cfg["_dir"]).parent)


def select(cfg, top=None):
    top = top or cfg["stage3"]["top"]
    g = gpd.read_file(profile_dir(cfg) / "operational" / "profile.gpkg")
    t = g[g.skor_risiko.notna()].sort_values("peringkat").head(top)
    out = Path(cfg["khg"])
    out.parent.mkdir(parents=True, exist_ok=True)
    t[["khg_id", "nama", "province", "area_km2", "peringkat", "geometry"]].to_file(out, driver="GPKG")
    log.info("top %d KHG -> %s", len(t), out)


# ------------------------------------------------------------------------------------------------ summaries
def _zonal(path, geom_ll, how="mean", bands=None):
    """Values of a raster inside a WGS84 geometry (cells whose centre is inside; if none, the cell at the centroid)."""
    with rasterio.open(path) as src:
        g = geom_ll
        if src.crs and src.crs.to_epsg() != 4326:
            from pyproj import Transformer
            tf = Transformer.from_crs(4326, src.crs, always_xy=True).transform
            g = shapely.ops.transform(tf, geom_ll)
        w = rasterio.windows.from_bounds(*g.bounds, transform=src.transform)
        c0, r0 = int(np.floor(w.col_off)), int(np.floor(w.row_off))
        c1, r1 = int(np.ceil(w.col_off + w.width)), int(np.ceil(w.row_off + w.height))
        try:   # whole pixels, at least one, even when the KHG is smaller than a cell
            win = rasterio.windows.Window(c0, r0, max(c1 - c0, 1), max(r1 - r0, 1)).intersection(
                rasterio.windows.Window(0, 0, src.width, src.height))
        except rasterio.errors.WindowError:
            return None
        arr = src.read(bands or 1, window=win, masked=False).astype("float64")
        tr = src.window_transform(win)
        shape = arr.shape[-2:]
        inside = ~geometry_mask([g], out_shape=shape, transform=tr, all_touched=False)
        if not inside.any():
            c = g.representative_point()
            r, k = rasterio.transform.rowcol(tr, c.x, c.y)
            inside = np.zeros(shape, bool)
            if 0 <= r < shape[0] and 0 <= k < shape[1]:
                inside[r, k] = True
        nd = src.nodata
        if nd is not None and not (isinstance(nd, float) and np.isnan(nd)):
            arr = np.where(arr == nd, np.nan, arr)
        return arr[..., inside]


def land_cover(cache, geom_ll):
    p = cache / "static" / "worldcover.tif"
    if not p.exists():
        return {}
    v = _zonal(p, geom_ll)
    if v is None:
        return {}
    v = v[np.isfinite(v)]
    out = {f"lc_{n}": float((v == k).mean()) for k, n in WORLDCOVER.items() if k in (10, 20, 30, 40, 50, 80, 90, 95)}
    out["lc_other"] = float(1 - sum(out.values()))
    out["lc_n_cells"] = int(len(v))
    return out


def water_season(cache, geom_ll):
    p = cache / "static" / "water_season.tif"
    if not p.exists():
        return {}
    v = _zonal(p, geom_ll)
    if v is None:
        return {}
    v = v[np.isfinite(v)]
    return {"water_any_frac": float((v > 0).mean()), "water_perm_frac": float((v >= 10).mean())} if len(v) else {}


def peat_extent(cfg, geom_ll):
    s3 = cfg["stage3"]
    out = {}
    if s3.get("peat_extent") and Path(s3["peat_extent"]).exists():
        v = _zonal(s3["peat_extent"], geom_ll)
        if v is not None and len(v):
            seen = v[(v == 0) | (v == 1)]            # 255 = tile not fetched
            out["peat_frac_gfw"] = float((seen == 1).mean()) if len(seen) else np.nan
            out["peat_gfw_coverage"] = float(len(seen) / len(v))
    if s3.get("peat_global") and Path(s3["peat_global"]).exists():
        v = _zonal(s3["peat_global"], geom_ll)
        if v is not None and len(v):
            out["peat_frac_gpm1km"] = float(np.isin(v, (1, 2)).mean())
    return out


def summarize(cfg):
    khg = gpd.read_file(cfg["khg"])
    cache_root = Path(cfg["cache_dir"])
    rows, yearly = [], []
    for r in khg.itertuples():
        cache = cache_root / f"L1_{r.khg_id}"
        row = {"khg_id": r.khg_id}
        # TerraClimate: deficit (dry season) and monthly rain, per year
        for p in sorted((cache / "annual").glob("deficit_*.tif")):
            y = int(p.stem.split("_")[1])
            v = _zonal(p, r.geometry)
            if v is not None and np.isfinite(v).any():
                yearly.append((r.khg_id, y, "deficit_mm", float(np.nanmean(v))))
        for p in sorted((cache / "climate").glob("ppt_*.tif")):
            y = int(p.stem.split("_")[1])
            m = _zonal(p, r.geometry, bands=list(range(1, 13)))
            if m is not None and m.ndim == 2 and np.isfinite(m).any():
                mm = np.nanmean(m, axis=1)           # mean over the KHG per month
                yearly.append((r.khg_id, y, "rain_mm", float(mm.sum())))
                yearly.append((r.khg_id, y, "rain_dry_season_mm", float(mm[np.array(cfg["dry_months"]) - 1].sum())))
        for p in sorted((cache / "annual").glob("ndmi_*.tif")):
            y = int(p.stem.split("_")[1])
            v = _zonal(p, r.geometry)
            if v is not None and np.isfinite(v).any():
                yearly.append((r.khg_id, y, "ndmi", float(np.nanmedian(v))))
        row.update(land_cover(cache, r.geometry))
        row.update(water_season(cache, r.geometry))
        row.update(peat_extent(cfg, r.geometry))
        rows.append(row)
    out = Path(cfg["_dir"])
    prof = pd.DataFrame(rows)
    yr = pd.DataFrame(yearly, columns=["khg_id", "year", "metric", "value"])
    # period means for the table
    for metric, col in (("deficit_mm", "deficit_mean_mm"), ("rain_mm", "rain_mean_mm"), ("rain_dry_season_mm", "rain_dry_mean_mm"),
                        ("ndmi", "ndmi_median")):
        m = yr[yr.metric == metric].groupby("khg_id").value.mean().rename(col)
        prof = prof.merge(m, on="khg_id", how="left")
    prof.to_csv(out / "stage3_profile.csv", index=False, encoding="utf-8")
    yr.to_csv(out / "stage3_yearly.csv", index=False, encoding="utf-8")
    log.info("%d KHG, %d yearly values -> %s", len(prof), len(yr), out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["select", "summarize"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--top", type=int)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_cfg(a.config)
    {"select": lambda: select(cfg, a.top), "summarize": lambda: summarize(cfg)}[a.step]()


if __name__ == "__main__":
    main()
