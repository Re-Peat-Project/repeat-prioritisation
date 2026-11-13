#!/usr/bin/env python3
"""Burned area and hotspots by land status for all of Indonesia: concessions (business licences), forest area (kawasan hutan)
and DMPG villages, with peat as an added split.

  repeat-national-fire --config configs/examples/national_profile.yaml [--workers 6] [--force] [--tiles 120_40 ...] [--summary-only]

Method. Indonesia is cut into tiles of an equal-area grid (EPSG:6933, `fire_landstatus.cell_m`, 30 m, so every cell has the
same area). In each tile every layer is rasterised on that grid (a cell takes a polygon's value when its centre lies inside):
  district     village boundaries 2023 (KLH): province, district and island; the land mask (cells outside every village are sea)
  khg          KHG boundaries (865 KHG, SK.129/2017); 0 = outside every KHG
  kawasan      forest area function 2023: conservation, protection, production (HP, HPT), convertible (HPK), other land use (APL),
               water or undefined; 0 = not mapped. Overlaps take the first class in that order
  licence      business licences 2025, one bit per type (oil palm, mining, plantation forest PPHTR, forest concession PBPH, and
               community forest PPHKM), so overlapping licences keep every type
  dmpg         Desa Mandiri Peduli Gambut village land (SiTMAT portal)
  peat         KLH peat (PPEG 2026) on this grid (peat.extent; nearest cell; 255 where the raster has no value), or the peat
               polygons themselves when `fire_landstatus.peat_vector` is set ({path, layer, where}; 0 outside them)
  burned       KLHK burnt-area polygons 2015-2026, one bit per year (BA_yyyy)
Cells with the same values are counted together. Hotspots take the values of the cell they fall in:
  MODIS 2026   KLH file to its last date, FIRMS MODIS NRT after it (hotspots_modis_2026.gpkg); low, medium, high kept apart
  VIIRS        S-NPP 2012-2026 (FIRMS archive, standard and NRT 2026); vegetation fire (type 0) where the file records a type
Neither MODIS nor the VIIRS NRT file records a type, so a hotspot within `static_radius_m` of a VIIRS detection typed as volcano,
static land source or offshore (types 1-3, 2012-2026) is flagged `static` and kept apart.

Each tile is cached in <out>/fire_landstatus/cache/, so an interrupted run resumes. Writes, in <out>/fire_landstatus/:
  cells.parquet      one row per value combination: kab, khg, kawasan, licence bits, dmpg, peat, burn bits, cells, area_ha
  hotspots.parquet   one row per combination of the same classes and source, year, month, confidence, static flag, ytd: n
  districts.csv      kab index -> island, province, district
  checks.csv         per tile and year: raster burned area against the exact polygon area; hotspot totals against the files
  meta.json          inputs, cell size, grid, last dates, raster codes
  layers/            for review in a GIS: status.vrt over tiles/status_<i>_<j>.tif (7 bands: kawasan, concession type, DMPG, peat,
                     KHG index, number of burns, burn-year bits; EPSG:6933, 30 m) and hotspots_2026.gpkg (layers modis_2026, viirs_2026: every 2026 hotspot with its classes)
Tables for the report and the dashboard are made from these by `national.fire_tables`.
"""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy.spatial import cKDTree

from repeat_prioritisation.national import fire_common as C

log = logging.getLogger("prioritas.fire")

DEFAULT = {"crs": "EPSG:6933", "cell_m": 30, "tile_cells": 3000, "years": [2015, 2026],
           "villages": "batas_desa_indonesia_2023_KLH.gpkg",
           "modis": "hotspots_modis_2026.gpkg",
           "viirs": ["hotspot_viirs_snpp_2012_2025.gpkg", "hotspot_viirs_snpp_sp_2026.gpkg", "hotspot_viirs_snpp_nrt_2026.gpkg"],
           "static_radius_m": {"modis": 1000, "viirs": 375}}
