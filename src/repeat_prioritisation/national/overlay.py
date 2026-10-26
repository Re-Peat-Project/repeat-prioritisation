#!/usr/bin/env python3
"""Land-status overlays for the profiled KHG: forest area function, peat ecosystem function (FEG), business licences
and the Bluebook target villages (with the DPG villages of the BRG atlas among them), crossed with peat, burned area and
this year's hotspots.

  repeat-national-overlay --config configs/examples/national_stage3.yaml

Reads the KHG written by `national.stage3 select` and writes, in <stage3>/overlay/:
  overlay_summary.csv   one row per KHG, layer and class: area, share of KHG and of peat, burned share, hotspots
  overlay_actors.csv    licence holders per KHG: area, peat burned, hotspots this year
  overlay_map.json      clipped, simplified polygons of each layer for the dashboard map

Areas come from a regular grid of points inside the KHG (cell size chosen from the KHG area), each point carrying its
peat flag, class in every layer, burned flag and licences. A point can sit in several licences, so licence areas
overlap and are never summed; "any licence" counts each point once. Counts of hotspots by class add back to the number
of this year's hotspots inside the KHG. The figures say where hotspots and burns fall, not who caused them.
5 km ring (overlay.ring_km): land within ring_km of any licence but inside none, the zone the Bluebook 2026 canal-block
data calls "Buffer 5 Kilometer". Licences are read out to ring_km beyond the KHG so that a licence next door still draws its
ring; only the part of a ring inside the KHG is counted. Per holder, the ring is the land within ring_km of its licences that
lies in no licence; rings of neighbouring holders overlap and are never summed. Distances are measured in the Albers
equal-area projection of profile.AEA (scale error within about 1 % over Indonesia).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
import shapely.ops
from pyproj import Transformer

from repeat_prioritisation.national import profile as P  # noqa: E402
from repeat_prioritisation.national import stage3 as S3  # noqa: E402

log = logging.getLogger("prioritas.overlay")

# forest area function (Fungsi code in the KWS layer) -> class
KWS_CLASS = {
    "cons": ["CA", "CAL", "SM", "SML", "TN", "TNL", "TWA", "TWAL", "TAHURA", "TB", "HSA (KSA)", "KSA/KPA", "KSAL/KPAL"],
    "hl": ["HL"], "prod": ["HP", "HPT"], "hpk": ["HPK"], "apl": ["APL"], "other": ["TUBUH AIR", "DANAU", "Belum terdefinisi"],
}
KWS_ORDER = ["cons", "hl", "prod", "hpk", "apl", "other", "none"]
KWS_LABEL = {"cons": "Conservation", "hl": "Protection forest", "prod": "Production forest", "hpk": "Convertible production",
             "apl": "Other land use", "other": "Water, undefined", "none": "Not mapped"}
FEG_ORDER = ["lindung", "budidaya", "none"]
FEG_LABEL = {"lindung": "Protected function", "budidaya": "Cultivation function", "none": "Not mapped"}
LIC_ORDER = ["sawit", "pbph", "pphkm", "pphtr", "tambang"]
LIC_VALUE = {"Perkebunan Kelapa Sawit": "sawit", "PBPH": "pbph", "PPHKM": "pphkm", "PPHTR": "pphtr", "Pertambangan": "tambang"}
LIC_LABEL = {"sawit": "Oil palm", "pbph": "Forest concession (PBPH)", "pphkm": "Community forest (PPHKM)",
             "pphtr": "Plantation forest (PPHTR)", "tambang": "Mining"}
CODE_TO_KWS = {c: k for k, cs in KWS_CLASS.items() for c in cs}

RING_ORDER = ["lic", "ring", "out"]
RING_LABEL = {"lic": "In a licence", "ring": "Within 5 km of a licence", "out": "Farther from licences"}

DEFAULT = {"overlay": {"top_actors": 8, "company_names": True, "max_licence_polygons": 120, "ring_km": 5},
           "inputs": {"forest_area": "landstatus/KWSHUTAN_AR_250K_2023_Transcripted.gpkg",
                      "peat_function": "landstatus/FEG__Indonesia__2017__Rev_Tipologi.gpkg",
                      "licences": "landstatus/ALL_Updade__IZIN_USAHA__PBPH_Perkebunan_HTRKM_Tambang__2025.gpkg"}}


def load_cfg(path):
    cfg = S3.load_cfg(path)
    for k, v in DEFAULT["inputs"].items():
        cfg["inputs"].setdefault(k, v)
    P._merge(cfg, {"overlay": dict(DEFAULT["overlay"], **cfg.get("overlay", {}))})
    return cfg


def peat_path(cfg):
    pe = (cfg.get("peat") or {}).get("extent") or (cfg.get("stage3") or {}).get("peat_extent")
    return pe if pe and Path(pe).exists() else None


def now_points(cfg, g):
    """This year's KLH hotspots inside g, kept levels only: x, y, month, high, on-peat (arrays)."""
    inp, data = cfg["inputs"], Path(cfg["data"])
    e = np.zeros(0)
    if not (inp.get("hotspots_now") and (data / inp["hotspots_now"]).exists()):
        return e, e, e.astype(int), e.astype(bool), e.astype(bool)
    h = P._read_mask(data / inp["hotspots_now"], g, columns=["layer", "C_LEVEL", "Kepercayaa"])
    if not len(h):
        return e, e, e.astype(int), e.astype(bool), e.astype(bool)
    lvl = h["C_LEVEL"].fillna(h["Kepercayaa"]).astype("string").str.lower().map(P.LEVEL)
    keep = lvl.isin(cfg["now"]["levels"]).to_numpy()
    h, lvl = h[keep], lvl[keep]
    xs, ys = h.geometry.x.to_numpy(), h.geometry.y.to_numpy()
    inside = shapely.contains_xy(g, xs, ys)
    xs, ys, lvl, h = xs[inside], ys[inside], lvl[inside], h[inside]
    pe = peat_path(cfg)
    ps = P.PeatSampler(pe) if pe else None
    onp = (ps.sample(ps.window(g), xs, ys) == 1) if ps is not None else np.ones(len(xs), bool)
    return xs, ys, h["layer"].str[:2].astype(int).to_numpy(), (lvl == "high").to_numpy(), onp


