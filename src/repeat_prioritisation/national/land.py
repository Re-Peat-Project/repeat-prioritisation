#!/usr/bin/env python3
"""Land status of every KHG: kawasan hutan (forest area function), peat function and DMPG villages, crossed with peat,
burned peat (2015-2025) and this year's hotspots.

  repeat-national-land --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 4] [--force]

The same method and rows as `national.overlay` (regular grid of points per KHG, areas are point counts times the cell area)
without the licence, ring and map layers, so it runs for all 865 KHG from the layers in `_data`. Results of each KHG are cached
in <out>/land/cache/<khg_id>.json and reused unless --force, so an interrupted run resumes. Writes, in <out>/land/:
  land_summary.csv        one row per KHG, layer (forest, feg, dmpg, dmpg_prog, dmpg_forest) and class: area, peat, burned peat, hotspots
  land_dmpg_villages.csv  one row per DMPG village and KHG: area, peat, burned peat and hotspots inside the KHG
  land_checks.csv         per KHG: class areas against the KHG area, hotspot counts by class against the hotspots inside
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P

log = logging.getLogger("prioritas.land")
LAYER_TOTAL = ("forest", "feg")       # classes of these layers add up to the whole KHG


def load_cfg(path):
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    for k, v in O.DEFAULT["inputs"].items():
        cfg["inputs"].setdefault(k, v)
    return cfg


def cache_file(cfg, kid):
    return Path(cfg["out"]) / "land" / "cache" / (re.sub(r"[^\w.-]", "_", kid) + ".json")


def work(args):
    cfg, kid, name, geom = args
    f = cache_file(cfg, kid)
    rows, vil, meta = O.one_land(cfg, kid, name, geom)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"rows": rows, "vil": vil, "meta": meta}, default=float), encoding="utf-8")
    return kid


def collect(cfg, ids):
    rows, vil, chk = [], [], []
    for kid in ids:
        d = json.loads(cache_file(cfg, kid).read_text(encoding="utf-8"))
        rows += d["rows"]
        vil += d["vil"]
        m, r = d["meta"], pd.DataFrame(d["rows"])
        c = {"khg_id": kid, "khg_km2_grid": m["khg_km2_grid"], "cell_m": m["cell_m"], "hs_inside": m["hs_inside"]}
        for layer in LAYER_TOTAL:
            s = r[r.layer == layer]
            c[f"{layer}_area_gap"] = float(s.area_km2.sum() - m["khg_km2_grid"])
            c[f"{layer}_hs_gap"] = int(s.hs_now.sum() - m["hs_inside"])
        chk.append(c)
    return pd.DataFrame(rows), pd.DataFrame(vil), pd.DataFrame(chk)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*", help="khg_id to compute (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="recompute KHG that are already cached")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_cfg(a.config)
    khg = P.load_khg(cfg)
    if a.khg:
        khg = khg[khg.khg_id.isin(a.khg)]
    todo = [(cfg, r.khg_id, r.nama, r.geometry) for r in khg.itertuples() if a.force or not cache_file(cfg, r.khg_id).exists()]
    log.info("%d KHG, %d to compute", len(khg), len(todo))
    if todo:
        with ProcessPoolExecutor(a.workers) as ex:
            for n, kid in enumerate(ex.map(work, todo), 1):
                if n % 25 == 0 or n == len(todo):
                    log.info("%d / %d (%s)", n, len(todo), kid)
    out = Path(cfg["out"]) / "land"
    summ, vil, chk = collect(cfg, khg.khg_id.tolist())
    num = [c for c in summ.columns if summ[c].dtype == float]
    summ[num] = summ[num].round(4)
    cols = ["khg_id", "khg", "layer", "class", "label"] + [c for c in summ.columns if c not in ("khg_id", "khg", "layer", "class", "label")]
    summ[cols].to_csv(out / "land_summary.csv", index=False)
    vil.round(4).to_csv(out / "land_dmpg_villages.csv", index=False)
    chk.round(4).to_csv(out / "land_checks.csv", index=False)
    log.info("%d KHG -> %s", khg.shape[0], out)


if __name__ == "__main__":
    main()
