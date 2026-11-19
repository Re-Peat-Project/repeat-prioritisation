#!/usr/bin/env python3
"""Burned peat from Sentinel-2 per KHG (amendment 2026-11-18 of the final rule; settings in config final.burned_s2).

  repeat-national-final-burned --config configs/examples/national_profile.yaml --year 2024 [--khg ...] [--workers 4]   # calibration grid
  repeat-national-final-burned --config ... --calibrate        # choose (dnbr_min, post_max) against the TreeMap map of calibration_year
  repeat-national-final-burned --config ... --year 2026        # all grid pairs again for the year itself, then burned_s2.csv with the chosen pair

Method (after Gaveau, Descals & Salim 2026, PLOS One 21(4): e0331831, and KLHK's dNBR protocol), in Google Earth Engine:
- Sentinel-2 L2A harmonized, pixels with Cloud Score+ cs_cdf >= 0.6, NBR = (B8 - B12) / (B8 + B12).
- For each month m: before = median NBR of the `pre_months` months before m; after = `post_percentile` percentile of the NBR in m.
  Burned in m: before - after > dnbr_min and after < post_max, and a fire detection near it: within viirs_m of a VIIRS (S-NPP, NOAA-20,
  confidence nominal or high) or within modis_m of a MODIS (FIRMS, confidence >= 30) detection, in the 3 months before m or in m.
- Year: union of the months, then patches smaller than min_patch_ha removed (8-connected), on a 20 m grid in geographic coordinates (Earth Engine cannot parse EPSG:6933; near the equator a 20 m cell is within 1.2 % of 400 m2; areas use the exact pixel area).
- Counted on the KHG's KLH peat (the dashboard peat outline; the whole KHG for the 10 scored without KLH peat), cut into 0.25 degree cells
  so that each request stays small. Every (dnbr_min, post_max) pair of the grid is computed in the same pass, as one band each.
- obs_share: share of the peat with a valid before and after NBR in at least one month (cloud and smoke gaps).

Writes <out>/final_inputs/burned_s2/<year>_grid.csv (KHG x pair: burned_ha, peat_ha, obs_share), calibration.json, and
<out>/final_inputs/burned_s2.csv (u_burned_2026, burned_2026_ha, burned_2026_obs_share) for the year in config `year`.
Requests are cached per batch in <out>/final_inputs/burned_s2/cache (resumable).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
import shapely.geometry
import yaml

from repeat_prioritisation.national import profile as P

CELL_DEG = 0.25
INDONESIA = [94.5, -11.5, 141.5, 6.5]


def pairs(bc):
    return [(t, p) for t in bc["dnbr_grid"] for p in bc["post_max_grid"]]


def band_name(t, p):
    return f"b_{int(round(t * 100)):02d}_{'m' if p < 0 else 'p'}{int(round(abs(p) * 100)):02d}"


def stage_a(bc, year, months=None, mask=None):
    """Per pixel, over the months of `year`: the largest NBR drop (before - after) among the months where the after NBR is below
    post_max and a fire detection is near, one band per post_max (x1000, int16; -1000 = never), plus 'obs' (valid in some month).
    The burned mask of a pair is then (band > dnbr_min), which equals the union of the monthly tests, so the whole grid comes from
    one pass. Each image is read once: one composite per month gives the median (for the before image of later months) and the
    `post_percentile` percentile (the after image); before = median of the three monthly medians (amendment 2026-11-18, before any
    result, for the Earth Engine budget: the 3-month median recomputed for every month read each image three times more)."""
    import ee
    box = ee.Geometry.Rectangle(INDONESIA)
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(box).linkCollection(cs, ["cs_cdf"])

    pm = ee.Image(bc["peat_mask_asset"]) if bc.get("peat_mask_asset") else None   # stored 30 m peat mask: only peat pixels are processed

    def nbr(i):
        m = i.select("cs_cdf").gte(0.6)
        if pm is not None:
            m = m.And(pm.mask())
        return i.normalizedDifference(["B8", "B12"]).rename("nbr").updateMask(m)

    viirs = ee.ImageCollection("NASA/LANCE/SNPP_VIIRS/C2").merge(ee.ImageCollection("NASA/LANCE/NOAA20_VIIRS/C2"))
    v_proj = ee.ImageCollection("NASA/LANCE/NOAA20_VIIRS/C2").first().projection()
    firms = ee.ImageCollection("FIRMS")
    m_proj = firms.first().projection()

    def hot(a, b):
        v = (viirs.filterDate(a, b).map(lambda i: i.select("frp").mask().And(i.select("confidence").gte(1)).rename("h"))
             .max().unmask(0).setDefaultProjection(v_proj).focalMax(bc["viirs_m"], "circle", "meters"))
        m = (firms.filterDate(a, b).map(lambda i: i.select("confidence").gte(30).unmask(0).rename("h"))
             .max().unmask(0).setDefaultProjection(m_proj).focalMax(bc["modis_m"], "circle", "meters"))
        return v.Or(m)

    last = months or 12
    red = ee.Reducer.median().combine(ee.Reducer.percentile([bc["post_percentile"]]), sharedInputs=True)
    comp = {}
    for k in range(1 - bc["pre_months"], last + 1):           # monthly composites, from pre_months before January
        d0 = ee.Date.fromYMD(year, 1, 1).advance(k - 1, "month")
        c = s2.filterDate(d0, d0.advance(1, "month")).map(nbr).reduce(red)
        comp[k] = (c.select(0).rename("med"), c.select(1).rename("low"))
    best = {p: ee.Image(-1.0) for p in bc["post_max_grid"]}
    cal = {}
    cm = bc.get("calibration_months")
    obs = ee.Image(0)
    for k in range(1, last + 1):
        d0 = ee.Date.fromYMD(year, k, 1)
        pre = ee.ImageCollection([comp[k - j][0] for j in range(1, bc["pre_months"] + 1)]).median()
        post = comp[k][1]
        d = pre.subtract(post)
        obs = obs.Or(d.mask().unmask(0))
        h = hot(d0.advance(-3, "month"), d0.advance(1, "month"))
        for p in bc["post_max_grid"]:
            best[p] = best[p].max(d.updateMask(post.lt(p).And(h)).unmask(-1))
        if cm and k == cm:                                  # calibration window (months 1..cm), kept at no extra reading cost
            cal = dict(best)
    bands = [best[p].multiply(1000).round().toInt16().rename(post_band(p)) for p in bc["post_max_grid"]]
    bands += [cal[p].multiply(1000).round().toInt16().rename(post_band(p) + "_cal") for p in cal]
    out = ee.Image.cat(bands + [obs.toByte().rename("obs")])
    return out.updateMask(mask) if mask is not None else out


def post_band(p):
    return f"d_{'m' if p < 0 else 'p'}{int(round(abs(p) * 100)):02d}"


def stage_b(bc, a):
    """From the stage A image: one band per grid pair, burned after the patch filter, plus 'obs'."""
    npx = math.ceil(bc["min_patch_ha"] * 1e4 / bc["scale_m"] ** 2)
    out = []
    for suf in ("", "_cal"):
        for t, p in pairs(bc):
            if suf and not bc.get("calibration_months"):
                continue
            m = a.select(post_band(p) + suf).gt(int(round(t * 1000))).selfMask()
            out.append(m.updateMask(m.connectedPixelCount(npx + 1, True).gte(npx)).unmask(0).rename(band_name(t, p) + suf))
    return ee_cat(out + [a.select("obs")])


def ee_cat(lst):
    import ee
    return ee.Image.cat(lst)


def year_image(bc, year, months=None):
    """Both stages in one expression (interactive use on small areas)."""
    return stage_b(bc, stage_a(bc, year, months))


def regions(cfg, khg=None):
    """KLH peat of each KHG (dashboard outline; whole KHG where scored without KLH peat), cut into 0.25 degree cells."""
    base = Path(cfg["out"])
    peat = {}
    for ln in (base / "tiles" / "src" / "peat.geojsonl").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            f = json.loads(ln)
            peat[f["properties"]["k"]] = shapely.geometry.shape(f["geometry"])
    k = P.load_khg(cfg)
    k = k[k.khg_id.notna()]
    fk = base / "final" / "final_khg.csv"
    wk = set()
    if fk.exists():
        f = pd.read_csv(fk)
        if "whole_khg" in f:
            wk = set(f.loc[f.whole_khg.fillna(False).astype(bool), "khg_code"])
    cells = []
    for kid, g in zip(k.khg_id, k.geometry.values):
        if khg and kid not in khg:
            continue
        geom = g if kid in wk else peat.get(kid)
        if geom is None or geom.is_empty:
            continue
        geom = shapely.make_valid(geom)
        x0, y0, x1, y1 = geom.bounds
        for i in range(int(math.floor(x0 / CELL_DEG)), int(math.ceil(x1 / CELL_DEG))):
            for j in range(int(math.floor(y0 / CELL_DEG)), int(math.ceil(y1 / CELL_DEG))):
                c = geom.intersection(shapely.geometry.box(i * CELL_DEG, j * CELL_DEG, (i + 1) * CELL_DEG, (j + 1) * CELL_DEG))
                if not c.is_empty and c.area > 1e-8:
                    cells.append({"k": kid, "c": f"{i}_{j}", "geometry": shapely.geometry.mapping(shapely.make_valid(c))})
    return cells


def _root(cfg):
    import ee
    proj = cfg["final"]["cover"].get("ee_project")
    ee.Initialize(project=proj)
    root = f"projects/{proj}/assets/repeat_burned_s2"
    try:
        ee.data.getAsset(root)
    except ee.EEException:
        ee.data.createAsset({"type": "FOLDER"}, root)
    return root


def export_a(cfg, year, khg=None, months=None):
    """Stage A as Earth Engine batch exports, one image asset per 1 degree tile holding peat cells (masked to those cells)."""
    import ee
    bc = cfg["final"]["burned_s2"]
    root = _root(cfg)
    cells = regions(cfg, khg)
    tiles = {}
    for c in cells:
        i, j = map(int, c["c"].split("_"))
        tiles.setdefault((i // 4, j // 4), []).append(c)
    out = Path(cfg["out"]) / "final_inputs" / "burned_s2"
    out.mkdir(parents=True, exist_ok=True)
    reg = out / f"{year}_m{months or 12}_tasks.json"
    tasks = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    for (ti, tj), cs in sorted(tiles.items()):
        key = f"a{year}m{months or 12}_{ti}_{tj}".replace("-", "n")
        if key in tasks and tasks[key].get("state") != "FAILED":
            continue
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(c["geometry"])) for c in cs])
        mask = ee.Image(0).paint(fc, 1).selfMask()
        img = stage_a(bc, year, months, mask)
        bb = shapely.geometry.shape({"type": "GeometryCollection", "geometries": [c["geometry"] for c in cs]}).bounds
        t = ee.batch.Export.image.toAsset(image=img, description=key, assetId=f"{root}/{key}", region=ee.Geometry.Rectangle(list(bb)),
                                          scale=bc["scale_m"], crs="EPSG:4326", maxPixels=1e11)
        t.start()
        tasks[key] = {"asset": f"{root}/{key}", "task": t.id, "cells": len(cs)}
    reg.write_text(json.dumps(tasks, indent=0), encoding="utf-8")
    print(f"{len(tasks)} tile exports registered for {year} ({len(cells)} cells)")


def status(cfg, year, months=None):
    import ee
    _root(cfg)
    reg = Path(cfg["out"]) / "final_inputs" / "burned_s2" / f"{year}_m{months or 12}_tasks.json"
    tasks = json.loads(reg.read_text(encoding="utf-8"))
    st, eecu = {}, 0.0
    for k, v in tasks.items():
        s_ = ee.data.getTaskStatus(v["task"])[0]
        v["state"] = s_["state"]
        st[s_["state"]] = st.get(s_["state"], 0) + 1
        eecu += float(s_.get("batch_eecu_usage_seconds") or 0)
        if s_["state"] == "FAILED":
            print("  failed:", k, s_.get("error_message", "")[:160])
    reg.write_text(json.dumps(tasks, indent=0), encoding="utf-8")
    print(year, st, f"EECU-hours so far {eecu / 3600:.1f}")
    return st


def reduce_b(cfg, year, khg=None, months=None, workers=4, size=20):
    """Stage B on the exported tiles: per grid pair (and calibration window), burned ha on the peat of each KHG."""
    import ee
    bc = cfg["final"]["burned_s2"]
    _root(cfg)
    tag = f"{year}_m{months or 12}"
    out = Path(cfg["out"]) / "final_inputs" / "burned_s2"
    tasks = json.loads((out / f"{tag}_tasks.json").read_text(encoding="utf-8"))
    done = [v for v in tasks.values() if v.get("state", "COMPLETED") == "COMPLETED"]   # a partial run uses the finished tiles only
    print(f"{len(done)} of {len(tasks)} tiles finished")
    a = ee.ImageCollection([ee.Image(v["asset"]) for v in done]).mosaic()
    img = stage_b(bc, a)
    bands = img.bandNames().getInfo()
    area = img.multiply(ee.Image.pixelArea()).addBands(ee.Image.pixelArea().updateMask(a.select("obs").mask()).rename("peat"))
    cells = regions(cfg, khg)
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)

    def one(batch):
        f = cache / f"b{tag}_{batch[0]['k']}_{batch[0]['c']}_{len(batch)}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8")), None
        try:
            fc = ee.FeatureCollection([ee.Feature(ee.Geometry(c["geometry"]), {"k": c["k"], "c": c["c"]}) for c in batch])
            r = area.reduceRegions(collection=fc, reducer=ee.Reducer.sum(), scale=bc["scale_m"], crs="EPSG:4326", tileScale=4).getInfo()
            rows = [{"k": x["properties"]["k"], **{b: x["properties"].get(b, 0) for b in bands + ["peat"]}} for x in r["features"]]
        except Exception as e:                       # noqa: BLE001
            return None, f"{batch[0]['k']} {batch[0]['c']}: {type(e).__name__}: {str(e)[:160]}"
        f.write_text(json.dumps(rows), encoding="utf-8")
        return rows, None

    rows, errs = [], []
    jobs = [cells[i:i + size] for i in range(0, len(cells), size)]
    with ThreadPoolExecutor(workers) as ex:
        for i, (r, e) in enumerate(ex.map(one, jobs), 1):
            if e:
                errs.append(e)
            else:
                rows += r
    for e in errs[:10]:
        print("  ", e)
    d = pd.DataFrame(rows)
    g = d.groupby("k")[bands + ["peat"]].sum()
    res = pd.DataFrame({"khg_code": g.index, "peat_ha": g.peat.values / 1e4, "obs_share": (g.obs / g.peat).values})
    for b in bands:
        if b != "obs":
            res[b] = g[b].values / 1e4
    p = out / f"{tag}_grid.csv"
    res.sort_values("khg_code").to_csv(p, index=False, float_format="%.6g")
    print(f"{p}: {len(res)} KHG; {len(errs)} failed batches (rerun to retry)")
    return res


def treemap_ha(cfg, year, codes):
    """Burned ha on the same peat regions in the TreeMap annual Sentinel-2 map of `year` (value = months burned; > 0 counts)."""
    import rasterio
    from rasterio.mask import mask as rmask
    from rasterio.warp import transform_geom
    src_dir = Path(cfg["data"]) / "burned" / "treemap"
    tif = next(src_dir.glob(f"*{year}*.tif"))
    cells = regions(cfg, set(codes))
    out = {}
    with rasterio.open(tif) as src:
        for c in cells:
            gj = transform_geom("EPSG:4326", src.crs, c["geometry"]) if src.crs.to_epsg() != 4326 else c["geometry"]
            try:
                a, tr = rmask(src, [gj], crop=True, filled=True, nodata=0)
            except ValueError:
                continue
            a = a[0]
            if src.crs.is_geographic:          # pixel area from latitude
                rows = np.arange(a.shape[0])
                lat = tr.f + (rows + 0.5) * tr.e
                px = abs(tr.a * tr.e) * (111320.0 ** 2) * np.cos(np.radians(lat))
                ha = float(((a > 0) * px[:, None]).sum() / 1e4)
            else:
                ha = float((a > 0).sum() * abs(tr.a * tr.e) / 1e4)
            out[c["k"]] = out.get(c["k"], 0.0) + ha
    return pd.Series(out)


def lin_ccc(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    mx, my = x.mean(), y.mean()
    return float(2 * np.mean((x - mx) * (y - my)) / (x.var() + y.var() + (mx - my) ** 2))


def calibrate(cfg, months=None):
    """Pick (dnbr_min, post_max): highest Spearman, across the scored KHG, between our January-September burned share of peat and KLHK's
    2026 burned share (u_burned_now); totals are reported, not matched (KLHK may miss burns)."""
    bc = cfg["final"]["burned_s2"]
    out = Path(cfg["out"]) / "final_inputs" / "burned_s2"
    g = pd.read_csv(out / f"{bc['year']}_m{months or 12}_grid.csv")
    f = pd.read_csv(Path(cfg["out"]) / "final" / "final_khg.csv")
    f = f[f.type.notna()][["khg_code", "u_burned_now", "peat_km2"]]
    m = g.merge(f, on="khg_code", how="inner")
    klhk_ha = float((m.u_burned_now.fillna(0) * m.peat_km2 * 100).sum())
    rows = []
    for t, p in pairs(bc):
        b = band_name(t, p)
        sh = m[b + "_cal"] / m.peat_ha
        rows.append({"dnbr_min": t, "post_max": p, "band": b, "spearman_vs_klhk": float(sh.corr(m.u_burned_now, method="spearman")),
                     "ha_jan_sep": float(m[b + "_cal"].sum()), "ha_year_to_date": float(m[b].sum()), "klhk_ha_to_15oct": klhk_ha})
    best = max(rows, key=lambda r: r["spearman_vs_klhk"])
    res = {"method": "highest Spearman with KLHK 2026 burned share, scored KHG", "n_khg": int(len(m)), "grid": rows,
           "chosen": {k: best[k] for k in ("dnbr_min", "post_max", "band", "spearman_vs_klhk", "ha_jan_sep", "ha_year_to_date")}}
    (out / "calibration.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("chosen", res["chosen"])
    return res


def finish(cfg, months=None):
    """burned_s2.csv for the scoring year with the chosen pair (all months to the run date)."""
    bc = cfg["final"]["burned_s2"]
    out = Path(cfg["out"]) / "final_inputs" / "burned_s2"
    ch = json.loads((out / "calibration.json").read_text(encoding="utf-8"))["chosen"]
    d = pd.read_csv(out / f"{bc['year']}_m{months or 12}_grid.csv")
    y = bc["year"]
    r = pd.DataFrame({"khg_code": d.khg_code, f"u_burned_{y}": d[ch["band"]] / d.peat_ha, f"burned_{y}_ha": d[ch["band"]],
                      f"burned_{y}_obs_share": d.obs_share})
    p = Path(cfg["out"]) / "final_inputs" / "burned_s2.csv"
    r.to_csv(p, index=False, float_format="%.6g")
    print(f"{p}: {len(r)} KHG with {ch['band']}; total {r[f'burned_{y}_ha'].sum():,.0f} ha on peat")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--year", type=int, help="default: final.burned_s2.year")
    ap.add_argument("--months", type=int, help="months 1..N of the year (default 12)")
    ap.add_argument("--khg", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--export", action="store_true", help="stage A: submit one Earth Engine export per 1 degree tile")
    ap.add_argument("--status", action="store_true", help="state and compute used by the exports")
    ap.add_argument("--reduce", action="store_true", help="stage B: burned ha per KHG and grid pair from the exported tiles")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--finish", action="store_true")
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    year = a.year or cfg["final"]["burned_s2"]["year"]
    khg = set(a.khg) if a.khg else None
    if a.export:
        export_a(cfg, year, khg, a.months)
    if a.status:
        status(cfg, year, a.months)
    if a.reduce:
        reduce_b(cfg, year, khg, a.months, a.workers)
    if a.calibrate:
        calibrate(cfg, a.months)
    if a.finish:
        finish(cfg, a.months)


if __name__ == "__main__":
    main()