def peat_shape(cfg, g, tol):
    """The peat cells of the GFW extent inside g as one lon/lat geometry, simplified; None when the extent is missing."""
    pe = peat_path(cfg)
    if not pe:
        return None
    from rasterio.features import shapes
    ps = P.PeatSampler(pe)
    arr, tr = ps.window(g)
    m = arr == 1
    if not m.any():
        return None
    inv = Transformer.from_crs(ps.src.crs, 4326, always_xy=True)
    polys = [shapely.geometry.shape(geom) for geom, _ in shapes(m.astype(np.uint8), mask=m, transform=tr)]
    u = shapely.ops.transform(inv.transform, shapely.union_all(polys))
    u = shapely.intersection(shapely.make_valid(u), g).simplify(tol, preserve_topology=True)
    keep = [p for p in (u.geoms if u.geom_type.startswith("Multi") else [u]) if p.geom_type == "Polygon" and p.area > (3 * tol) ** 2]
    return shapely.MultiPolygon(keep) if keep else None


def grid(g_ll, cell=None):
    """Regular grid of points inside g (lon, lat arrays) and the cell area in km2."""
    tf, inv = Transformer.from_crs(4326, P.AEA, always_xy=True), Transformer.from_crs(P.AEA, 4326, always_xy=True)
    ga = shapely.ops.transform(tf.transform, g_ll)  # noqa: deprecated alias, still the simplest
    if cell is None:
        cell = max(100.0, round(np.sqrt(ga.area / 60000.0) / 50.0) * 50.0)
    x0, y0, x1, y1 = ga.bounds
    X, Y = np.meshgrid(np.arange(x0 + cell / 2, x1, cell), np.arange(y0 + cell / 2, y1, cell))
    X, Y = X.ravel(), Y.ravel()
    m = shapely.contains_xy(ga, X, Y)
    lon, lat = inv.transform(X[m], Y[m])
    return np.asarray(lon), np.asarray(lat), (cell / 1000.0) ** 2, cell


def to_aea(geoms):
    tf = Transformer.from_crs(4326, P.AEA, always_xy=True)
    return shapely.transform(geoms, lambda c: np.column_stack(tf.transform(c[:, 0], c[:, 1])))


def from_aea(geoms):
    inv = Transformer.from_crs(P.AEA, 4326, always_xy=True)
    return shapely.transform(geoms, lambda c: np.column_stack(inv.transform(c[:, 0], c[:, 1])))


