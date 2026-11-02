#!/usr/bin/env python3
"""VIIRS hotspots on peat per KHG, year and month: the data of the month-by-year heat map in the dashboard profile.

  repeat-national-monthly --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 4] [--force]

Same hotspots as `repeat-national-tenure`: VIIRS SNPP 2012-2026 (standard product, then the 2026 standard and near-real-time
files), vegetation-fire type 0 where the file has a type, medium (n) and high (h) confidence kept apart, on peat cells of the
GFW peat extent. Results of each KHG are cached in <out>/monthly/cache/<khg_id>.json, so an interrupted run resumes. Writes
<out>/monthly/hotspot_month_year.csv: khg_id, year, month, conf, n (only months with a detection).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import profile as P
from repeat_prioritisation.national import tenure as T

log = logging.getLogger("prioritas.monthly")


def cache_file(cfg, kid):
    return Path(cfg["out"]) / "monthly" / "cache" / (re.sub(r"[^\w.-]", "_", kid) + ".json")


def work(args):
    cfg, kid, geom = args
    h = T.viirs(cfg, geom)
    rows = []
    if len(h):
        g = h.assign(month=h["date"].dt.month).groupby(["year", "month", "conf"], as_index=False).size()
        rows = [{"khg_id": kid, "year": int(r.year), "month": int(r.month), "conf": r.conf, "n": int(r.size)} for r in g.itertuples()]
    f = cache_file(cfg, kid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows), encoding="utf-8")
    return kid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*", help="khg_id to compute (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="recompute KHG that are already cached")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    sel = P.load_khg(cfg)
    if a.khg:
        sel = sel[sel.khg_id.isin(a.khg)]
    todo = [(cfg, r.khg_id, r.geometry) for r in sel.itertuples() if a.force or not cache_file(cfg, r.khg_id).exists()]
    log.info("%d KHG, %d to compute", len(sel), len(todo))
    if a.workers > 1 and len(todo) > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            for i, kid in enumerate(ex.map(work, todo), 1):
                if i % 25 == 0 or i == len(todo):
                    log.info("%d/%d", i, len(todo))
    else:
        for t in todo:
            log.info("%s", t[1])
            work(t)
    rows = []
    for kid in sel.khg_id:
        rows += json.loads(cache_file(cfg, kid).read_text(encoding="utf-8"))
    out = Path(cfg["out"]) / "monthly"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["khg_id", "year", "month", "conf", "n"]).to_csv(out / "hotspot_month_year.csv", index=False)
    log.info("%d KHG, %d rows -> %s", len(sel), len(rows), out)


if __name__ == "__main__":
    main()