KWS_CODES = ["cons", "hl", "prod", "hpk", "apl", "other"]          # raster value = index + 1; 0 = not mapped
LIC_BITS = {"sawit": 1, "tambang": 2, "pphtr": 4, "pbph": 8, "pphkm": 16}
CONF = {"l": "low", "n": "medium", "h": "high", "low": "low", "medium": "medium", "high": "high"}
LEVEL_NAMES = {"rendah": "low", "low": "low", "sedang": "medium", "medium": "medium", "tinggi": "high", "high": "high"}
# bit layout of the cell key
SHIFT = {"kab": 0, "khg": 10, "kws": 20, "lic": 23, "dmpg": 28, "peat": 29, "burn": 31}
WIDTH = {"kab": 10, "khg": 10, "kws": 3, "lic": 5, "dmpg": 1, "peat": 2, "burn": 12}

_S = {}   # per-worker state (set by init)


def settings(cfg):
    s = dict(DEFAULT)
    s.update(cfg.get("fire_landstatus") or {})
    return s


def out_dir(cfg):
    return Path(cfg["out"]) / "fire_landstatus"


def tiles(cfg):
    """Tile index (i, j) and the grid origin, from the bounds of the village boundaries (the land of Indonesia)."""
    s, data = settings(cfg), Path(cfg["data"])
    b = pyogrio.read_info(data / s["villages"], force_total_bounds=True)["total_bounds"]
    tf = Transformer.from_crs(4326, s["crs"], always_xy=True)
    x0, y0 = tf.transform(b[0], b[1])
    x1, y1 = tf.transform(b[2], b[3])
    c, t = s["cell_m"], s["tile_cells"]
    x0, y1 = np.floor(x0 / c) * c, np.ceil(y1 / c) * c
    nx, ny = int(np.ceil((x1 - x0) / (c * t))), int(np.ceil((y1 - y0) / (c * t)))
    return [(i, j) for j in range(ny) for i in range(nx)], (float(x0), float(y1))


def tile_geo(origin, i, j, c, t):
    x0, y1 = origin[0] + i * t * c, origin[1] - j * t * c
    return from_origin(x0, y1, c, c), (x0, y1 - t * c, x0 + t * c, y1)


def static_points(cfg):
    """VIIRS detections typed volcano, static land source or offshore (1-3), 2012-2026, in grid metres (unique to 50 m)."""
    s, data = settings(cfg), Path(cfg["data"])
    tf = Transformer.from_crs(4326, s["crs"], always_xy=True)
    xy = []
    for f in s["viirs"]:
        if (data / f).exists() and "type" in pyogrio.read_info(data / f)["fields"]:
            h = pyogrio.read_dataframe(data / f, columns=["type"], where="type IN (1, 2, 3)")
            xy.append(np.column_stack(tf.transform(h.geometry.x.to_numpy(), h.geometry.y.to_numpy())))
    xy = np.vstack(xy) if xy else np.zeros((0, 2))
    return np.unique(np.round(xy / 50) * 50, axis=0)


def last_date(cfg, f):
    d = pd.to_datetime(pyogrio.read_dataframe(Path(cfg["data"]) / f, columns=["acq_date"], read_geometry=False)["acq_date"], errors="coerce")
    return d.max()


def init(state):
    _S.update(state)
    _S["tree"] = cKDTree(state["static"]) if len(state["static"]) else None


def _vec(path, bbox, cols, layer=None, where=None):
    try:
        g = pyogrio.read_dataframe(path, bbox=bbox, columns=cols, layer=layer, where=where)
    except Exception:                       # noqa: BLE001  (empty result on some drivers)
        return gpd.GeoDataFrame(columns=cols, geometry=[], crs=4326)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g


def _rast(geoms, values, shape, tr, dtype):
    shapes = [(g, v) for g, v in zip(geoms, values) if g is not None and not g.is_empty]
    if not shapes:
        return np.zeros(shape, dtype)
    return rasterize(shapes, out_shape=shape, transform=tr, fill=0, dtype=dtype, all_touched=False)


