"""Cell panel of one KHG for the hypothesis tests: the 200 m peat cells of the licence-edge run, each with its tenure class, distances to
the nearest licence, canal and road, dome position, burn history, and the VIIRS hotspots of every year over the same calendar window.

A hotspot takes the cell nearest to it (within 0.71 of the cell size). Medium and high confidence are counted together (`n_<year>`) and
high alone (`h_<year>`). Tenure follows `national.tenure` (licence, forest area without a licence, other land) and a DMPG flag.
Cached in <out>/hypotheses/panel/<khg_id>.parquet and hot/<khg_id>.parquet, keyed by the fingerprint of the input files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from scipy.spatial import cKDTree

from repeat_common import khg as K
from repeat_prioritisation.investigations import licence_edge as LE
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P
from repeat_prioritisation.national import tenure as T

YEARS = list(range(2012, 2027))
BA_YEARS = list(range(2015, 2026))
ROADS = "Transportasi_Jalan_Detil.gpkg"
BLOCK_M = 5000.0


def fingerprint(paths, extra=""):
    h = hashlib.sha256(extra.encode())
    for p in sorted(map(str, paths)):
        f = Path(p)
        h.update(p.encode())
        if f.exists():
            st = f.stat()
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def inputs(cfg, kid):
    code = kid.replace("KHG.", "", 1)
    run = K.folder(code) / "04_prioritisation" / "licence_edge"
    data = Path(cfg["data"])
    kfolder = K.folder(code)
    return run, [run / "cells.csv.gz", run / "summary.json", data / cfg["inputs"]["licences"], data / cfg["inputs"]["forest_area"], data / cfg["inputs"]["dmpg"],
                 data / cfg["inputs"]["burned"], data / ROADS, *[data / f for f in T.VIIRS], kfolder / "00_inputs" / "canals.gpkg"]


def build(cfg, kid, out: Path, force=False):
    """Write the panel and the hotspot list of one KHG; return their paths and the fingerprint. None when the KHG has no licence-edge run."""
    run, files = inputs(cfg, kid)
    if not (run / "cells.csv.gz").exists():
        return None
    fp = fingerprint(files, "panel-v1")
    dst, dst_h = out / "panel" / f"{kid}.parquet", out / "hot" / f"{kid}.parquet"
    meta_f = out / "panel" / f"{kid}.json"
    if not force and dst.exists() and dst_h.exists() and meta_f.exists() and json.loads(meta_f.read_text())["fingerprint"] == fp:
        return dst, dst_h, json.loads(meta_f.read_text())
    summ = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    cell = float(summ["cell_m"])
    cells = pd.read_csv(run / "cells.csv.gz", usecols=["x", "y", "lon", "lat", "har_m", "position", "canal_m"])
    cells = cells[cells["position"].isin(["foot", "slope", "crest"])].reset_index(drop=True)
    g = shapely.make_valid(P.load_khg(cfg).set_index("khg_id").loc[kid, "geometry"])
    data, inp = Path(cfg["data"]), cfg["inputs"]
    kws, _ = O.read_forest_feg(cfg, g)
    lic = O._read(data / inp["licences"], g, ["IZIN_USAHA"])
    lic["cls"] = lic["IZIN_USAHA"].map(O.LIC_VALUE)
    lic = lic[lic["cls"].isin(T.LIC_RANK)]
    dpg = O.read_dmpg(data / inp["dmpg"], g) if (data / inp["dmpg"]).exists() else None
    pts = gpd.GeoDataFrame(index=cells.index, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326)
    pc = T.classify(pts, lic, kws, dpg)
    cells = cells.join(pc)
    x, y = LE.to_aea(cells.lon.to_numpy(), cells.lat.to_numpy())
    cells["bx"], cells["by"] = np.floor(x / BLOCK_M).astype(int), np.floor(y / BLOCK_M).astype(int)
    # distance to the nearest licence polygon (0 inside one), in metres, from the licence set that defines the tenure class
    if len(lic):
        polys = shapely.transform(shapely.make_valid(lic.geometry.values), lambda c: np.column_stack(LE.to_aea(c[:, 0], c[:, 1])))
        _, dist = shapely.STRtree(polys).query_nearest(shapely.points(x, y), return_distance=True, all_matches=False)
        cells["dist_lic_m"] = np.where(cells["tenure"] == "licence", 0.0, dist)
    else:
        cells["dist_lic_m"] = np.nan
    rv = LE.line_vertices(data / ROADS, g.buffer(0.05))
    cells["road_m"] = cKDTree(rv).query(np.column_stack([x, y]))[0] if len(rv) else np.nan
    # burn history: burnt-area polygons 2015-2025, and 2026
    b = pyogrio.read_dataframe(data / inp["burned"], mask=g)
    pts_a = shapely.points(x, y)
    for yr in BA_YEARS + [2026]:
        cells[f"ba_{yr}"] = False
        col = f"BA_{yr}"
        if col in b.columns and len(b):
            polys = shapely.transform(shapely.make_valid(b.geometry[b[col].notna()].values), lambda q: np.column_stack(LE.to_aea(q[:, 0], q[:, 1])))
            if len(polys):
                cells.loc[shapely.STRtree(polys).query(pts_a, predicate="within")[0], f"ba_{yr}"] = True
    # hotspots on peat, same calendar window in every year
    h = T.viirs(cfg, g)
    h = h[h["ytd"]].reset_index(drop=True)
    hx, hy = LE.to_aea(h.geometry.x.to_numpy(), h.geometry.y.to_numpy())
    d, i = cKDTree(np.column_stack([x, y])).query(np.column_stack([hx, hy]))
    ok = d <= cell * 0.71
    for yr in YEARS:
        cells[f"n_{yr}"] = 0
        cells[f"h_{yr}"] = 0
    hh = h[ok].assign(cell=i[ok])
    for (yr, conf), grp in hh.groupby(["year", "conf"]):
        cnt = np.bincount(grp["cell"].to_numpy(), minlength=len(cells))
        cells[f"n_{int(yr)}"] += cnt
        if conf == "high":
            cells[f"h_{int(yr)}"] += cnt
    hot = pd.DataFrame({"date": hh["date"].to_numpy(), "year": hh["year"].to_numpy(), "conf": hh["conf"].to_numpy(),
                        "tenure": cells["tenure"].to_numpy()[hh["cell"]], "sub": cells["sub"].to_numpy()[hh["cell"]],
                        "position": cells["position"].to_numpy()[hh["cell"]], "dmpg": cells["dmpg"].to_numpy()[hh["cell"]]})
    cells = cells.drop(columns=["har_m"]).assign(khg_id=kid)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst_h.parent.mkdir(parents=True, exist_ok=True)
    cells.to_parquet(dst, index=False, compression="zstd")
    hot.to_parquet(dst_h, index=False, compression="zstd")
    meta = {"fingerprint": fp, "khg_id": kid, "cell_m": cell, "cells": int(len(cells)), "hotspots_on_peat": int(len(h)), "hotspots_on_cells": int(ok.sum()),
            "licence_polygons": int(len(lic)), "road_vertices": int(len(rv)), "dem": summ.get("dem"), "window_last_day": str(T.last_day(data).date())}
    meta_f.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return dst, dst_h, meta
