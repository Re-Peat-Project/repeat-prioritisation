#!/usr/bin/env python3
"""Earth Engine indicators on the peat of each KHG (amendment 2026-11-18 of the final rule).

  repeat-national-final-gee --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 4]

The peat of each KHG is the dissolved KLH peat drawn on the dashboard (<out>/tiles/src/peat.geojsonl, thinned to about 120 m);
the 10 KHG without KLH peat use the whole KHG. Settings in config `final.cover`. Per KHG:
  hansen_loss_2015   share of the peat with tree cover >= 30% in 2000 and loss in 2015-2024 (UMD Hansen GFC v1.12), at 30 m
  ndvi_dry, ndmi_dry median Sentinel-2 SR (harmonized) of the dry months of `dry_year`, clouds masked with Cloud Score+ (cs >= 0.6);
                     NDVI = (B8 - B4) / (B8 + B4), NDMI = (B8 - B11) / (B8 + B11); mean over the peat at 30 m
  ndvi_low_share     share of the peat with that NDVI below `ndvi_low`: open or degraded cover now
  sm_root_dry        SMAP L4 (NASA/SMAP/SPL4SMGP/008) root-zone soil moisture, m3/m3, mean of the dry months of `dry_year`, 11 km
  sm_root_anom       sm_root_dry minus the mean of the same months over `baseline_years`
Requests go in batches of KHG and are cached in <out>/final_inputs/gee_cache/ (resumable). Writes <out>/final_inputs/gee.csv.
"""
from __future__ import annotations

import argparse
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import shapely
import yaml

from repeat_prioritisation.national import profile as P


def images(cv):
    import ee
    y = cv["dry_year"]
    m0, m1 = cv["dry_months"]
    start, end = f"{y}-{m0:02d}-01", f"{y + (m1 == 12)}-{(m1 % 12) + 1:02d}-01"
    gfc = ee.Image("UMD/hansen/global_forest_change_2024_v1_12")
    loss = gfc.select("treecover2000").gte(30).And(gfc.select("lossyear").gte(15)).And(gfc.select("lossyear").lte(24)).rename("hansen_loss_2015")
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start, end).linkCollection(cs, ["cs"])
          .map(lambda i: i.updateMask(i.select("cs").gte(0.6))).median())
    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi_dry")
    ndmi = s2.normalizedDifference(["B8", "B11"]).rename("ndmi_dry")
    low = ndvi.lt(cv["ndvi_low"]).rename("ndvi_low_share")
    smap = ee.ImageCollection("NASA/SMAP/SPL4SMGP/008").select("sm_rootzone")
    dry = lambda yy: smap.filterDate(f"{yy}-{m0:02d}-01", f"{yy + (m1 == 12)}-{(m1 % 12) + 1:02d}-01").mean()
    now = dry(y)
    b0, b1 = cv["baseline_years"]
    base = ee.ImageCollection([dry(yy) for yy in range(b0, b1 + 1)]).mean()
    return {"fine": (loss.addBands(ndvi).addBands(ndmi).addBands(low), 30), "smap": (now.rename("sm_root_dry").addBands(now.subtract(base).rename("sm_root_anom")), 11000)}


def batch(args):
    import ee
    cv, feats, cache, imgs = args
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry(f["geometry"]), {"khg_code": f["k"]}) for f in feats])
    out = {}
    for key, (img, scale) in imgs.items():
        r = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=scale, tileScale=8).getInfo()
        for ft in r["features"]:
            out.setdefault(ft["properties"]["khg_code"], {}).update({k: v for k, v in ft["properties"].items() if k != "khg_code"})
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out), encoding="utf-8")
    return out


def run(cfg, khg=None, workers=4, size=6):
    import ee
    cv = cfg["final"]["cover"]
    ee.Initialize(project=cv.get("ee_project"))
    base = Path(cfg["out"])
    peat = {}
    for ln in (base / "tiles" / "src" / "peat.geojsonl").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            f = json.loads(ln)
            peat[f["properties"]["k"]] = shapely.geometry.shape(f["geometry"])
    k = P.load_khg(cfg)
    k = k[k.khg_id.notna()]
    feats = []
    for kid, g in zip(k.khg_id, k.geometry.values):
        if khg and kid not in khg:
            continue
        geom = peat.get(kid)
        if geom is None or geom.is_empty or geom.area == 0:
            geom = g                                  # no KLH peat: the whole KHG, as in the rule
        geom = shapely.make_valid(geom.simplify(0.0005, preserve_topology=True))
        feats.append({"k": kid, "geometry": shapely.geometry.mapping(geom)})
    imgs = images(cv)
    tag = f"{cv['dry_year']}_{cv['dry_months'][0]}-{cv['dry_months'][1]}"
    jobs = [(cv, feats[i:i + size], base / "final_inputs" / "gee_cache" / f"{tag}_{feats[i]['k']}_{len(feats[i:i + size])}.json", imgs) for i in range(0, len(feats), size)]
    res, errs = {}, []

    def safe(j):
        try:
            return batch(j), None
        except Exception as e:
            return None, f"{j[1][0]['k']}..: {type(e).__name__}: {str(e)[:150]}"
    with ThreadPoolExecutor(workers) as ex:
        for i, (r, e) in enumerate(ex.map(safe, jobs), 1):
            if e:
                errs.append(e)
            else:
                res.update(r)
            if i % 20 == 0 or i == len(jobs):
                print(f"batch {i}/{len(jobs)}", flush=True)
    d = pd.DataFrame([{"khg_code": kk, **v} for kk, v in res.items()])
    p = base / "final_inputs" / "gee.csv"
    if khg and p.exists():
        old = pd.read_csv(p)
        d = pd.concat([old[~old.khg_code.isin(d.khg_code)], d], ignore_index=True)
    d.sort_values("khg_code").to_csv(p, index=False, float_format="%.6g")
    print(f"{p}: {len(d)} KHG; {len(errs)} failed batches (rerun to retry)")
    for e in errs[:10]:
        print("  ", e)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--batch", type=int, default=6)
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    run(cfg, set(a.khg) if a.khg else None, a.workers, a.batch)


if __name__ == "__main__":
    main()