def _hotspots(path, bbox, kind, ytd_cut, now):
    """Hotspots of one file inside bbox: x, y (lon/lat), year, month, conf, ytd, typed (file has a type column).
    Field names in any case. MODIS: `level` (low/medium/high, or rendah/sedang/tinggi) where present, else FIRMS `confidence` 0-100
    (low <30, medium 30-79, high >=80, the KLH limits); `month` where present, else the month of acq_date."""
    fields = {c.lower(): c for c in pyogrio.read_info(path)["fields"]}
    want = [c for c in ("acq_date", "confidence", "type", "level", "month") if c in fields]
    h = _vec(path, bbox, [fields[c] for c in want]).rename(columns={fields[c]: c for c in want})
    if not len(h):
        return None
    if "type" in h:
        h = h[h["type"] == 0]
    d = pd.to_datetime(h["acq_date"], errors="coerce") if "acq_date" in h else pd.Series(pd.NaT, index=h.index)
    if kind == "modis":
        if "level" in h:
            conf = h["level"].astype(str).str.lower().map(LEVEL_NAMES).fillna(h["level"].astype(str))
        else:
            conf = pd.cut(pd.to_numeric(h["confidence"], errors="coerce"), [-1, 29, 79, 101], labels=["low", "medium", "high"]).astype(str)
        month = (h["month"].fillna(d.dt.month) if "month" in h else d.dt.month).astype(int)
        year = np.full(len(h), now)
        ytd = np.ones(len(h), bool)
    else:
        conf = h["confidence"].map(CONF)
        month, year = d.dt.month.to_numpy(), d.dt.year.to_numpy()
        ytd = (d.dt.month * 100 + d.dt.day).to_numpy() <= ytd_cut.month * 100 + ytd_cut.day
    return pd.DataFrame({"x": h.geometry.x.to_numpy(), "y": h.geometry.y.to_numpy(), "year": np.asarray(year, int),
                         "month": np.asarray(month, int), "conf": np.asarray(conf), "ytd": np.asarray(ytd, bool),
                         "typed": "type" in h})