def near_licences(lon, lat, lic_m, dist_m):
    """Points (lon, lat) against licence polygons in AEA metres: a mask of points inside any licence, and the
    (point, licence) index pairs closer than dist_m. Shared with investigations.dmpg."""
    tf = Transformer.from_crs(4326, P.AEA, always_xy=True)
    x, y = tf.transform(np.asarray(lon, float), np.asarray(lat, float))
    inside = np.zeros(len(x), bool)
    if not len(x) or not len(lic_m):
        return inside, np.zeros(0, int), np.zeros(0, int)
    tree, pts = shapely.STRtree(lic_m), shapely.points(x, y)
    inside[tree.query(pts, predicate="intersects")[0]] = True
    pi, li = tree.query(pts, predicate="dwithin", distance=dist_m)
    return inside, pi, li


def _read(path, g, cols):
    d = pyogrio.read_dataframe(path, mask=g, columns=cols)
    d = d[d.geometry.notna() & ~d.geometry.is_empty].copy()
    d["geometry"] = shapely.make_valid(d.geometry.values)
    return d.reset_index(drop=True)


def _first(points, layer, col):
    """Value of `col` of the layer polygon holding each point (first match), NaN outside."""
    j = gpd.sjoin(points[["geometry"]], layer[[col, "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    return j[col].reindex(points.index)


def _rings(geom, tol):
    g = geom.simplify(tol, preserve_topology=True) if tol else geom
    out = []
    for p in (list(g.geoms) if g.geom_type in ("MultiPolygon", "GeometryCollection") else [g]):
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        out.append([[[round(float(x), 4), round(float(y), 4)] for x, y in ring.coords] for ring in [p.exterior, *p.interiors]])
    return out


def _stats(layer, cls, order, labels, pts, hs, area_cell, khg_km2, peat_total):
    rows = []
    for c in order:
        m = (cls == c).to_numpy()
        if not m.any() and not (hs["cls"] == c).any():
            continue
        n_peat = int((m & pts["peat"].to_numpy()).sum())
        n_burn = int((m & pts["peat"].to_numpy() & pts["burned"].to_numpy()).sum())
        h = hs["cls"] == c
        rows.append({"layer": layer, "class": c, "label": labels[c], "area_km2": m.sum() * area_cell,
                     "share_khg": m.sum() * area_cell / khg_km2, "peat_km2": n_peat * area_cell,
                     "share_peat": n_peat * area_cell / peat_total if peat_total else np.nan,
                     "burned_peat_km2": n_burn * area_cell, "burned_share": n_burn / n_peat if n_peat else np.nan,
                     "hs_now": int(h.sum()), "hs_now_peat": int((h & hs["onp"]).sum())})
    return rows


def one(cfg, kid, name, g):
    inp, data, oc = cfg["inputs"], Path(cfg["data"]), cfg["overlay"]
    g = shapely.make_valid(g)
    lon, lat, area_cell, cell = grid(g)
    pts = gpd.GeoDataFrame({"peat": np.zeros(len(lon), bool), "burned": np.zeros(len(lon), bool)}, geometry=gpd.points_from_xy(lon, lat), crs=4326)
    pe = peat_path(cfg)
    if pe:
        ps = P.PeatSampler(pe)
        pts["peat"] = ps.sample(ps.window(g), lon, lat) == 1
    ycols = [f"BA_{y}" for y in range(2015, 2026)]
    b = _read(data / inp["burned"], g, ycols)
    if len(b):
        b = b[b[ycols].notna().any(axis=1)]
        if len(b):
            hit = gpd.sjoin(pts[["geometry"]], b[["geometry"]], how="inner", predicate="within")
            pts.loc[hit.index.unique(), "burned"] = True
    xs, ys, mon, hi, onp = now_points(cfg, g)
    hs = gpd.GeoDataFrame({"onp": np.asarray(onp, bool), "high": np.asarray(hi, bool)}, geometry=gpd.points_from_xy(xs, ys), crs=4326)
    khg_km2 = len(pts) * area_cell
    peat_total = float(pts["peat"].sum() * area_cell)

    kws = _read(data / inp["forest_area"], g, ["Fungsi"])
    kws["cls"] = kws["Fungsi"].map(CODE_TO_KWS).fillna("other")
    feg = _read(data / inp["peat_function"], g, ["FEG_KGHLTR"])
    feg["cls"] = np.where(feg["FEG_KGHLTR"].str.contains("Lindung", na=False), "lindung", "budidaya")
    ring_m = 1000.0 * oc["ring_km"]
    g_ring = from_aea(to_aea(g).buffer(ring_m))     # licences next door draw a ring into the KHG
    lic = _read(data / inp["licences"], g_ring, ["PERUSAHAAN", "IZIN_USAHA", "KEG_USAHA"])
    lic["cls"] = lic["IZIN_USAHA"].map(LIC_VALUE)
    lic_m = to_aea(lic.geometry.values) if len(lic) else np.array([])
    vil = _read(data / inp["villages"], g, ["OBJECTID", "DESA_2023", "KEC_2023", "KABKO_2023"])
    vil["dmpg"] = vil["OBJECTID"].isin(P.dmpg_ids(data / inp["dmpg"])) if inp.get("dmpg") else False

    rows, report, pcs = [], {}, {}
    for layer, df, col, order, labels in (("forest", kws, "cls", KWS_ORDER, KWS_LABEL), ("feg", feg, "cls", FEG_ORDER, FEG_LABEL)):
        pc = _first(pts, df, col).fillna("none") if len(df) else pd.Series("none", index=pts.index)
        hc = _first(hs, df, col).fillna("none") if len(df) and len(hs) else pd.Series("none", index=hs.index, dtype=object)
        hs2 = pd.DataFrame({"cls": hc.to_numpy(), "onp": hs["onp"].to_numpy()})
        pcs[layer] = pc
        rows += _stats(layer, pc, order, labels, pts, hs2, area_cell, khg_km2, peat_total)
        report[layer] = int(sum(r["hs_now"] for r in rows if r["layer"] == layer))

    # licences: overlapping, so one flag per type and one for any licence
    pl = gpd.sjoin(pts[["geometry"]], lic[["cls", "PERUSAHAAN", "KEG_USAHA", "geometry"]], how="inner", predicate="within") if len(lic) else pd.DataFrame()
    hl = gpd.sjoin(hs[["geometry", "onp"]], lic[["cls", "PERUSAHAAN", "geometry"]], how="inner", predicate="within") if len(lic) and len(hs) else pd.DataFrame()
    for key in LIC_ORDER + ["any"]:
        pm = pd.Series(False, index=pts.index)
        hm = pd.Series(False, index=hs.index)
        if len(pl):
            pm[(pl.index if key == "any" else pl.index[pl["cls"] == key]).unique()] = True
        if len(hl):
            hm[(hl.index if key == "any" else hl.index[hl["cls"] == key]).unique()] = True
        cls = pd.Series(np.where(pm, "in", "out"), index=pts.index)
        hs2 = pd.DataFrame({"cls": np.where(hm, "in", "out"), "onp": hs["onp"].to_numpy()})
        on_lind, on_prot = (pcs["feg"] == "lindung").to_numpy(), pcs["forest"].isin(["cons", "hl"]).to_numpy()
        r = _stats("licence_" + key, cls, ["in"], {"in": LIC_LABEL.get(key, "Any licence")}, pts, hs2, area_cell, khg_km2, peat_total)
        for x in r:
            x["lindung_km2"] = float((pm.to_numpy() & on_lind).sum() * area_cell)
            x["forest_protected_km2"] = float((pm.to_numpy() & on_prot).sum() * area_cell)
        rows += r if r else [{"layer": "licence_" + key, "class": "in", "label": LIC_LABEL.get(key, "Any licence"), "area_km2": 0.0, "share_khg": 0.0,
                              "peat_km2": 0.0, "share_peat": 0.0, "burned_peat_km2": 0.0, "burned_share": np.nan, "hs_now": 0, "hs_now_peat": 0,
                              "lindung_km2": 0.0, "forest_protected_km2": 0.0}]
    # 5 km ring: in a licence / within ring_km of one / farther (classes add up)
    none = (np.zeros(0, bool), np.zeros(0, int), np.zeros(0, int))
    pin, ppi, pli = near_licences(lon, lat, lic_m, ring_m)
    hin, hpi, hli = near_licences(hs.geometry.x, hs.geometry.y, lic_m, ring_m) if len(hs) else none
    ring_cls = lambda n, inside, pi: np.where(inside, "lic", np.where(np.isin(np.arange(n), pi), "ring", "out"))
    rows += _stats("ring", pd.Series(ring_cls(len(pts), pin, ppi), index=pts.index), RING_ORDER, RING_LABEL, pts,
                   pd.DataFrame({"cls": ring_cls(len(hs), hin, hpi), "onp": hs["onp"].to_numpy()}), area_cell, khg_km2, peat_total)
    comp = lic["PERUSAHAAN"].to_numpy() if len(lic) else np.array([], object)
    rp = pd.DataFrame({"i": ppi, "company": comp[pli]}).drop_duplicates()     # ring points per holder, outside every licence
    rp = rp[~pin[rp["i"].to_numpy(int)]]
    rh = pd.DataFrame({"i": hpi, "company": comp[hli]}).drop_duplicates()
    rh = rh[~hin[rh["i"].to_numpy(int)]]

    # target villages
    pv = pd.Series(False, index=pts.index)
    hv = pd.Series(False, index=hs.index)
    if len(vil):
        j = gpd.sjoin(pts[["geometry"]], vil[["geometry"]], how="inner", predicate="within")
        pv[j.index.unique()] = True
        if len(hs):
            hv[gpd.sjoin(hs[["geometry"]], vil[["geometry"]], how="inner", predicate="within").index.unique()] = True
    rows += _stats("village", pd.Series(np.where(pv, "in", "out"), index=pts.index), ["in"], {"in": "Target village"}, pts,
                   pd.DataFrame({"cls": np.where(hv, "in", "out"), "onp": hs["onp"].to_numpy()}), area_cell, khg_km2, peat_total)
    # DPG villages of the BRG atlas (a subset of the target villages): context, not scored
    pd_ = pd.Series(False, index=pts.index)
    hd = pd.Series(False, index=hs.index)
    dv = vil[vil["dmpg"]] if len(vil) else vil
    if len(dv):
        pd_[gpd.sjoin(pts[["geometry"]], dv[["geometry"]], how="inner", predicate="within").index.unique()] = True
        if len(hs):
            hd[gpd.sjoin(hs[["geometry"]], dv[["geometry"]], how="inner", predicate="within").index.unique()] = True
    rows += _stats("dmpg", pd.Series(np.where(pd_, "in", "out"), index=pts.index), ["in"], {"in": "DPG village"}, pts,
                   pd.DataFrame({"cls": np.where(hd, "in", "out"), "onp": hs["onp"].to_numpy()}), area_cell, khg_km2, peat_total)

    for r in rows:
        r.update({"khg_id": kid, "khg": name})
    # hotspots by class add back to the hotspots inside the KHG
    for layer in ("forest", "feg"):
        tot = sum(r["hs_now"] for r in rows if r["layer"] == layer)
        if tot != len(hs):
            log.warning("%s %s: class hotspots %d != hotspots %d", kid, layer, tot, len(hs))

    # actors: licence holders, by area, burned peat and hotspots this year
    # holders with a licence or a ring in the KHG
    actors = []
    peat, burned, onp = pts["peat"].to_numpy(), pts["burned"].to_numpy(), hs["onp"].to_numpy()
    for comp in sorted((set(pl["PERUSAHAAN"]) if len(pl) else set()) | set(rp["company"])):
        idx = pl.index[pl["PERUSAHAAN"] == comp].unique() if len(pl) else pd.Index([], dtype=int)
        n_hs = int(hl.loc[hl["PERUSAHAAN"] == comp].index.nunique()) if len(hl) else 0
        n_hs_p = int(hl.loc[(hl["PERUSAHAAN"] == comp) & hl["onp"]].index.nunique()) if len(hl) else 0
        lr = lic[lic["PERUSAHAAN"] == comp]
        ri = rp.loc[rp["company"] == comp, "i"].to_numpy(int)
        hi_ = rh.loc[rh["company"] == comp, "i"].to_numpy(int)
        actors.append({"khg_id": kid, "khg": name, "company": comp, "type": ", ".join(sorted(set(lr["cls"].dropna().map(lambda c: LIC_LABEL.get(c, c))))),
                       "activity": ", ".join(sorted(set(lr["KEG_USAHA"].dropna().astype(str)))),
                       "area_km2": len(idx) * area_cell, "share_khg": len(idx) * area_cell / khg_km2,
                       "burned_peat_km2": int((pts.loc[idx, "peat"] & pts.loc[idx, "burned"]).sum()) * area_cell,
                       "lindung_km2": int((pcs["feg"].loc[idx] == "lindung").sum()) * area_cell,
                       "forest_protected_km2": int(pcs["forest"].loc[idx].isin(["cons", "hl"]).sum()) * area_cell,
                       "hs_now": n_hs, "hs_now_peat": n_hs_p,
                       "ring_km2": len(ri) * area_cell, "ring_peat_km2": int(peat[ri].sum()) * area_cell,
                       "ring_burned_peat_km2": int((peat[ri] & burned[ri]).sum()) * area_cell,
                       "ring_hs_now": len(hi_), "ring_hs_now_peat": int(onp[hi_].sum())})
    actors.sort(key=lambda a: (-(a["hs_now"] + a["ring_hs_now"]), -a["area_km2"]))

    # map layers
    tol = 0.0003 + 0.00002 * np.sqrt(khg_km2)
    cl = lambda geoms: shapely.intersection(shapely.make_valid(geoms), g)
    mp = {"forest": [], "feg": [], "licence": [], "village": [], "ring": []}
    for df, key in ((kws, "forest"), (feg, "feg")):
        if len(df):
            gc = cl(df.geometry.values)
            for c in df["cls"].unique():
                u = shapely.union_all(gc[(df["cls"] == c).to_numpy()])
                if not u.is_empty:
                    mp[key].append({"c": c, "r": _rings(u, tol)})
    if len(lic):
        gc = cl(lic.geometry.values)
        lic2 = lic.assign(geometry=gc)
        lic2 = lic2[~lic2.geometry.is_empty]
        for (comp, c), grp in lic2.groupby(["PERUSAHAAN", "cls"]):
            u = shapely.union_all(grp.geometry.values)
            mp["licence"].append({"c": c, "n": comp if oc["company_names"] else "", "a": float(u.area), "r": _rings(u, tol)})
        mp["licence"].sort(key=lambda d: -d["a"])
        for d in mp["licence"]:
            d.pop("a")
        mp["licence"] = mp["licence"][: oc["max_licence_polygons"]]
    if len(lic):
        lu = shapely.union_all(shapely.make_valid(lic_m))
        for c, u in (("lic", lu), ("ring", lu.buffer(ring_m).difference(lu))):
            u = shapely.intersection(shapely.make_valid(from_aea(u)), g)
            if not u.is_empty:
                mp["ring"].append({"c": c, "r": _rings(u, tol)})
    if len(vil):
        gc = cl(vil.geometry.values)
        for k, geom in enumerate(gc):
            if not geom.is_empty:
                mp["village"].append({"n": f'{vil["DESA_2023"].iloc[k]}, {vil["KEC_2023"].iloc[k]}', "r": _rings(geom, tol),
                                      **({"d": 1} if vil["dmpg"].iloc[k] else {})})
    mp["cell_m"] = cell
    return rows, actors, mp


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--only", nargs="*", help="khg_id to compute (default: all in the stage 3 selection)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_cfg(a.config)
    sel = gpd.read_file(cfg["khg"])
    if a.only:
        sel = sel[sel.khg_id.isin(a.only)]
    out = Path(cfg["_dir"]) / "overlay"
    out.mkdir(parents=True, exist_ok=True)
    rows, actors, maps = [], [], {}
    for r in sel.itertuples():
        log.info("%s %s", r.khg_id, r.nama)
        rw, ac, mp = one(cfg, r.khg_id, r.nama, r.geometry)
        rows += rw
        actors += ac
        maps[r.khg_id] = mp
    top = cfg["overlay"]["top_actors"]
    df = pd.DataFrame(rows)
    num = [c for c in df.columns if df[c].dtype == float]
    df[num] = df[num].round(4)
    cols = ["khg_id", "khg", "layer", "class", "label"] + [c for c in df.columns if c not in ("khg_id", "khg", "layer", "class", "label")]
    df[cols].to_csv(out / "overlay_summary.csv", index=False)
    ac = pd.DataFrame(actors)
    if len(ac):
        if not cfg["overlay"]["company_names"]:
            ac["company"] = ac.groupby("khg_id").cumcount().map(lambda k: f"licence holder {k + 1}")
        ac = ac.round(4)
        ac.to_csv(out / "overlay_actors.csv", index=False)
        ac.groupby("khg_id").head(top).to_csv(out / "overlay_actors_top.csv", index=False)
    (out / "overlay_map.json").write_text(json.dumps(maps, separators=(",", ":")), encoding="utf-8")
    log.info("%d KHG -> %s", len(maps), out)


if __name__ == "__main__":
    main()
