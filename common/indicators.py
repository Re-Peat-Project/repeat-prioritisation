"""Per-unit indicators for one KHG, computed from the cache and vector layers."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

from repeat_common import tma as TMA
from repeat_common.grid import Grid, label_raster, read, vector_to_grid_mask, warp_to_grid

log = logging.getLogger("prioritas.indicators")


class Zonal:
    """Fast zonal statistics over a label raster (unit index, -1 = outside)."""

    def __init__(self, labels: np.ndarray, n: int, max_median_px: int = 3_000_000, seed: int = 0):
        self.lab = labels.ravel()
        self.n = n
        self.inside = self.lab >= 0
        rng = np.random.default_rng(seed)
        idx = np.flatnonzero(self.inside)
        self.med_idx = idx if idx.size <= max_median_px else np.sort(rng.choice(idx, max_median_px, replace=False))

    def mean(self, arr: np.ndarray) -> np.ndarray:
        a = arr.ravel()
        ok = self.inside & np.isfinite(a)
        s = np.bincount(self.lab[ok], weights=a[ok], minlength=self.n)
        c = np.bincount(self.lab[ok], minlength=self.n)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(c > 0, s / c, np.nan)

    def share(self, mask: np.ndarray) -> np.ndarray:
        return self.mean(mask.astype("float32"))

    def median(self, arr: np.ndarray) -> np.ndarray:
        a = arr.ravel()[self.med_idx]
        lab = self.lab[self.med_idx]
        ok = np.isfinite(a)
        s = pd.Series(a[ok]).groupby(lab[ok]).median()
        out = np.full(self.n, np.nan)
        out[s.index.to_numpy()] = s.to_numpy()
        return out


def _years_mean(fn, years):
    vals = [fn(y) for y in years]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmean(np.stack(vals), axis=0)


def _nan_if_none(v):
    return np.nan if v is None else v


def compute(cfg: dict, khg_id: str, units_k, grid: Grid, cache: Path) -> pd.DataFrame:
    import geopandas as gpd
    p = cfg["params"]
    yb = list(range(cfg["years"]["baseline"][0], cfg["years"]["baseline"][1] + 1))
    yv = list(cfg["years"]["validation"])
    yel = [y for y in cfg["years"]["elnino"] if y in yb]
    up = units_k.to_crs(grid.crs).reset_index(drop=True)
    n = len(up)
    lab = label_raster(up, grid)
    Z = Zonal(lab, n)
    df = pd.DataFrame({"khg_id": khg_id, "unit_id": up["unit_id"].values,
                       "area_km2": up.geometry.area.values / 1e6})
    ann = cache / "annual"

    def layer(name, y):
        f = ann / f"{name}_{y}.tif"
        return read(f) if f.exists() else None

    # ---------------- urgency ----------------
    df["u_deficit"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.mean(a))(layer("deficit", y)), yb))
    df["u_deficit_elnino"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.mean(a))(layer("deficit", y)), yel)) if yel else np.nan
    df["u_ndmi"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.median(a))(layer("ndmi", y)), yb))
    df["u_ndvi"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.median(a))(layer("ndvi", y)), yb))
    df["u_dry_days_mean"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.mean(a))(layer("drymean", y)), yb))
    df["u_dryspell"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.mean(a))(layer("dryspell", y)), yb))
    df["u_spell14"] = _nan_if_none(_years_mean(lambda y: (lambda a: None if a is None else Z.mean(a))(layer("spell14", y)), yb))

    wcf = cache / "static" / "worldcover.tif"
    wc = read(wcf) if wcf.exists() else None

    # water balance per unit: WB = P (1 - interception[land cover]) (1 - C) - ET, monthly
    clim = cache / "climate"
    icpt = np.zeros(n)
    if wc is not None:
        for cls, v in (p["interception_by_class"] or {}).items():
            icpt += float(v) * Z.share(wc == int(cls))
    wb_all, dm = [], []
    for y in yb:
        fp, fe = clim / f"ppt_{y}.tif", clim / f"aet_{y}.tif"
        if not (fp.exists() and fe.exists()):
            continue
        P = np.stack([Z.mean(warp_to_grid(str(fp), grid, band=b)) for b in range(1, 13)])
        E = np.stack([Z.mean(warp_to_grid(str(fe), grid, band=b)) for b in range(1, 13)])
        wb = P * (1 - icpt) * (1 - float(p["runoff_coefficient"])) - E
        wb_all.append(wb)
        dm.append((wb < 0).sum(axis=0).astype(float))
    if wb_all:
        df["u_wb_mean"] = np.mean(np.concatenate(wb_all), axis=0)
        df["u_deficit_months"] = np.mean(np.stack(dm), axis=0)
    else:
        df["u_wb_mean"] = np.nan
        df["u_deficit_months"] = np.nan

    burned_b = [layer("burned", y) for y in yb]
    burned_b = [b for b in burned_b if b is not None]
    burned_any = None
    if burned_b:
        st = np.stack(burned_b)
        freq = np.nanmean(st, axis=0)
        df["u_fire_freq"] = Z.mean(freq)
        burned_any = np.nanmax(st, axis=0) > 0
    else:
        df["u_fire_freq"] = np.nan

    hp = cache / "hotspots.csv"
    pts = None
    if hp.exists():
        h = pd.read_csv(hp)
        if len(h):
            pts = gpd.GeoDataFrame(h, geometry=gpd.points_from_xy(h.longitude, h.latitude), crs=4326).to_crs(grid.crs)
            j = gpd.sjoin(pts, up[["unit_id", "geometry"]], predicate="within", how="inner")
            cnt = j[j["year"].isin(yb)].groupby("unit_id").size()
            df["u_hotspot"] = df["unit_id"].map(cnt).fillna(0).values / df["area_km2"].values / max(len(yb), 1)
        else:
            df["u_hotspot"] = 0.0
    else:
        df["u_hotspot"] = np.nan

    canals = cfg["vectors"].get("canals")
    canal_mask = None
    if canals:
        cg = gpd.read_file(canals).to_crs(grid.crs)
        inter = gpd.overlay(up[["unit_id", "geometry"]], cg[["geometry"]].assign(_c=1), how="intersection",
                            keep_geom_type=False)
        length = inter.assign(L=inter.geometry.length).groupby("unit_id")["L"].sum() / 1000.0
        df["u_canal_density"] = df["unit_id"].map(length).fillna(0).values / df["area_km2"].values
        canal_mask = vector_to_grid_mask(cg, grid)
    else:
        df["u_canal_density"] = np.nan

    dcan = None
    if canal_mask is not None and canal_mask.any():
        dcan = ndimage.distance_transform_edt(~canal_mask, sampling=grid.res)

    # water table (TMA): SiTMAT folder or CSV, see common/tma.py
    tma = TMA.per_unit(TMA.load(cfg, yb), up, p["tma_threshold_m"], p["tma_max_gap_days"])
    for c_ in ("u_tma", "u_tma_recession", "n_tma_stations"):
        df[c_] = tma[c_].values

    # ---------------- impact ----------------
    pdp = cfg["rasters"].get("peat_depth")
    if pdp:
        thick = warp_to_grid(pdp, grid) * float(p.get("peat_depth_scale", 1.0))     # to metres (0.01 if the raster is in cm)
        df["i_peat_depth"] = Z.mean(thick)
        # water stock (m of water per m2): water content 0.8 of peat volume, 0.7 where canals drain it
        wcr = np.full(grid.shape, float(p["water_content_natural"]), "float32")
        if dcan is not None:
            wcr[dcan <= p["l_inf_m"]] = float(p["water_content_canalised"])
        df["i_water_stock"] = Z.mean(thick * wcr)
    else:
        df["i_peat_depth"] = np.nan
        df["i_water_stock"] = np.nan
    prot = cfg["vectors"].get("protected")
    if prot and prot.get("path"):
        pg = gpd.read_file(prot["path"])
        if prot.get("field"):
            pg = pg[pg[prot["field"]].astype(str).str.lower().isin([str(v).lower() for v in prot["values"]])]
        df["i_protected"] = Z.share(vector_to_grid_mask(pg, grid, all_touched=False))
    else:
        df["i_protected"] = np.nan
    sett = cfg["vectors"].get("settlements")
    if sett:
        sm = vector_to_grid_mask(sett, grid)
        dist = ndimage.distance_transform_edt(~sm, sampling=grid.res) if sm.any() else np.full(grid.shape, np.inf)
        df["i_exposure"] = Z.share(dist <= p["exposure_m"])
    else:
        df["i_exposure"] = np.nan
    df["i_forest"] = Z.share(np.isin(wc, p["forest_classes"])) if wc is not None else np.nan

    # ---------------- feasibility ----------------
    if dcan is not None:
        lim = np.full(grid.shape, float(p["l_inf_m"]), dtype="float32")
        if burned_any is not None:
            lim[burned_any] = float(p["l_inf_burnt_m"])
        df["f_reach"] = Z.share(dcan <= lim)
    else:
        df["f_reach"] = np.nan

    water = np.zeros(grid.shape, dtype=bool)
    wsf = cache / "static" / "water_season.tif"
    if wsf.exists():
        ws = read(wsf)
        water |= np.nan_to_num(ws) >= p["water_min_months"]
    for key in ("rivers", "lakes", "tidal"):
        if cfg["vectors"].get(key):
            water |= vector_to_grid_mask(cfg["vectors"][key], grid)
    df["tidal_share"] = Z.share(vector_to_grid_mask(cfg["vectors"]["tidal"], grid, all_touched=False)) \
        if cfg["vectors"].get("tidal") else 0.0
    if water.any():
        dist, inds = ndimage.distance_transform_edt(~water, sampling=grid.res, return_indices=True)
        df["f_water_dist"] = Z.mean(dist)
        dtm = cfg["rasters"].get("dtm")
        if dtm:
            z = warp_to_grid(dtm, grid)
            zw = z[inds[0], inds[1]]
            df["f_lift"] = Z.median(np.clip(z - zw, 0, None))
        else:
            df["f_lift"] = np.nan
    else:
        df["f_water_dist"] = np.nan
        df["f_lift"] = np.nan

    roads = cfg["vectors"].get("roads")
    if roads:
        rm = vector_to_grid_mask(roads, grid)
        df["f_access"] = Z.mean(ndimage.distance_transform_edt(~rm, sampling=grid.res)) if rm.any() else np.nan
    else:
        df["f_access"] = np.nan

    # ---------------- canal-block adequacy (metrik IPG) ----------------
    df["u_ipg_gap"] = np.nan
    for c_ in ("m_ipg", "n_sekat_ada", "n_sekat_perlu", "sekat_tambahan", "kemiringan_kanal"):
        df[c_] = np.nan
    dtm = cfg["rasters"].get("dtm")
    if canals and dtm:
        cgi = gpd.read_file(canals).to_crs(grid.crs)
        f_ = p.get("ipg_canal_class_field")
        if f_ and f_ in cgi.columns:
            cgi = cgi[cgi[f_].astype(str).str.lower().isin([c.lower() for c in p["ipg_canal_classes"]])]
        if len(cgi):
            z = warp_to_grid(dtm, grid)
            gy, gx = np.gradient(z, grid.res)
            slope = np.hypot(gx, gy)
            cm = vector_to_grid_mask(cgi, grid)
            slope_c = Z.median(np.where(cm, slope, np.nan))
            inter = gpd.overlay(up[["unit_id", "geometry"]], cgi[["geometry"]].assign(_c=1),
                                how="intersection", keep_geom_type=False)
            L = df["unit_id"].map(inter.assign(L=inter.geometry.length).groupby("unit_id")["L"].sum()).fillna(0).values
            fac = 2.0 if str(p["ipg_category"]).upper() == "B" else 1.0
            with np.errstate(divide="ignore", invalid="ignore"):
                js = np.clip(float(p["ipg_dA_m"]) / slope_c, p["ipg_js_min_m"], p["ipg_js_max_m"]) * fac
            need = np.where(L > 0, np.ceil(L / js), 0)
            df["kemiringan_kanal"] = slope_c
            df["n_sekat_perlu"] = need
            blk = cfg["vectors"].get("blocks")
            if blk:
                bg = gpd.read_file(blk).to_crs(grid.crs)
                jb = gpd.sjoin(bg, up[["unit_id", "geometry"]], predicate="within", how="inner")
                have = df["unit_id"].map(jb.groupby("unit_id").size()).fillna(0).values
                df["n_sekat_ada"] = have
                with np.errstate(divide="ignore", invalid="ignore"):
                    m = np.where(need > 0, have / need, np.nan)
                df["m_ipg"] = m
                df["u_ipg_gap"] = np.where(need > 0, 1 - np.minimum(1, m), 0.0)
                df["sekat_tambahan"] = np.maximum(0, need - have)
            else:
                df["sekat_tambahan"] = need

    # ---------------- land management ----------------
    con = cfg["vectors"].get("concessions") or {}
    df["pengelola"] = "Non-konsesi"
    df["porsi_dikecualikan"] = 0.0
    if con.get("path"):
        cg2 = gpd.read_file(con["path"]).to_crs(grid.crs)
        tf = con.get("type_field")
        cg2["_tipe"] = cg2[tf].astype(str) if tf and tf in cg2.columns else "Konsesi"
        ov = gpd.overlay(up[["unit_id", "geometry"]], cg2[["_tipe", "geometry"]], how="intersection",
                         keep_geom_type=False)
        if len(ov):
            ov["a"] = ov.geometry.area / 1e6
            share = ov.groupby(["unit_id", "_tipe"])["a"].sum().unstack(fill_value=0)
            share = share.div(df.set_index("unit_id")["area_km2"].reindex(share.index), axis=0)
            dom = share.idxmax(axis=1).where(share.max(axis=1) >= 0.5, "Campuran")
            df["pengelola"] = df["unit_id"].map(dom).fillna("Non-konsesi").values
            excl = [x for x in (con.get("exclude_types") or []) if x in share.columns]
            if excl:
                df["porsi_dikecualikan"] = df["unit_id"].map(share[excl].sum(axis=1)).fillna(0).values

    # ---------------- validation targets (years not used above) ----------------
    bv = [layer("burned", y) for y in yv]
    bv = [b for b in bv if b is not None]
    df["v_burned_frac"] = Z.mean(np.nanmax(np.stack(bv), axis=0)) if bv else np.nan
    if pts is not None:
        j = gpd.sjoin(pts, up[["unit_id", "geometry"]], predicate="within", how="inner")
        cnt = j[j["year"].isin(yv)].groupby("unit_id").size()
        df["v_hotspot"] = df["unit_id"].map(cnt).fillna(0).values / df["area_km2"].values / max(len(yv), 1)
    else:
        df["v_hotspot"] = np.nan

    log.info("KHG %s: indicators for %d units", khg_id, n)
    return df
