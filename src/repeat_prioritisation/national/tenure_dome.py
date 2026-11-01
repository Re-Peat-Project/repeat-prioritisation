#!/usr/bin/env python3
"""Fire by land tenure and position on the peat dome, for the KHG that have a licence-edge run.

  repeat-national-tenure-dome --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...]

Position (foot, slope, crest) is the third of the KHG's peat cells by height above the nearest river, from the DTM the
licence-edge investigation chose (`<khg folder>/04_prioritisation/licence_edge/cells.csv.gz`, 200 m cells), so a KHG needs that
run first (`python -m repeat_prioritisation.investigations.licence_edge`). Each peat cell and each VIIRS hotspot on peat gets the
tenure class of `national.tenure` (same precedence and layers); a hotspot takes the position of the nearest cell within 0.71 of
the cell size. Writes <out>/tenure/:
  tenure_dome.csv   khg_id, tenure, position, peat_km2, burned_peat_km2, year, conf, n  (hotspots on peat; calendar window of
                    `tenure_hotspots.csv`; one row per class, position, year and confidence, with area repeated)
  tenure_dome_checks.csv  per KHG: peat cells, hotspots assigned to a cell against hotspots on peat, DTM used
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from repeat_common import khg as K
from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P
from repeat_prioritisation.national import tenure as T

log = logging.getLogger("prioritas.tenure_dome")


def one(cfg, kid):
    code = kid.replace("KHG.", "", 1)
    run = K.folder(code) / "04_prioritisation" / "licence_edge"
    if not (run / "cells.csv.gz").exists():
        return None
    cells = pd.read_csv(run / "cells.csv.gz", usecols=["x", "y", "lon", "lat", "position", "ba_2015"] + [f"ba_{y}" for y in range(2016, 2026)])
    cells = cells[cells["position"].isin(["foot", "slope", "crest"])].reset_index(drop=True)
    meta = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    cell = float(meta["cell_m"])
    khg = P.load_khg(cfg)
    g = shapely.make_valid(khg[khg.khg_id == kid].geometry.iloc[0])
    data, inp = Path(cfg["data"]), cfg["inputs"]
    kws, _ = O.read_forest_feg(cfg, g)
    lic = O._read(data / inp["licences"], g, ["IZIN_USAHA"])
    lic["cls"] = lic["IZIN_USAHA"].map(O.LIC_VALUE)
    dpg = None
    pts = gpd.GeoDataFrame(index=cells.index, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326)
    pc = T.classify(pts, lic, kws, dpg)
    cells["tenure"] = pc["tenure"].to_numpy()
    cells["burned"] = cells[[f"ba_{y}" for y in range(2015, 2026)]].any(axis=1)
    area = cells.groupby(["tenure", "position"], as_index=False).agg(n=("x", "size"), burn=("burned", "sum"))
    area["peat_km2"] = area["n"] * cell * cell / 1e6
    area["burned_peat_km2"] = area["burn"] * cell * cell / 1e6
    h = T.viirs(cfg, g)
    from repeat_prioritisation.investigations.licence_edge import to_aea
    cx, cy = to_aea(cells.lon.to_numpy(), cells.lat.to_numpy())
    hx, hy = to_aea(h.geometry.x.to_numpy(), h.geometry.y.to_numpy())
    d, i = cKDTree(np.column_stack([cx, cy])).query(np.column_stack([hx, hy]))
    ok = d <= cell * 0.71
    hot = pd.DataFrame({"tenure": cells["tenure"].to_numpy()[i[ok]], "position": cells["position"].to_numpy()[i[ok]],
                        "year": h["year"].to_numpy()[ok], "conf": h["conf"].to_numpy()[ok], "ytd": h["ytd"].to_numpy()[ok]})
    hot = hot[hot["ytd"]].groupby(["tenure", "position", "year", "conf"], as_index=False).size().rename(columns={"size": "n"})
    out = area[["tenure", "position", "peat_km2", "burned_peat_km2"]].merge(hot, on=["tenure", "position"], how="left")
    out.insert(0, "khg_id", kid)
    chk = {"khg_id": kid, "cells": int(len(cells)), "hs_on_peat": int(len(h)), "hs_on_cells": int(ok.sum()), "dem": meta.get("dem")}
    return out, chk


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*", help="khg_id to compute (default: every KHG with a licence-edge run)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    ids = a.khg or [k for k in P.load_khg(cfg).khg_id if (K.folder(k.replace("KHG.", "", 1)) / "04_prioritisation" / "licence_edge" / "cells.csv.gz").exists()]
    rows, chks = [], []
    for kid in ids:
        try:
            r = one(cfg, kid)
        except Exception as e:      # a KHG without a folder or a registry entry
            log.warning("%s skipped: %s", kid, e)
            continue
        if r is None:
            log.info("%s: no licence-edge run, skipped", kid)
            continue
        log.info("%s done", kid)
        rows.append(r[0])
        chks.append(r[1])
    out = Path(cfg["out"]) / "tenure"
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(rows).round(4).to_csv(out / "tenure_dome.csv", index=False)
    pd.DataFrame(chks).to_csv(out / "tenure_dome_checks.csv", index=False)
    log.info("%d KHG -> %s", len(rows), out)


if __name__ == "__main__":
    main()