def one_tile(ij):
    """Cell combinations and hotspots of one tile; None when the tile holds no village land."""
    cfg, s = _S["cfg"], _S["s"]
    data, inp = Path(cfg["data"]), cfg["inputs"]
    i, j = ij
    c, t = s["cell_m"], s["tile_cells"]
    tr, (x0, y0, x1, y1) = tile_geo(_S["origin"], i, j, c, t)
    inv = Transformer.from_crs(s["crs"], 4326, always_xy=True)
    lon0, lat0 = inv.transform(x0, y0)
    lon1, lat1 = inv.transform(x1, y1)
    bbox = (lon0, lat0, lon1, lat1)
    shape = (t, t)
    crs = s["crs"]

    vil = _vec(data / s["villages"], bbox, ["PULAU", "PROV_2023", "KABKO_2023"])
    if not len(vil):
        return None
    kab_key = (vil["PROV_2023"].astype(str) + "|" + vil["KABKO_2023"].fillna("").astype(str)).map(_S["kab_index"]).fillna(0).astype(int)
    kab = _rast(vil.to_crs(crs).geometry, kab_key, shape, tr, "uint16")
    land = kab > 0
    if not land.any():
        return None

    khg = _S["khg"]
    kk = khg.iloc[list(khg.sindex.query(shapely.box(x0, y0, x1, y1)))]
    khg_r = _rast(kk.geometry, kk["idx"], shape, tr, "uint16")

    kws = _vec(data / inp["forest_area"], bbox, ["Fungsi"])
    kws_r = np.zeros(shape, "uint8")
    if len(kws):
        code = kws["Fungsi"].map(C.CODE_TO_KWS).fillna("other").map({k: n + 1 for n, k in enumerate(KWS_CODES)})
        kws = kws.assign(code=code).sort_values("code", ascending=False)   # first class in KWS_CODES rasterised last, so it wins
        kws_r = _rast(kws.to_crs(crs).geometry, kws["code"], shape, tr, "uint8")

    lic = _vec(data / inp["licences"], bbox, ["IZIN_USAHA"])
    lic_r = np.zeros(shape, "uint8")
    if len(lic):
        lic = lic.assign(cls=lic["IZIN_USAHA"].map(C.LIC_VALUE)).to_crs(crs)
        for k, bit in LIC_BITS.items():
            sel = lic[lic["cls"] == k]
            if len(sel):
                lic_r |= _rast(sel.geometry, [1] * len(sel), shape, tr, "uint8") * np.uint8(bit)

    dm = _vec(data / inp["dmpg"], bbox, [], layer=s.get("dmpg_layer", C.DMPG_LAYER)) if inp.get("dmpg") else []
    dm_r = _rast(dm.to_crs(crs).geometry, [1] * len(dm), shape, tr, "uint8") if len(dm) else np.zeros(shape, "uint8")

    peat = np.full(shape, 255, "uint8")
    pv = s.get("peat_vector")
    if pv:                                  # peat polygons (e.g. PPEG LAHAN_GAMB = 'LAHAN GAMBUT'), cell-centre rule; 0 elsewhere
        pg = _vec(data / pv["path"], bbox, [], layer=pv.get("layer"), where=pv.get("where"))
        peat = _rast(pg.to_crs(crs).geometry, [1] * len(pg), shape, tr, "uint8") if len(pg) else np.zeros(shape, "uint8")
    elif _S["peat"]:
        with rasterio.open(_S["peat"]) as src:
            reproject(rasterio.band(src, 1), peat, src_nodata=None, dst_transform=tr, dst_crs=crs, dst_nodata=255,
                      resampling=Resampling.nearest, init_dest_nodata=True)
    peat_c = np.where(peat == 1, 1, np.where(peat == 0, 0, 3)).astype("uint8")

    y_a, y_b = s["years"]
    ycols = [f"BA_{y}" for y in range(y_a, y_b + 1)]
    ba = _vec(data / inp["burned"], bbox, ycols)
    burn = np.zeros(shape, "uint16")
    chk = []
    if len(ba):
        bam = ba.to_crs(crs)
        box = shapely.box(x0, y0, x1, y1)
        for n, col in enumerate(ycols):
            sel = bam[ba[col].notna().to_numpy()]
            if not len(sel):
                continue
            m = _rast(sel.geometry, [1] * len(sel), shape, tr, "uint8").astype(bool)
            burn |= (m.astype("uint16") << n)
            exact = float(shapely.area(shapely.intersection(shapely.make_valid(sel.geometry.to_numpy()), box)).sum()) / 1e4
            chk.append({"tile": f"{i}_{j}", "year": y_a + n, "exact_ha": exact, "raster_ha": m.sum() * c * c / 1e4,
                        "raster_land_ha": (m & land).sum() * c * c / 1e4})

    def key(sel):
        k = kab[sel].astype(np.int64)
        for name, arr in (("khg", khg_r), ("kws", kws_r), ("lic", lic_r), ("dmpg", dm_r), ("peat", peat_c), ("burn", burn)):
            k |= arr[sel].astype(np.int64) << SHIFT[name]
        return k

    u, n = np.unique(key(land), return_counts=True)
    cells = pd.DataFrame({"key": u, "cells": n})
    if _S.get("rasters"):          # layers for review in a GIS: land status and burn years of every 30 m cell
        conc = np.zeros(shape, "uint16")                      # first concession type, as in the tables; 5 = PPHKM only
        conc[(lic_r & 16) > 0] = 5
        for code, bit in ((4, 8), (3, 4), (2, 2), (1, 1)):
            conc[(lic_r & bit) > 0] = code
        nburn = sum(((burn >> n) & 1) for n in range(len(ycols))).astype("uint16")
        bands = [(kws_r, "kawasan: 0 not mapped, 1 conservation, 2 protection, 3 production, 4 convertible, 5 APL, 6 water or undefined"),
                 (conc, "concession: 0 none, 1 oil palm, 2 mining, 3 PPHTR, 4 PBPH (first type), 5 PPHKM only"),
                 (dm_r, "DMPG village: 1 yes"), (peat_c, "peat: 0 no, 1 yes, 3 no information"), (khg_r, "KHG index (khg_index.csv), 0 outside"),
                 (nburn, f"number of burn years {y_a}-{y_b}"), (burn, f"burn years: bit n = burned in {y_a} + n")]
        f = raster_path(cfg, (i, j))
        f.parent.mkdir(parents=True, exist_ok=True)
        prof = {"driver": "GTiff", "width": t, "height": t, "count": len(bands), "dtype": "uint16", "crs": crs, "transform": tr, "nodata": 65535,
                "compress": "deflate", "predictor": 2, "tiled": True, "blockxsize": 512, "blockysize": 512}
        with rasterio.open(f.with_suffix(".tmp.tif"), "w", **prof) as dst:
            for b, (arr, desc) in enumerate(bands, 1):
                dst.write(np.where(land, arr.astype("uint16"), np.uint16(65535)), b)
                dst.set_band_description(b, desc)
        f.with_suffix(".tmp.tif").replace(f)

    # hotspots: every point whose cell lies in this tile (the bbox read can include points on the next tile's edge)
    tf = Transformer.from_crs(4326, crs, always_xy=True)
    hs = []
    for kind, files, cut in (("modis", [s["modis"]], None), ("viirs", s["viirs"], _S["viirs_cut"])):
        for f in files:
            if not (data / f).exists():
                continue
            h = _hotspots(data / f, bbox, kind, cut, s["years"][1])
            if h is None or not len(h):
                continue
            hx, hy = tf.transform(h["x"].to_numpy(), h["y"].to_numpy())
            col = np.floor((hx - x0) / c).astype(int)
            row = np.floor((y1 - hy) / c).astype(int)
            ok = (col >= 0) & (col < t) & (row >= 0) & (row < t)
            h, hx, hy, col, row = h[ok], hx[ok], hy[ok], col[ok], row[ok]
            static = np.zeros(len(h), bool)
            if _S["tree"] is not None and len(h) and not h["typed"].iloc[0]:
                d, _ = _S["tree"].query(np.column_stack([hx, hy]), distance_upper_bound=s["static_radius_m"][kind])
                static = np.isfinite(d)
            idx = (row, col)
            k = kab[idx].astype(np.int64)
            for name, arr in (("khg", khg_r), ("kws", kws_r), ("lic", lic_r), ("dmpg", dm_r), ("peat", peat_c)):
                k |= arr[idx].astype(np.int64) << SHIFT[name]
            hs.append(pd.DataFrame({"key": k, "source": kind, "file": f, "year": h["year"].to_numpy(), "month": h["month"].to_numpy(),
                                    "conf": h["conf"].to_numpy(), "static": static, "ytd": h["ytd"].to_numpy(),
                                    "lon": h["x"].to_numpy(), "lat": h["y"].to_numpy()}))
    allh = pd.concat(hs, ignore_index=True) if hs else pd.DataFrame(columns=["key", "source", "file", "year", "month", "conf", "static", "ytd", "lon", "lat"])
    hot = allh.groupby(["key", "source", "file", "year", "month", "conf", "static", "ytd"], as_index=False).size().rename(columns={"size": "n"})
    pts = allh[allh["year"] == s["years"][1]].reset_index(drop=True)  # this year's points, kept for review with their classes
    return cells, hot, pd.DataFrame(chk), pts


