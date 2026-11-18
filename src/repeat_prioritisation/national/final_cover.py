#!/usr/bin/env python3
"""Forest change and burn recovery on the peat of each KHG (amendment 2026-11-18 of the final rule), on the JRC TMF 30 m grid.

  repeat-national-final-cover --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 3]

Inputs (config `final.cover`, paths under $REPEAT_DATA): the per-KHG JRC Tropical Moist Forest files (bands Dec2014, Dec2024 of
projects/JRC/TMF/v1_2024/AnnualChanges: 1 undisturbed forest, 2 degraded, 3 deforested, 4 regrowth, 5 water, 6 other land),
KLH's PPEG analysis (peat LAHAN_GAMB, land cover PL_2022) and KLHK burnt area 2015-2026. Every layer is burned onto the TMF
grid of the KHG (cell centre); shares are of the KHG's peat cells with a TMF value. The 10 KHG without KLH peat use the whole
KHG, as in the rest of the rule.

Writes <out>/final_inputs/cover.csv, one row per KHG:
  tmf_forest_2024, tmf_degraded_2024, tmf_deforested_2024, tmf_regrowth_2024   TMF class shares in Dec 2024
  forest_loss_2015        forest (undisturbed or degraded) in Dec 2014, deforested in Dec 2024
  burn_recovered_share    burned 2015-2023 and forest, degraded forest or regrowth in Dec 2024
  burn_unrecovered_share  burned 2015-2023 and deforested or other land in Dec 2024, not plantation, crop or settlement
  reveg_share             needs replanting: open or degraded cover in PL_2022, or burned and not recovered, or deforested since
                          2015; plantations, crops and settlements in PL_2022 never count (the revegetation label, >= 20%)
  cover_cells             peat cells counted
"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import shapely
import yaml

from repeat_prioritisation.national import profile as P

PPEG = "ALL_Analysis_Integrasi_Tematik__PPEG_Indonesia__April_2026.gpkg"
OPEN = {"Semak Belukar Rawa", "Semak Belukar", "Lahan Terbuka", "Rawa", "Savana/ Padang Rumput", "Savana/Padang Rumput"}
EXCL = lambda s: s in ("Perkebunan", "Hutan Tanaman", "Sawah", "Permukiman") or s.startswith("Pertanian")


def one(args):
    import rasterio
    from rasterio.features import rasterize
    cfg, kid, wkb, whole = args
    data, cv = Path(cfg["data"]), cfg["final"]["cover"]
    f = data / cv["tmf"] / f"{kid}.tif"
    if not f.exists():
        return {"khg_code": kid, "cover_note": "no TMF file"}
    g = shapely.make_valid(shapely.from_wkb(wkb))
    with rasterio.open(f) as src:
        t14, t24 = src.read(1), src.read(2)
        tr, shape = src.transform, (src.height, src.width)
    ras = lambda geoms: rasterize([(x, 1) for x in geoms if x is not None and not x.is_empty], out_shape=shape, transform=tr, fill=0, dtype="uint8").astype(bool) \
        if len(geoms) else np.zeros(shape, bool)
    inkhg = ras([g])
    pp = pyogrio.read_dataframe(data / PPEG, bbox=g.bounds, columns=["LAHAN_GAMB", "PL_2022"])
    if len(pp):
        rp = shapely.get_coordinates(pp.geometry.representative_point())
        pp = pp[shapely.contains_xy(g, rp[:, 0], rp[:, 1])]
    pl = pp.PL_2022.fillna("") if len(pp) else pd.Series([], dtype=str)
    peat = inkhg if whole else ras(pp.geometry.values[(pp.LAHAN_GAMB == "LAHAN GAMBUT").to_numpy()]) & inkhg
    opn = ras(pp.geometry.values[pl.isin(OPEN).to_numpy()]) if len(pp) else np.zeros(shape, bool)
    excl = ras(pp.geometry.values[pl.map(EXCL).to_numpy().astype(bool)]) if len(pp) else np.zeros(shape, bool)
    y0, y1 = cv["burned_years"]
    cols = [f"BA_{y}" for y in range(y0, y1 + 1)]
    ba = pyogrio.read_dataframe(data / cfg["inputs"]["burned"], bbox=g.bounds, columns=cols)
    burned = ras(ba.geometry.values[ba[cols].notna().any(axis=1).to_numpy()]) if len(ba) else np.zeros(shape, bool)
    valid = peat & (t24 > 0)
    n = int(valid.sum())
    if n == 0:
        return {"khg_code": kid, "cover_cells": 0, "cover_note": "no peat cells with TMF"}
    sh = lambda m: float((m & valid).sum()) / n
    forest14 = np.isin(t14, (1, 2))
    rec = np.isin(t24, (1, 2, 4))
    lost = forest14 & (t24 == 3)
    unrec = burned & np.isin(t24, (3, 6)) & ~excl
    return {"khg_code": kid, "cover_cells": n,
            "tmf_forest_2024": sh(t24 == 1), "tmf_degraded_2024": sh(t24 == 2), "tmf_deforested_2024": sh(t24 == 3), "tmf_regrowth_2024": sh(t24 == 4),
            "forest_loss_2015": sh(lost), "burn_recovered_share": sh(burned & rec), "burn_unrecovered_share": sh(unrec),
            "reveg_share": sh((opn | unrec | lost) & ~excl), "cover_note": "whole KHG used as peat" if whole else ""}


def run(cfg, khg=None, workers=3):
    out = Path(cfg["out"]) / "final_inputs"
    k = P.load_khg(cfg)
    k = k[k.khg_id.notna()]
    wk = set()
    wf = Path(cfg["out"]) / "final" / "final_khg.csv"
    if wf.exists():
        f = pd.read_csv(wf)
        if "whole_khg" in f:
            wk = set(f.loc[f.whole_khg.fillna(False).astype(bool), "khg_code"])
    todo = [(cfg, kid, shapely.to_wkb(geom), kid in wk) for kid, geom in zip(k.khg_id, k.geometry.values) if not khg or kid in khg]
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(one, todo, chunksize=2), 1):
            rows.append(r)
            if i % 100 == 0 or i == len(todo):
                print(f"{i}/{len(todo)}", flush=True)
    d = pd.DataFrame(rows)
    p = out / "cover.csv"
    if khg and p.exists():
        old = pd.read_csv(p)
        d = pd.concat([old[~old.khg_code.isin(d.khg_code)], d], ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    d.sort_values("khg_code").to_csv(p, index=False, float_format="%.6g")
    print(f"{p}: {len(d)} KHG, {int(d.cover_cells.fillna(0).gt(0).sum())} with peat cells")
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    run(cfg, set(a.khg) if a.khg else None, a.workers)


if __name__ == "__main__":
    main()
