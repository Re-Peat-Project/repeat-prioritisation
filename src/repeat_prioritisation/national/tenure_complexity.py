#!/usr/bin/env python3
"""Tenure complexity of the peat of each KHG: how many claims overlap on the same land.

  repeat-national-tenure-complexity --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 4] [--force]

`national.tenure` gives every place ONE tenure class (licence > forest area > other land) and so discards the overlaps; this module
keeps them. Every peat grid point of a KHG (same grid and peat as `national.tenure`) records the claims on it. Six claim types:
  licence     inside a business licence (oil palm, PBPH, PPHTR, mining; licence file `inputs.licences`); holders from PERUSAHAAN
  community   inside a social-forestry permit: PPHKM (licence file), Hutan Desa (PPHD) or HTR (`layers.hutan_desa`, `layers.htr`)
  forest      inside the forest estate (Kawasan Hutan, any function but APL); conservation or protection noted
  dmpg        inside a DMPG village (KLH's peat-care village programme)
  occupied    inside PPTPKH (`layers.pptpkh`): land held inside the forest estate that is being settled (settlements, farmland,
              transmigration, TORA allocations): the forest-area part of agrarian reform
  released    inside forest estate released for other uses (`layers.pelepasan`): a past change of status
The layers are fetched by repeat_common.fetch_tenure_layers into $REPEAT_DATA/tenure/.

Rule v1, written 2026-11-16 before any result: indicators c_multi_licence, c_licence_protected, c_licence_community (licence and
PPHKM or DMPG), c_claims_mean (of 4 claim types), c_holders_density (holders per 100 km2 of peat); first amendment (before the
national result) dropped c_multi_licence: the licence file is a clean partition (16,049 touching pairs, no shared area). The v1
national result is kept in <out>/tenure_complexity_v1/.
Rule v2, written 2026-11-16 after the v1 national result and before any v2 result (config key `tenure_complexity`), because v1
missed the main community and occupation claims and two of its indicators did not discriminate (c_licence_protected: 0.1% of
peat nationally; c_holders_density: dominated by small KHG):
  Scored, per KHG:
    c_licence_community  share of peat under a licence and also a social-forestry permit or a DMPG village
    c_contested          share of peat where claims conflict: a licence on PPTPKH or social-forestry land, or forest estate on PPTPKH
    c_claims_mean        mean number of claim types per peat point (0-6)
    c_holders            number of distinct licence holders on the KHG's peat
  Reported, not scored: c_multi_licence, c_licence_protected, c_holders_density, shares of each claim type, peat with no claim,
  peat with 3+ claim types.
  Index: tenure_complexity = mean of the scored indicators' percentile ranks (0-1) among KHG with at least `min_peat_km2` of peat
  (equal weights, provisional); smaller KHG get the indicators but no index. Rank 1 = most complex.
  Missing claims (no layer held): customary forest (hutan adat: the public mirror is empty) and customary territories (BRWA serves
  no polygons; its register is in tenure/brwa_wilayah_adat.csv), PIAPS and the Ministry's newer permit releases (SIGAP, on
  request), BPN land rights (HGU, certificates). Read the index as a lower bound on community and private claims.

Writes <out>/tenure_complexity/:
  tenure_complexity.csv          one row per KHG: peat_km2, the indicators, the reported shares, index and rank
  tenure_complexity_claims.csv   khg_id, n_claim_types (0-6), peat_km2
  tenure_complexity_checks.csv   per KHG: peat points, sum of the claim-count areas against the peat area
  tenure_complexity_meta.json    the rule as configured, layers used, date
Per-KHG results are cached in <out>/tenure_complexity/cache/, so an interrupted run resumes.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P

log = logging.getLogger("prioritas.tenure_complexity")
BUSINESS = ["sawit", "tambang", "pphtr", "pbph"]
INDICATORS = ["c_licence_community", "c_contested", "c_claims_mean", "c_holders"]
DEFAULT_LAYERS = {"hutan_desa": "tenure/hutan_desa.gpkg", "htr": "tenure/htr.gpkg", "pptpkh": "tenure/pptpkh.gpkg", "pelepasan": "tenure/pelepasan.gpkg"}
DEFAULT_RULE = {"version": 2, "indicators": INDICATORS, "weights": "equal", "min_peat_km2": 25, "written": "2026-11-16", "layers": DEFAULT_LAYERS}


def _counts(pts, layer, key=None):
    """Per point: number of polygons of `layer` containing it, and (key given) the set of distinct `key` values."""
    j = gpd.sjoin(pts[["geometry"]], layer[[c for c in ([key] if key else []) + ["geometry"]]], how="inner", predicate="within")
    n = np.zeros(len(pts), int)
    idx = pts.index.get_indexer(j.index)
    np.add.at(n, idx, 1)
    return n, j


def one(cfg, kid, name, g, points=False):
    """points=True also returns the peat points with their claims (for worked examples)."""
    data, inp = Path(cfg["data"]), cfg["inputs"]
    g, lon, lat, pts, _, area_cell, cell = O.base_points(cfg, g)
    pts = pts[pts["peat"]].reset_index(drop=True)
    peat_km2 = len(pts) * area_cell
    out = {"khg_id": kid, "khg": name, "peat_km2": peat_km2, "points": len(pts)}
    if not len(pts):
        return out, {}
    kws, _ = O.read_forest_feg(cfg, g)
    lic = O._read(data / inp["licences"], g, ["IZIN_USAHA", "PERUSAHAAN"])
    lic["cls"] = lic["IZIN_USAHA"].map(O.LIC_VALUE)
    dpg = O.read_dmpg(data / inp["dmpg"], g) if inp.get("dmpg") and (data / inp["dmpg"]).exists() else None
    biz = lic[lic["cls"].isin(BUSINESS)]
    n_lic, jl = _counts(pts, biz, "PERUSAHAAN") if len(biz) else (np.zeros(len(pts), int), pd.DataFrame(columns=["PERUSAHAAN"]))
    has_lic = n_lic > 0
    holders = {str(h).strip().upper() for h in jl["PERUSAHAAN"].dropna() if str(h).strip()}
    rule = {**DEFAULT_RULE, **(cfg.get("tenure_complexity") or {})}
    lays = {**DEFAULT_LAYERS, **(rule.get("layers") or {})}

    def inside(path):
        f = data / path
        if not f.exists():
            raise FileNotFoundError(f"{f} missing: run python -m repeat_common.fetch_tenure_layers")
        lay = O._read(f, g, [])
        return (_counts(pts, lay)[0] > 0) if len(lay) else np.zeros(len(pts), bool)

    pphkm = lic[lic["cls"] == "pphkm"]
    has_pphkm = (_counts(pts, pphkm)[0] > 0) if len(pphkm) else np.zeros(len(pts), bool)
    has_hd, has_htr = inside(lays["hutan_desa"]), inside(lays["htr"])
    community = has_pphkm | has_hd | has_htr
    occupied, released = inside(lays["pptpkh"]), inside(lays["pelepasan"])
    if len(kws):
        jk = gpd.sjoin(pts[["geometry"]], kws[["cls", "geometry"]], how="inner", predicate="within")
        fset = jk.groupby(level=0)["cls"].agg(set)
        cls_at = pd.Series([set()] * len(pts), index=pts.index)
        cls_at.loc[fset.index] = fset
        in_forest = cls_at.map(lambda s: bool(s & {"cons", "hl", "prod", "hpk"})).to_numpy()
        in_protected = cls_at.map(lambda s: bool(s & {"cons", "hl"})).to_numpy()
    else:
        in_forest = in_protected = np.zeros(len(pts), bool)
    in_dmpg = np.zeros(len(pts), bool)
    if dpg is not None and len(dpg):
        in_dmpg[pts.index.get_indexer(gpd.sjoin(pts[["geometry"]], dpg[["geometry"]], how="inner", predicate="within").index.unique())] = True
    claims = sum(x.astype(int) for x in (has_lic, community, in_forest, in_dmpg, occupied, released))
    contested = (has_lic & (occupied | community)) | (in_forest & occupied)
    out.update({
        "c_licence_community": float(np.mean(has_lic & (community | in_dmpg))),
        "c_contested": float(np.mean(contested)),
        "c_claims_mean": float(np.mean(claims)),
        "c_holders": len(holders),
        "c_multi_licence": float(np.mean(n_lic >= 2)),
        "c_licence_protected": float(np.mean(has_lic & in_protected)),
        "c_holders_density": 100.0 * len(holders) / peat_km2,
        "share_licence": float(np.mean(has_lic)),
        "share_pphkm": float(np.mean(has_pphkm)),
        "share_hutan_desa": float(np.mean(has_hd)),
        "share_htr": float(np.mean(has_htr)),
        "share_community": float(np.mean(community)),
        "share_forest_estate": float(np.mean(in_forest)),
        "share_dmpg": float(np.mean(in_dmpg)),
        "share_pptpkh": float(np.mean(occupied)),
        "share_released": float(np.mean(released)),
        "share_no_claim": float(np.mean(claims == 0)),
        "share_3plus_claims": float(np.mean(claims >= 3)),
    })
    cc = {int(k): int(v) * area_cell for k, v in zip(*np.unique(claims, return_counts=True))}
    if points:
        p = pd.DataFrame({"lon": pts.geometry.x, "lat": pts.geometry.y, "licence": has_lic, "community": community, "forest": in_forest,
                          "dmpg": in_dmpg, "pptpkh": occupied, "released": released, "claims": claims, "contested": contested,
                          "licence_community": has_lic & (community | in_dmpg)})
        return out, cc, p, {"cell_m": cell, "holders": sorted(holders)}
    return out, cc


def cache_file(cfg, kid):
    return Path(cfg["out"]) / "tenure_complexity" / "cache" / (re.sub(r"[^\w.-]", "_", kid) + ".json")


def work(args):
    cfg, kid, name, geom = args
    row, cc = one(cfg, kid, name, geom)
    f = cache_file(cfg, kid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"row": row, "claims": cc}, default=lambda v: v.item() if hasattr(v, "item") else float(v)), encoding="utf-8")
    return kid


def index(df, rule):
    ok = df["peat_km2"] >= rule["min_peat_km2"]
    ranks = df.loc[ok, rule["indicators"]].rank(pct=True, method="average")
    df["tenure_complexity"] = np.nan
    df.loc[ok, "tenure_complexity"] = ranks.mean(axis=1)
    df["tenure_complexity_rank"] = df["tenure_complexity"].rank(ascending=False, method="min").astype("Int64")
    return df


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*", help="khg_id to compute (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="recompute KHG that are already cached")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    rule = {**DEFAULT_RULE, **(cfg.get("tenure_complexity") or {})}
    sel = P.load_khg(cfg)
    if a.khg:
        sel = sel[sel.khg_id.isin(a.khg)]
    todo = [(cfg, r.khg_id, r.nama, r.geometry) for r in sel.itertuples() if a.force or not cache_file(cfg, r.khg_id).exists()]
    log.info("%d KHG, %d to compute", len(sel), len(todo))
    if a.workers > 1 and len(todo) > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            for i, kid in enumerate(ex.map(work, todo), 1):
                if i % 25 == 0 or i == len(todo):
                    log.info("%d/%d done (%s)", i, len(todo), kid)
    else:
        for t in todo:
            log.info("%s %s", t[1], t[2])
            work(t)
    rows, claims, chk = [], [], []
    for kid in sel.khg_id:
        d = json.loads(cache_file(cfg, kid).read_text(encoding="utf-8"))
        rows.append(d["row"])
        for k, v in d["claims"].items():
            claims.append({"khg_id": kid, "n_claim_types": int(k), "peat_km2": v})
        chk.append({"khg_id": kid, "points": d["row"]["points"], "peat_km2": d["row"]["peat_km2"],
                    "gap_km2": sum(d["claims"].values()) - d["row"]["peat_km2"]})
    df = index(pd.DataFrame(rows), rule)
    out = Path(cfg["out"]) / "tenure_complexity"
    out.mkdir(parents=True, exist_ok=True)
    df.round(5).to_csv(out / "tenure_complexity.csv", index=False)
    pd.DataFrame(claims).round(4).to_csv(out / "tenure_complexity_claims.csv", index=False)
    pd.DataFrame(chk).round(4).to_csv(out / "tenure_complexity_checks.csv", index=False)
    inp = cfg["inputs"]
    (out / "tenure_complexity_meta.json").write_text(json.dumps({
        "rule": rule, "run": str(date.today()), "peat": str(O.peat_path(cfg)),
        "layers": {**{k: inp.get(k) for k in ("licences", "forest_area", "dmpg")}, **{**DEFAULT_LAYERS, **(rule.get("layers") or {})}},
        "missing_claims": ["hutan adat (mirror empty)", "BRWA customary territory polygons", "PIAPS and newer SIGAP permit releases", "BPN land rights (HGU, certificates)"]},
        indent=1), encoding="utf-8")
    log.info("%d KHG -> %s", len(sel), out)


if __name__ == "__main__":
    main()