def cache_paths(cfg, ij):
    d = out_dir(cfg) / "cache"
    return [d / f"{ij[0]}_{ij[1]}.{x}.parquet" for x in ("cells", "hot", "chk", "pts")], d / f"{ij[0]}_{ij[1]}.empty"


def raster_path(cfg, ij):
    return out_dir(cfg) / "layers" / "tiles" / f"status_{ij[0]}_{ij[1]}.tif"


def work(ij):
    files, empty = cache_paths(_S["cfg"], ij)
    r = one_tile(ij)
    files[0].parent.mkdir(parents=True, exist_ok=True)
    if r is None:
        empty.write_text("", encoding="utf-8")
        return ij, False
    for f, df in zip(files, r):
        tmp = f.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(f)
    return ij, True


def decode(df, names=tuple(SHIFT)):
    k = df["key"].to_numpy(np.int64)
    for name in names:
        df[name] = ((k >> SHIFT[name]) & ((1 << WIDTH[name]) - 1)).astype(np.int32)
    return df.drop(columns="key")


def district_table(cfg):
    s = settings(cfg)
    v = pyogrio.read_dataframe(Path(cfg["data"]) / s["villages"], columns=["PULAU", "PROV_2023", "KABKO_2023"], read_geometry=False)
    v["KABKO_2023"] = v["KABKO_2023"].fillna("")
    d = (v.groupby(["PROV_2023", "KABKO_2023"], as_index=False)["PULAU"].agg(lambda x: x.mode().iat[0])
         .sort_values(["PROV_2023", "KABKO_2023"]).reset_index(drop=True))
    d.insert(0, "kab", np.arange(1, len(d) + 1))
    return d.rename(columns={"PULAU": "island", "PROV_2023": "province", "KABKO_2023": "district"})


