#!/usr/bin/env python3
"""Summary tables of burned area and hotspots by land status, from the tallies of `repeat-national-fire`.

  repeat-national-fire-tables --config configs/examples/national_profile.yaml

Reads <out>/fire_landstatus/cells.parquet and hotspots.parquet and writes, in the same folder:
  area.parquet       island, province, in_khg, kawasan, licence bits, dmpg, peat -> area_ha, burned_<year>_ha, burned_any_ha,
                     burned_2plus_ha (2015-2026)
  hot.parquet        the same classes and source, year, month, conf, static, ytd -> n
  khg.parquet        per KHG and the same classes (no province) -> area and burned measures
  tables/*.csv       report tables, each with `basis` = all (all land) or peat (KLH peat cells):
                     t_times_burned (area burned 0, 1, 2, 3, 4+ times in the burn years, by concession, forest group, DMPG)
                     t_national, t_concession_x_forest, t_licence_type, t_forest_function, t_dmpg, t_island, t_province, t_khg,
                     t_hotspots_year (VIIRS per year and land status, full year and year to date), t_modis_month
  hotspots_outside_villages.csv  hotspots outside the village boundaries (sea, neighbouring countries), left out of every table
  checks.csv         totals that must agree: area and hotspots across tables, burned area against the exact polygon area
Default hotspot counts: medium and high confidence, static sources left out; MODIS 2026 is the KLH series (headline), VIIRS the
trend. A licence type table counts overlapping licences once per type, so its rows do not add up; the concession rows do.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from repeat_prioritisation.national import fire_landstatus as F
from repeat_prioritisation.national import land as L

log = logging.getLogger("prioritas.fire_tables")

KWS = {0: "none", **{n + 1: k for n, k in enumerate(F.KWS_CODES)}}
KWS_LABEL = {"cons": "Conservation", "hl": "Protection forest", "prod": "Production forest (HP, HPT)", "hpk": "Convertible production (HPK)",
             "apl": "Other land use (APL)", "other": "Water, undefined", "none": "Not mapped"}
KWS_GROUP = {"cons": "kawasan", "hl": "kawasan", "prod": "kawasan", "hpk": "kawasan", "apl": "apl", "other": "other", "none": "other"}
GROUP_LABEL = {"kawasan": "Forest area (kawasan hutan)", "apl": "Other land use (APL)", "other": "Water, undefined or not mapped"}
LIC_PRIMARY = [("sawit", 1), ("tambang", 2), ("pphtr", 4), ("pbph", 8)]      # concession types, first set bit wins (as national.tenure)
LIC_LABEL = {"sawit": "Oil palm", "tambang": "Mining", "pphtr": "Plantation forest (PPHTR)", "pbph": "Forest concession (PBPH)",
             "pphkm": "Community forest (PPHKM)", "none": "No concession"}
CONC_MASK = 1 | 2 | 4 | 8                                                     # PPHKM (16) is not a concession


def primary(bits):
    out = np.full(len(bits), "none", object)
    for name, b in reversed(LIC_PRIMARY):
        out[(bits & b) > 0] = name
    return out


def classes(df, dist, khg_index):
    """Decoded class columns from the raw tallies."""
    d = dist.set_index("kab")
    df = df.assign(island=df["kab"].map(d["island"]).fillna("Outside village boundaries"),
                   province=df["kab"].map(d["province"]).fillna("Outside village boundaries"),
                   in_khg=df["khg"] > 0, kawasan=df["kws"].map(KWS),
                   concession=primary(df["lic"].to_numpy()), lic_bits=df["lic"], dmpg=df["dmpg"] > 0, peat=df["peat"])
    df["forest_group"] = df["kawasan"].map(KWS_GROUP)
    df["khg_id"] = df["khg"].map(khg_index).fillna("")
    return df


def burned_measures(cells, years):
    for n, y in enumerate(years):
        cells[f"burned_{y}_ha"] = np.where((cells["burn"].to_numpy() >> n) & 1, cells["area_ha"], 0.0)
    nb = sum(((cells["burn"].to_numpy() >> n) & 1) for n in range(len(years)))
    cells["burned_any_ha"] = np.where(nb >= 1, cells["area_ha"], 0.0)
    cells["burned_2plus_ha"] = np.where(nb >= 2, cells["area_ha"], 0.0)
    return cells


def add_basis(df):
    """Rows for all land and again for the peat cells only (column basis)."""
    return pd.concat([df.assign(basis="all"), df[df["peat"] == 1].assign(basis="peat")], ignore_index=True)


def measures(area, hot, dims, years, viirs_years):
    """Area, burned and hotspot measures by `dims` (+ basis). Hotspots: medium and high confidence, static left out."""
    num = ["area_ha"] + [f"burned_{y}_ha" for y in years] + ["burned_any_ha", "burned_2plus_ha"]
    a = area.groupby(["basis"] + dims, as_index=False)[num].sum()
    h = hot[hot["conf"].isin(["medium", "high"]) & ~hot["static"]]
    parts = []
    m = h[h["source"] == "modis"]
    parts.append(m.groupby(["basis"] + dims)["n"].sum().rename("modis_2026_n"))
    parts.append(m[m["conf"] == "high"].groupby(["basis"] + dims)["n"].sum().rename("modis_2026_high_n"))
    s = hot[(hot["source"] == "modis") & hot["static"] & hot["conf"].isin(["medium", "high"])]
    parts.append(s.groupby(["basis"] + dims)["n"].sum().rename("modis_2026_static_n"))
    v = h[h["source"] == "viirs"]
    for y in viirs_years:
        parts.append(v[v["year"] == y].groupby(["basis"] + dims)["n"].sum().rename(f"viirs_{y}_n"))
        parts.append(v[(v["year"] == y) & v["ytd"]].groupby(["basis"] + dims)["n"].sum().rename(f"viirs_{y}_ytd_n"))
    hh = pd.concat(parts, axis=1).reset_index() if parts else pd.DataFrame(columns=["basis"] + dims)
    out = a.merge(hh, on=["basis"] + dims, how="outer")
    hc = [c for c in out.columns if c.endswith("_n")]
    out[hc] = out[hc].fillna(0).astype(int)
    out[num] = out[num].fillna(0.0).round(2)
    return out


def summary_attrs(A, H, key, years):
    """One row per `key` value (all land): area, peat, burned per year and 2015-2025, MODIS 2026 hotspots (medium + high, static left
    out), rate per 100 km2, and the shares of burned area 2015-2025 and of hotspots inside concessions, forest area and DMPG villages."""
    past = [f"burned_{y}_ha" for y in years if y <= 2025]
    a = A[A["basis"] == "all"].assign(burned_1525_ha=lambda x: x[past].sum(axis=1))
    h = H[(H["basis"] == "all") & (H["source"] == "modis") & H["conf"].isin(["medium", "high"]) & ~H["static"]]
    out = a.groupby(key)[["area_ha", "burned_1525_ha"] + [f"burned_{y}_ha" for y in years]].sum()
    out["peat_ha"] = A[A["basis"] == "peat"].groupby(key)["area_ha"].sum()
    out["modis26"] = h.groupby(key)["n"].sum()
    out["modis26_peat"] = h[h["peat"] == 1].groupby(key)["n"].sum()
    for name, m_a, m_h in (("conc", a["concession_any"], h["concession_any"]), ("kws", a["forest_group"] == "kawasan", h["forest_group"] == "kawasan"),
                           ("dmpg", a["dmpg"], h["dmpg"])):
        out[f"area_{name}_pct"] = 100 * a[m_a].groupby(key)["area_ha"].sum() / out["area_ha"]
        out[f"burned_{name}_pct"] = 100 * a[m_a].groupby(key)["burned_1525_ha"].sum() / out["burned_1525_ha"]
        out[f"modis26_{name}_pct"] = 100 * h[m_h].groupby(key)["n"].sum() / out["modis26"]
    out = out.fillna({c: 0 for c in out.columns if not c.endswith("_pct")})
    out["modis26_per100km2"] = out["modis26"] / out["area_ha"] * 1e4
    return out.round(2).reset_index()


def summary_layers(cfg, d, A, H, years):
    """Polygons for review in a GIS, in <out>/fire_landstatus/layers/summary.gpkg: layers province (village boundaries dissolved by
    province; reused on later runs) and khg, with the attributes of summary_attrs."""
    import geopandas as gpd
    import pyogrio
    s = F.settings(cfg)
    lay = d / "layers"
    lay.mkdir(exist_ok=True)
    out = lay / "summary.gpkg"
    if out.exists() and "province" in pyogrio.list_layers(out)[:, 0]:     # the dissolve is slow: reuse the province outlines
        geo = gpd.read_file(out, layer="province", columns=["province", "island"])
    else:
        v = pyogrio.read_dataframe(Path(cfg["data"]) / s["villages"], columns=["PULAU", "PROV_2023"])
        v["geometry"] = v.geometry.make_valid()
        try:
            pr = v.dissolve("PROV_2023", aggfunc="first", method="coverage")
        except Exception:                   # noqa: BLE001  (coverage union needs a clean coverage; fall back to the plain union)
            pr = v.dissolve("PROV_2023", aggfunc="first")
        geo = pr.reset_index().rename(columns={"PROV_2023": "province", "PULAU": "island"})[["province", "island", "geometry"]]
    prov = geo.merge(summary_attrs(A, H, "province", years), on="province", how="left")
    tmp = lay / "summary.tmp.gpkg"
    if tmp.exists():
        tmp.unlink()
    prov.to_file(tmp, layer="province", driver="GPKG")
    from repeat_prioritisation.national import profile as P
    khg = P.load_khg(cfg)[["khg_id", "nama", "geometry"]]
    kk = summary_attrs(A[A["khg_id"] != ""], H[H["khg_id"] != ""], "khg_id", years)
    khg.merge(kk, on="khg_id", how="left").to_file(tmp, layer="khg", driver="GPKG")
    tmp.replace(out)


def diagnostics(cfg, d, A, H, years, tdir):
    """Data-quality tables: burned-area completeness, DMPG on comparable land, the static-source rule, cross-check with land."""
    # 1 burned hectares per VIIRS detection (all land, full year, medium + high, static left out), national and per province
    v = H[(H["basis"] == "all") & (H["source"] == "viirs") & H["conf"].isin(["medium", "high"]) & ~H["static"]]
    a = A[A["basis"] == "all"]
    rows = []
    for scope, ga, gv in [("Indonesia", a.assign(_p="Indonesia"), v.assign(_p="Indonesia")), ("province", a.assign(_p=a["province"]), v.assign(_p=v["province"]))]:
        vb = gv.groupby(["_p", "year"])["n"].sum()
        for p, g in ga.groupby("_p"):
            for y in years:
                b, n = float(g[f"burned_{y}_ha"].sum()), int(vb.get((p, y), 0))
                rows.append({"scope": scope, "name": p, "year": y, "burned_ha": round(b, 1), "viirs_n": n, "ha_per_detection": round(b / n, 3) if n else None})
    pd.DataFrame(rows).to_csv(tdir / "t_completeness.csv", index=False)
    # 2 DMPG against other peat, only in provinces that hold DMPG village land
    pa = A[A["basis"] == "peat"]
    provs = sorted(pa.loc[pa["dmpg"], "province"].unique())
    ph = H[(H["basis"] == "peat") & H["province"].isin(provs)]
    measures(pa[pa["province"].isin(provs)], ph, ["dmpg", "concession_any"], years,
             sorted(H.loc[H["source"] == "viirs", "year"].unique())).assign(provinces=len(provs)).to_csv(tdir / "t_dmpg_comparable.csv", index=False)
    # 3 static-source rule tested on the typed VIIRS 2026 file, with static points from 2012-2025 only (no circularity)
    s, data = F.settings(cfg), Path(cfg["data"])
    arch, typed = data / s["viirs"][0], data / s["viirs"][1]
    if arch.exists() and typed.exists():
        from pyproj import Transformer
        from scipy.spatial import cKDTree
        import pyogrio
        tf = Transformer.from_crs(4326, s["crs"], always_xy=True)
        st = pyogrio.read_dataframe(arch, columns=["type"], where="type IN (1, 2, 3)")
        tree = cKDTree(np.unique(np.round(np.column_stack(tf.transform(st.geometry.x.to_numpy(), st.geometry.y.to_numpy())) / 50) * 50, axis=0))
        h = pyogrio.read_dataframe(typed, columns=["type", "confidence"])
        h = h[h["confidence"].isin(["n", "h"])]
        dd, _ = tree.query(np.column_stack(tf.transform(h.geometry.x.to_numpy(), h.geometry.y.to_numpy())), distance_upper_bound=s["static_radius_m"]["viirs"])
        flag, true = np.isfinite(dd), h["type"].isin([1, 2, 3]).to_numpy()
        tp, fp, fn = int((flag & true).sum()), int((flag & ~true).sum()), int((~flag & true).sum())
        pd.DataFrame([{"file": s["viirs"][1], "radius_m": s["static_radius_m"]["viirs"], "detections": len(h), "typed_static": int(true.sum()), "flagged": int(flag.sum()),
                       "true_pos": tp, "false_pos": fp, "false_neg": fn, "precision": round(tp / max(1, tp + fp), 3), "recall": round(tp / max(1, tp + fn), 3)}]).to_csv(d / "checks_static.csv", index=False)
    # 4 per-KHG forest-area classes against national.land (100 m grid points)
    lf = Path(cfg["out"]) / "land" / "land_summary.csv"
    if lf.exists():
        land = pd.read_csv(lf)
        land = land[land["layer"] == "forest"].groupby(["khg_id", "class"])["area_km2"].sum().rename("land_km2")
        k = pd.read_parquet(d / "khg.parquet").groupby(["khg_id", "kawasan"])["area_ha"].sum().div(100).rename("fire_km2")
        k.index = k.index.set_names(["khg_id", "class"])
        j = pd.concat([land, k], axis=1).fillna(0.0).reset_index()
        tot = j.groupby("khg_id")[["land_km2", "fire_km2"]].sum().reset_index()
        tot.assign(rel_diff=(tot["fire_km2"] - tot["land_km2"]) / tot["land_km2"]).round(4).to_csv(d / "checks_khg_area.csv", index=False)
        j.assign(diff_km2=j["fire_km2"] - j["land_km2"]).round(3).to_csv(d / "checks_khg_forest.csv", index=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    s = F.settings(cfg)
    d = F.out_dir(cfg)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    years = list(range(s["years"][0], s["years"][1] + 1))
    dist = pd.read_csv(d / "districts.csv", keep_default_na=False)
    kidx = pd.read_csv(d / "khg_index.csv").set_index("idx")["khg_id"]
    cells = burned_measures(classes(pd.read_parquet(d / "cells.parquet"), dist, kidx), years)
    hot = classes(pd.read_parquet(d / "hotspots.parquet"), dist, kidx)
    outside = hot[hot["kab"] == 0].groupby(["source", "file", "year"], as_index=False)["n"].sum()
    outside.to_csv(d / "hotspots_outside_villages.csv", index=False)   # sea and neighbouring countries: not Indonesia's land
    hot = hot[hot["kab"] > 0]
    viirs_years = sorted(hot.loc[hot["source"] == "viirs", "year"].unique().tolist())

    dims_all = ["island", "province", "in_khg", "forest_group", "kawasan", "concession", "lic_bits", "dmpg", "peat"]
    num = ["area_ha"] + [f"burned_{y}_ha" for y in years] + ["burned_any_ha", "burned_2plus_ha"]
    area = cells.groupby(dims_all, as_index=False)[num].sum()
    area.to_parquet(d / "area.parquet", index=False)
    hdims = dims_all + ["source", "year", "month", "conf", "static", "ytd"]
    hot.groupby(hdims, as_index=False)["n"].sum().to_parquet(d / "hot.parquet", index=False)
    kdims = ["khg_id", "forest_group", "kawasan", "concession", "lic_bits", "dmpg", "peat"]
    cells[cells["khg"] > 0].groupby(kdims, as_index=False)[num].sum().to_parquet(d / "khg.parquet", index=False)

    A, H = add_basis(cells), add_basis(hot)
    A["concession_any"] = (A["lic_bits"] & CONC_MASK) > 0
    H["concession_any"] = (H["lic_bits"] & CONC_MASK) > 0
    tdir = d / "tables"
    tdir.mkdir(exist_ok=True)
    tables = {
        "t_national": [],
        "t_scope": ["in_khg"],
        "t_concession_x_forest": ["concession_any", "forest_group"],
        "t_forest_function": ["kawasan", "concession_any"],
        "t_concession_type": ["concession"],
        "t_dmpg": ["dmpg", "concession_any", "forest_group"],
        "t_island": ["island"],
        "t_province": ["island", "province", "concession_any", "forest_group"],
        "t_khg": ["khg_id", "concession_any", "forest_group"],
    }
    out = {}
    for name, dims in tables.items():
        A_ = A.assign(_all="Indonesia") if not dims else A
        H_ = H.assign(_all="Indonesia") if not dims else H
        t = measures(A_, H_, dims or ["_all"], years, viirs_years)
        if name == "t_khg":
            t = t[t["khg_id"] != ""]
        t.to_csv(tdir / f"{name}.csv", index=False)
        out[name] = t
    # times burned in the burn years (KLHK flags; a cell that burned in n different years counts as burned n times)
    A["times_burned"] = sum(((A["burn"].to_numpy() >> n) & 1) for n in range(len(years))).clip(0, 4)
    tb = (A[A["kab"] > 0].groupby(["basis", "concession_any", "forest_group", "dmpg", "times_burned"])["area_ha"].sum()
          .unstack(fill_value=0.0).reindex(columns=range(5), fill_value=0.0))
    tb.columns = ["unburned_ha", "burned_1x_ha", "burned_2x_ha", "burned_3x_ha", "burned_4plus_ha"]
    tb.round(2).reset_index().to_csv(tdir / "t_times_burned.csv", index=False)
    # licence types, non-exclusive: one block per type over the cells that carry that bit
    rows = []
    for name, bit in [("sawit", 1), ("tambang", 2), ("pphtr", 4), ("pbph", 8), ("pphkm", 16)]:
        sa, sh = A[(A["lic_bits"] & bit) > 0].assign(licence=name), H[(H["lic_bits"] & bit) > 0].assign(licence=name)
        rows.append(measures(sa, sh, ["licence", "forest_group"], years, viirs_years))
    pd.concat(rows, ignore_index=True).to_csv(tdir / "t_licence_type.csv", index=False)
    # VIIRS per year by land status (trend), MODIS 2026 per month (headline series)
    hv = H[(H["source"] == "viirs") & ~H["static"]]
    hv.groupby(["basis", "concession_any", "forest_group", "dmpg", "year", "conf", "ytd"], as_index=False)["n"].sum().to_csv(tdir / "t_hotspots_year.csv", index=False)
    hm = H[H["source"] == "modis"]
    hm.groupby(["basis", "concession_any", "forest_group", "dmpg", "month", "conf", "static"], as_index=False)["n"].sum().to_csv(tdir / "t_modis_month.csv", index=False)

    # checks
    chk = []
    nat = out["t_national"].set_index("basis")
    for name, t in out.items():
        if name in ("t_national", "t_khg"):
            continue
        g = t.groupby("basis")[["area_ha", "burned_any_ha", "modis_2026_n"]].sum()
        for b in g.index:
            for c in g.columns:
                chk.append({"check": f"{name} sums to national", "basis": b, "measure": c, "value": float(g.loc[b, c]), "reference": float(nat.loc[b, c]),
                            "diff": float(g.loc[b, c] - nat.loc[b, c])})
    bt = pd.read_csv(d / "checks_burned_tiles.csv")
    for y, g in bt.groupby("year"):
        chk.append({"check": "burned raster against exact polygon area", "basis": "all cells", "measure": f"burned_{y}_ha", "value": float(g["raster_ha"].sum()),
                    "reference": float(g["exact_ha"].sum()), "diff": float(g["raster_ha"].sum() - g["exact_ha"].sum())})
        chk.append({"check": "burned on village land against exact polygon area", "basis": "all", "measure": f"burned_{y}_ha", "value": float(nat.loc["all", f"burned_{y}_ha"]),
                    "reference": float(g["exact_ha"].sum()), "diff": float(nat.loc["all", f"burned_{y}_ha"] - g["exact_ha"].sum())})
    if (d / "checks_hotspots.csv").exists():
        hc = pd.read_csv(d / "checks_hotspots.csv")
        for r in hc.itertuples():
            chk.append({"check": "hotspots in land tiles against the file", "basis": "all", "measure": r.file, "value": float(r.n_tiles), "reference": float(r.n_file),
                        "diff": float(r.n_tiles - r.n_file)})
    pd.DataFrame(chk).round(3).to_csv(d / "checks.csv", index=False)
    diagnostics(cfg, d, A, H, years, tdir)
    summary_layers(cfg, d, A, H, years)
    log.info("tables -> %s (%s)", tdir, meta.get("modis_last"))


if __name__ == "__main__":
    main()