def reference_counts(cfg, cut):
    """Hotspots in each file after the same type filter, for the check against the tile totals."""
    s, data, rows = settings(cfg), Path(cfg["data"]), []
    for kind, files in (("modis", [s["modis"]]), ("viirs", s["viirs"])):
        for f in files:
            if not (data / f).exists():
                continue
            fields = list(pyogrio.read_info(data / f)["fields"])
            cols = [c for c in ("type",) if c in fields] or [fields[0]]
            h = pyogrio.read_dataframe(data / f, columns=cols, read_geometry=False)
            n = int((h["type"] == 0).sum()) if "type" in h else len(h)
            rows.append({"source": kind, "file": f, "n_file": n})
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="recompute tiles that are already cached")
    ap.add_argument("--tiles", nargs="*", help="only these tiles, as i_j (for tests)")
    ap.add_argument("--summary-only", action="store_true", help="only rebuild the outputs from the cached tiles")
    ap.add_argument("--no-rasters", action="store_true", help="do not write the 30 m status and burn rasters (layers/tiles)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    from repeat_prioritisation.national import land as L     # the national config (dashboard package)
    run(L.load_cfg(a.config), a.workers, a.force, a.tiles, a.summary_only, not a.no_rasters)


def run(cfg, workers=6, force=False, tile_list=None, summary_only=False, rasters=True):
    """The tally for a loaded config (see the module docstring); tile_list = ["i_j", ...] limits it to those tiles."""
    s = settings(cfg)
    out = out_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    all_tiles, origin = tiles(cfg)
    sel = [tuple(map(int, x.split("_"))) for x in tile_list] if tile_list else all_tiles
    dist = district_table(cfg)
    viirs_cut = last_date(cfg, s["viirs"][-1])
    if not summary_only:
        khg = C.load_khg(cfg)[["khg_id", "geometry"]].to_crs(s["crs"]).reset_index(drop=True)
        khg["idx"] = np.arange(1, len(khg) + 1)
        state = {"cfg": cfg, "s": s, "origin": origin, "khg": khg, "peat": str(C.peat_path(cfg) or ""),
                 "kab_index": dict(zip(dist["province"] + "|" + dist["district"], dist["kab"])),
                 "static": static_points(cfg), "viirs_cut": viirs_cut, "rasters": rasters}
        todo = [ij for ij in sel if force or not any(p.exists() for p in [cache_paths(cfg, ij)[0][0], cache_paths(cfg, ij)[1]])]
        log.info("%d tiles, %d to compute, %d static points", len(sel), len(todo), len(state["static"]))
        khg[["khg_id", "idx"]].to_csv(out / "khg_index.csv", index=False)
        if workers > 1 and len(todo) > 1:
            with ProcessPoolExecutor(workers, initializer=init, initargs=(state,)) as ex:
                for n, (ij, land) in enumerate(ex.map(work, todo), 1):
                    if n % 20 == 0 or n == len(todo):
                        log.info("%d / %d tiles", n, len(todo))
        else:
            init(state)
            for ij in todo:
                log.info("tile %s %s", ij, work(ij)[1])
    collect(cfg, sel, dist, viirs_cut)


LAYERS_README = """# Review layers: burned area and hotspots by land status

Written by the fire tally (`fire_landstatus`: rasters, hotspots) and its tables step (`fire_tables`: summary polygons). Open in QGIS.

| File | Content |
|---|---|
| `status.vrt` | Mosaic of `tiles/status_<i>_<j>.tif`: the 30 m equal-area grid (EPSG:6933) the tallies were made on. 7 bands, uint16, nodata 65535 outside the 2023 village boundaries. |
| `hotspots_{y1}.gpkg` | Layers `modis_{y1}`, `viirs_{y1}`: every {y1} hotspot of medium or high confidence (low is not used) with the classes it was counted under: province, district, khg_id, kawasan, concession, licence_types, dmpg, peat, static (likely gas flare, volcano or offshore source), on_land (inside the village boundaries). |
| `summary.gpkg` | Layers `province` and `khg`: area, peat, burned area per year and {y0}-{yp}, MODIS {y1} hotspots (medium + high, static left out), hotspots per 100 km2, and the shares (%) of area, burned area {y0}-{yp} and hotspots inside concessions (`conc`), forest area (`kws`) and DMPG villages (`dmpg`). |

Bands of `status.vrt` (a paletted/unique-values renderer per band works best):

1. kawasan: 0 not mapped, 1 conservation, 2 protection forest, 3 production forest (HP, HPT), 4 convertible production (HPK), 5 other land use (APL), 6 water or undefined
2. concession: 0 none, 1 oil palm, 2 mining, 3 plantation forest (PPHTR), 4 forest concession (PBPH), 5 community forest (PPHKM) only; overlapping licences take the first type in this order
3. DMPG village: 0 no, 1 yes
4. peat (KLH peat land map, PPEG 2026): 0 no, 1 yes, 3 no peat information
5. KHG index (see `../khg_index.csv`), 0 outside every KHG
6. number of years burned, {y0}-{y1} (KLHK burned area)
7. burn years as bits: bit n set = burned in {y0} + n ({y0} = 1, {y0} + 1 = 2, {y0} + 2 = 4, ...)

Burned-area years that are incomplete as delivered show as low hectares per hotspot in `tables/t_completeness.csv`.
"""


def write_vrt(files, path):
    """Mosaic of the per-tile GeoTIFFs (same grid, same size) as a GDAL VRT, written without the GDAL command-line tools."""
    if not files:
        return
    from xml.sax.saxutils import escape
    with rasterio.open(files[0]) as r0:
        crs_wkt, c, (tw, th), nb, nd = r0.crs.to_wkt(), r0.transform.a, (r0.width, r0.height), r0.count, r0.nodata
        descr = r0.descriptions
    tr = {}
    for f in files:
        with rasterio.open(f) as r:
            tr[f] = (r.transform.c, r.transform.f)
    x0, y1 = min(v[0] for v in tr.values()), max(v[1] for v in tr.values())
    x1, y0 = max(v[0] for v in tr.values()) + tw * c, min(v[1] for v in tr.values()) - th * c
    W, H = int(round((x1 - x0) / c)), int(round((y1 - y0) / c))
    out = [f'<VRTDataset rasterXSize="{W}" rasterYSize="{H}">', f"  <SRS>{escape(crs_wkt)}</SRS>",
           f"  <GeoTransform>{x0}, {c}, 0, {y1}, 0, {-c}</GeoTransform>"]
    for b in range(1, nb + 1):
        out += [f'  <VRTRasterBand dataType="UInt16" band="{b}">', f"    <Description>{escape(descr[b - 1] or '')}</Description>",
                f"    <NoDataValue>{nd:g}</NoDataValue>"]
        for f in files:
            xo, yo = int(round((tr[f][0] - x0) / c)), int(round((y1 - tr[f][1]) / c))
            rel = Path(f).relative_to(Path(path).parent).as_posix()
            out += ["    <ComplexSource>", f'      <SourceFilename relativeToVRT="1">{escape(rel)}</SourceFilename>',
                    f"      <SourceBand>{b}</SourceBand>", f'      <SrcRect xOff="0" yOff="0" xSize="{tw}" ySize="{th}"/>',
                    f'      <DstRect xOff="{xo}" yOff="{yo}" xSize="{tw}" ySize="{th}"/>', f"      <NODATA>{nd:g}</NODATA>", "    </ComplexSource>"]
        out.append("  </VRTRasterBand>")
    out.append("</VRTDataset>")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def layers(cfg, pts, dist):
    """Review layers in <out>/layers: status.vrt (30 m status and burn years), hotspots_2026.gpkg (each 2026 hotspot with its classes)."""
    out = out_dir(cfg) / "layers"
    out.mkdir(parents=True, exist_ok=True)
    write_vrt(sorted((out / "tiles").glob("status_*.tif")), out / "status.vrt")
    y0, y1 = settings(cfg)["years"]
    (out / "README.md").write_text(LAYERS_README.format(y0=y0, y1=y1, yp=y1 - 1), encoding="utf-8")
    if not pts:
        return
    p = decode(pd.concat(pts, ignore_index=True), [n for n in SHIFT if n != "burn"])
    d = dist.set_index("kab")
    kidx = pd.read_csv(out_dir(cfg) / "khg_index.csv").set_index("idx")["khg_id"]
    kws = {0: "none", **{n + 1: k for n, k in enumerate(KWS_CODES)}}
    p = p.assign(province=p["kab"].map(d["province"]).fillna(""), district=p["kab"].map(d["district"]).fillna(""),
                 khg_id=p["khg"].map(kidx).fillna(""), kawasan=p["kws"].map(kws),
                 concession=(p["lic"] & 15) > 0, licence_types=p["lic"].map(lambda b: ",".join(k for k, v in LIC_BITS.items() if b & v)),
                 dmpg=p["dmpg"] > 0, peat=p["peat"].map({0: "no", 1: "yes", 3: "unknown"}), on_land=p["kab"] > 0)
    p = p[p["conf"].isin(["medium", "high"])].drop(columns=["kab", "khg", "kws", "lic", "ytd", "file", "year", "source"]).assign(source=p["source"])
    g = gpd.GeoDataFrame(p.drop(columns=["lon", "lat"]), geometry=gpd.points_from_xy(p["lon"], p["lat"]), crs=4326)
    now = settings(cfg)["years"][1]
    f = out / f"hotspots_{now}.gpkg"
    if f.exists():
        f.unlink()
    for src, sub in g.groupby("source"):
        sub.to_file(f, layer=f"{src}_{now}", driver="GPKG")


def collect(cfg, sel, dist, viirs_cut):
    s, out = settings(cfg), out_dir(cfg)
    cells, hot, chk, pts = [], [], [], []
    for ij in sel:
        files, empty = cache_paths(cfg, ij)
        if files[0].exists():
            cells.append(pd.read_parquet(files[0]))
            hot.append(pd.read_parquet(files[1]))
            chk.append(pd.read_parquet(files[2]))
            if files[3].exists():
                pts.append(pd.read_parquet(files[3]))
    cells = pd.concat(cells, ignore_index=True).groupby("key", as_index=False)["cells"].sum()
    cells = decode(cells)
    cells["area_ha"] = cells["cells"] * s["cell_m"] ** 2 / 1e4
    cells.to_parquet(out / "cells.parquet", index=False)
    hot = pd.concat(hot, ignore_index=True)
    hot = hot.groupby(["key", "source", "file", "year", "month", "conf", "static", "ytd"], as_index=False)["n"].sum()
    hot = decode(hot, [n for n in SHIFT if n != "burn"])
    hot.to_parquet(out / "hotspots.parquet", index=False)
    dist.to_csv(out / "districts.csv", index=False)
    chk = pd.concat(chk, ignore_index=True) if chk else pd.DataFrame()
    chk.to_csv(out / "checks_burned_tiles.csv", index=False)
    if len(sel) > 50:
        ref = reference_counts(cfg, viirs_cut)
        got = hot.groupby(["source", "file"], as_index=False)["n"].sum().rename(columns={"n": "n_tiles"})
        ref = ref.merge(got, on=["source", "file"], how="left").fillna({"n_tiles": 0})
        ref["outside_land_tiles"] = ref["n_file"] - ref["n_tiles"]
        ref.to_csv(out / "checks_hotspots.csv", index=False)
    meta = {"crs": s["crs"], "cell_m": s["cell_m"], "tile_cells": s["tile_cells"], "tiles": len(sel), "years": s["years"],
            "inputs": {"villages": s["villages"], "khg": cfg["inputs"]["khg"], "forest_area": cfg["inputs"]["forest_area"],
                       "licences": cfg["inputs"]["licences"], "dmpg": cfg["inputs"].get("dmpg"), "burned": cfg["inputs"]["burned"],
                       "peat": str(C.peat_path(cfg)) if not s.get("peat_vector") else s["peat_vector"]["path"], "modis": s["modis"], "viirs": s["viirs"]},
            "static_radius_m": s["static_radius_m"], "viirs_last": str(viirs_cut.date()),
            "modis_last": str(last_date(cfg, s["modis"]).date()),
            "kawasan_codes": KWS_CODES, "licence_bits": LIC_BITS, "peat_codes": {"0": "not peat", "1": "peat", "3": "no peat information"}}
    meta["raster_bands"] = "layers/status.vrt: 7 uint16 bands, nodata 65535 outside village land; each band carries its meaning as its description"
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    layers(cfg, pts, dist)
    log.info("%d cell rows, %d hotspot rows -> %s", len(cells), len(hot), out)


if __name__ == "__main__":
    main()
