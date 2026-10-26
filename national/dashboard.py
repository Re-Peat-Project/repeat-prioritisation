#!/usr/bin/env python3
"""Interactive dashboard of the national KHG ranking: one self-contained HTML file.

  python -m national.dashboard --config configs/examples/national_profile.yaml [--top 25] [--out file.html] [--reassemble]

Reads what `python -m national.profile --mode operational` wrote, the Stage 3 tables
(`python -m national.stage3 summarize`) and the input layers named in the config, for the maps of the KHG that get a detailed
profile: the top N by the default weights plus the team's selected KHG. The weights are applied in the browser, with the same
scaling as common.scoring (5th to 95th percentile of the KHG that pass the filters), so moving a slider re-ranks live.
Template, scripts and the English to Indonesian dictionary (i18n_id.js): national/assets/. D3 (ISC) and MapLibre GL JS (BSD) are vendored there. The basemap is OpenFreeMap (Positron style, OpenMapTiles data, OpenStreetMap contributors): it loads from the internet, the rest works offline.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import shapely
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from national import profile as P
from national import overlay as O  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"

# id, column, group, label, unit, default weight, display multiplier
PARAMS = [
    ("f1", "u_fire_freq", "hist", "Burned share", "% of peat per year", 100),
    ("f2", "u_burn_repeat", "hist", "Repeat burns", "% of peat burned 2+ times", 100),
    ("f3", "u_hotspot", "hist", "Hotspots 2015 to 2025", "per km2 of peat per year", 1),
    ("n1", "u_hotspot_now", "now", "Hotspots this year", "per km2 of peat, year to date", 1),
    ("n2", "u_burned_now", "now", "Burned area this year", "% of peat", 100),
    ("c1", "u_canal_primary", "canal", "Primary canals", "km per km2 of KHG", 1),
    ("c2", "u_canal_secondary", "canal", "Secondary canals", "km per km2 of KHG", 1),
    ("c3", "u_canal_tertiary", "canal", "Tertiary canals", "km per km2 of KHG", 1),
]
LC = [("lc_tree", "Tree"), ("lc_shrub", "Shrub"), ("lc_grass", "Grass"), ("lc_crop", "Crop"), ("lc_built", "Built"),
      ("lc_water", "Water"), ("lc_wetland", "Wetland"), ("lc_mangrove", "Mangrove"), ("lc_other", "Other")]


def r4(x):
    return round(float(x), 4)


def rings(geom, tol):
    g = geom.simplify(tol, preserve_topology=True) if tol else geom
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    out = []
    for p in polys:
        if p.is_empty:
            continue
        out.append([[[r4(x), r4(y)] for x, y in ring.coords] for ring in [p.exterior, *p.interiors]])
    return out


def flat_lines(geoms, tol, cap):
    lines = []
    for g in geoms:
        if g is None or g.is_empty:
            continue
        g = g.simplify(tol, preserve_topology=False)
        for ln in (g.geoms if g.geom_type.startswith("Multi") else [g]):
            if ln.geom_type == "LineString" and len(ln.coords) >= 2:
                lines.append(ln)
    lines.sort(key=lambda ln: -ln.length)
    return [[r4(v) for xy in ln.coords for v in xy[:2]] for ln in lines[:cap]]


def profile_layers(cfg, row, years):
    """Map layers of one KHG: outline, burn counts, canals by class, this year's hotspot points."""
    data, inp = Path(cfg["data"]), cfg["inputs"]
    g = shapely.make_valid(row.geom)
    tol = 0.0003 + 0.00002 * np.sqrt(row.area_km2)
    out = {"bounds": [r4(v) for v in g.bounds], "outline": rings(g, tol)}
    ycols = [f"BA_{y}" for y in range(2015, 2027)]
    b = P._read_mask(data / inp["burned"], g, columns=ycols)
    burn = []
    if len(b):
        win = [c for c in ycols if years[0] <= int(c[3:]) <= years[1]]
        n = b[win].notna().sum(axis=1).to_numpy()
        geom = shapely.intersection(shapely.make_valid(b.geometry.values), g)
        for k in (1, 2, 3, 4):
            sel = (n == k) if k < 4 else (n >= 4)
            if sel.any():
                u = shapely.union_all(geom[sel])
                if not u.is_empty:
                    burn.append({"n": k, "r": rings(u, tol)})
    out["burn"] = burn
    pg = O.peat_shape(cfg, g, tol * 1.5)
    out["peat"] = rings(pg, 0) if pg is not None else []
    c = P._read_mask(data / inp["canals"], g, columns=["KODE_KANAL"])
    canals = {"p": [], "s": [], "t": []}
    if len(c):
        geo = shapely.intersection(shapely.make_valid(c.geometry.values), g)
        code = c["KODE_KANAL"].astype(str).to_numpy()
        for k, key, cap in (("1", "p", 6000), ("2", "s", 8000), ("3", "t", 9000)):
            canals[key] = flat_lines(geo[code == k], tol / 2, cap)
    out["canals"] = canals
    pts = []
    if inp.get("hotspots_now") and (data / inp["hotspots_now"]).exists():
        h2 = P._read_mask(data / inp["hotspots_now"], g, columns=["layer", "C_LEVEL", "Kepercayaa"])
        if len(h2):
            lvl = h2["C_LEVEL"].fillna(h2["Kepercayaa"]).astype("string").str.lower().map(P.LEVEL)
            keep = lvl.isin(cfg["now"]["levels"]).to_numpy()
            h2, lvl = h2[keep], lvl[keep]
            xs, ys = h2.geometry.x.to_numpy(), h2.geometry.y.to_numpy()
            inside = shapely.contains_xy(g, xs, ys)
            xs, ys, lvl, h2 = xs[inside], ys[inside], lvl[inside], h2[inside]
            pe = cfg.get("peat", {}).get("extent")
            ps = P.PeatSampler(pe) if pe and Path(pe).exists() else None
            onp = (ps.sample(ps.window(g), xs, ys) == 1) if ps is not None else np.ones(len(xs), bool)
            mon = h2["layer"].str[:2].astype(int).to_numpy()
            hi = (lvl == "high").to_numpy()
            order = np.argsort(-hi.astype(int), kind="stable")[:9000]
            pts = [[r4(xs[k]), r4(ys[k]), int(mon[k]), int(hi[k]), int(onp[k])] for k in order]
            out["now_total"] = int(len(xs))
    out["now"] = pts
    return out


def build(cfg, top_n, out_path):
    base = Path(cfg["out"])
    prof = pd.read_csv(base / "operational" / "profile.csv", dtype={"khg_id": str})
    yearly = pd.read_csv(base / "operational" / "yearly.csv", dtype={"khg_id": str})
    rep = json.loads((base / "operational" / "report.json").read_text(encoding="utf-8"))
    vrep = json.loads((base / "validate" / "report.json").read_text(encoding="utf-8")) if (base / "validate" / "report.json").exists() else None
    s3dir = base / "stage3"
    s3 = pd.read_csv(s3dir / "stage3_profile.csv", dtype={"khg_id": str}) if (s3dir / "stage3_profile.csv").exists() else pd.DataFrame(columns=["khg_id"])
    s3y = pd.read_csv(s3dir / "stage3_yearly.csv", dtype={"khg_id": str}) if (s3dir / "stage3_yearly.csv").exists() else pd.DataFrame(columns=["khg_id", "year", "metric", "value"])
    prof = prof.merge(s3.drop(columns=[c for c in s3.columns if c in prof.columns and c != "khg_id"]), on="khg_id", how="left")
    nb = [cfg["years"]["baseline"][0], cfg["years"]["validation"][1]]
    nowrep = rep.get("now") or {}

    # which KHG are the team's
    team = {}
    sel_path = Path(P.os.environ.get("REPEAT_HUB", ROOT.parent / "re-peat")) / "sites" / "selected_khg.csv"
    if sel_path.exists():
        names = {P.norm_name(n): (role, given) for n, role, given in
                 pd.read_csv(sel_path).fillna("")[["khg_name_in_gpkg", "role", "name_as_given"]].itertuples(index=False) if n}
        for r in prof.itertuples():
            k = P.norm_name(r.nama)
            if k in names:
                team[r.khg_id] = names[k][0]

    # geometry of all KHG
    khg = P.load_khg(cfg)[["khg_id", "geometry"]].set_index("khg_id")
    prof = prof.reset_index(drop=True)
    order = prof.khg_id.tolist()
    geo = [rings(shapely.make_valid(khg.loc[k, "geometry"]), 0.012) for k in order]

    ranked = prof[prof.skor_risiko.notna()].sort_values("peringkat")
    prof_ids = list(dict.fromkeys(list(ranked.khg_id.head(top_n)) + list(team)))
    conf = prof.confidence.map({"tinggi": 2, "sedang": 1, "rendah": 0}).fillna(0).astype(int)

    cols = {
        "id": order, "name": prof.nama.str.replace(r"^KHG\s+", "", regex=True).str.replace(r"\s+", " ", regex=True).tolist(),
        "prov": prof.province.fillna("").astype(str).tolist(), "island": prof.island.fillna("").str.replace("PULAU ", "", regex=False).str.title().tolist(),
        "area": [round(float(x), 1) for x in prof.area_km2], "peat": [None if pd.isna(x) else round(float(x), 1) for x in prof.peat_km2],
        "conf": conf.tolist(), "team": [team.get(k, "") for k in order],
        "ref_rank": [None if pd.isna(x) else int(x) for x in prof.peringkat],
        "has": [int(k in prof_ids) for k in order],
        **({"n1h": [0.0 if pd.isna(u) or pd.isna(sh) else round(float(u) * float(sh), 4) for u, sh in zip(prof.u_hotspot_now, prof.hs_now_high_share)],
            "n1hn": [0 if pd.isna(k) or pd.isna(sh) else int(round(float(k) * float(sh))) for k, sh in zip(prof.hs_now_kept, prof.hs_now_high_share)]}
           if "hs_now_high_share" in prof and "u_hotspot_now" in prof else {}),
        "v": [[None if pd.isna(x) else round(float(x) * m, 4) for x in prof[c]] for _, c, _, _, _, m in PARAMS],
    }

    # detailed profiles
    profiles = {}
    for k in prof_ids:
        row = prof[prof.khg_id == k].iloc[0].copy()
        row["geom"] = khg.loc[k, "geometry"]
        yr = yearly[yearly.khg_id == k]
        den = float(row.peat_km2) if pd.notna(row.get("peat_km2")) else float(row.area_km2)
        burned = yr[yr.metric == "burned_peat_km2"].set_index("year").value.to_dict()
        hs = yr[yr.metric == "n_hotspot_peat"].set_index("year").value.to_dict()
        now_m = [[m, int(yr[yr.metric == f"hs_now_peat_m{m:02d}"].value.sum()), int(yr[yr.metric == f"hs_now_all_m{m:02d}"].value.sum())]
                 for m in nowrep.get("months", [])]
        ser = lambda metric, nd=0: [[int(y), round(float(v), nd)] for y, v in zip(*[s3y[(s3y.khg_id == k) & (s3y.metric == metric)].sort_values("year")[c] for c in ("year", "value")])]
        lay = profile_layers(cfg, type("R", (), {"geom": row["geom"], "area_km2": row.area_km2})(), nb)
        lc = [[lab, round(100 * float(row[c]), 1)] for c, lab in LC if c in row and pd.notna(row[c]) and float(row[c]) > 0.0005]
        profiles[k] = {
            "lay": lay, "burned": [[y, round(100 * burned.get(y, 0) / den, 3)] for y in range(2015, 2027)],
            "hs": [[y, int(hs.get(y, 0))] for y in range(2012, 2026)], "now_m": now_m,
            "deficit": ser("deficit_mm"), "rain": ser("rain_dry_season_mm"), "lc": lc,
            "info": {
                "kab": str(row.get("kabupaten", "")), "code": k, "peat_gfw": None if pd.isna(row.get("peat_frac")) else round(float(row.peat_frac), 3),
                "peat_gpm": None if pd.isna(row.get("peat_frac_gpm1km")) else round(float(row.peat_frac_gpm1km), 3),
                "hs_now": None if pd.isna(row.get("hs_now_kept")) else int(row.hs_now_kept), "hs_now_high": None if pd.isna(row.get("hs_now_high_share")) else round(float(row.hs_now_high_share), 2),
                "rank_now": None if pd.isna(row.get("peringkat_now")) else int(row.peringkat_now), "rank_now_n": None if pd.isna(row.get("peringkat_now_n")) else int(row.peringkat_now_n),
                "tma_n": 0 if pd.isna(row.get("n_tma_stations")) else int(row.n_tma_stations), "tma_deep": None if pd.isna(row.get("tma_deep_share")) else round(float(row.tma_deep_share), 2),
                "infra": int(row.get("n_infra_ada", 0) or 0), "desa": int(row.get("n_desa_target", 0) or 0),
                "dmpg": int(row.get("n_dmpg", 0) or 0),
            },
        }

    ov_dir = base / "stage3" / "overlay"
    has_ov = (ov_dir / "overlay_summary.csv").exists() and (ov_dir / "overlay_map.json").exists()
    if has_ov:
        ovs = pd.read_csv(ov_dir / "overlay_summary.csv", dtype={"khg_id": str})
        ova = pd.read_csv(ov_dir / "overlay_actors_top.csv", dtype={"khg_id": str}) if (ov_dir / "overlay_actors_top.csv").exists() else pd.DataFrame(columns=["khg_id"])
        ovm = json.loads((ov_dir / "overlay_map.json").read_text(encoding="utf-8"))
        rd = lambda v, nd=2: None if pd.isna(v) else round(float(v), nd)
        for k, pr in profiles.items():
            if k not in ovm:
                continue
            m = dict(ovm[k])
            cell = m.pop("cell_m", None)
            pr["lay"]["ov"] = m
            sub = ovs[ovs.khg_id == k]
            summ = {}
            for layer, g_ in sub.groupby("layer"):
                summ[layer] = [[r["class"], rd(r.area_km2), rd(r.peat_km2), rd(r.burned_peat_km2), int(r.hs_now_peat)]
                               + ([rd(r.lindung_km2), rd(r.forest_protected_km2)] if layer.startswith("licence_") else [])
                               for _, r in g_.iterrows()]
            act = [[r.company, r.type, rd(r.area_km2), rd(r.burned_peat_km2), int(r.hs_now_peat), rd(r.lindung_km2)]
                   for r in ova[ova.khg_id == k].itertuples()]
            pr["ov"] = {"cell": cell, "s": summ, "a": act}

    validation = None
    if vrep:
        v = vrep["validation"]
        validation = {k: {"auc": round(b["skor_risiko"]["auc"], 3), "auc_hist": round(b["hanya_riwayat_kebakaran"]["auc"], 3)} for k, b in v.items()}
    gpm_by_island = {}
    for isl, g_ in prof.dropna(subset=["peat_frac", "peat_frac_gpm1km"]).groupby("island"):
        gpm_by_island[isl.replace("PULAU ", "").title()] = [round(float(g_.peat_frac.median()), 2), round(float(g_.peat_frac_gpm1km.median()), 2), len(g_)]
    meta = {
        "generated": date.today().isoformat(), "period_now": nowrep.get("last_date"), "baseline": f"{nb[0]} to {nb[1]}",
        "n_khg": len(prof), "min_area": cfg["min_area_km2"], "min_peat": cfg["peat"]["min_peat_km2"],
        "weights": {pid: float(rep["weights"].get(col, 0.0)) for pid, col, *_ in PARAMS}, "validation": validation, "peat_by_island": gpm_by_island,
        "top_n": top_n, "overlay": has_ov,
    }
    params = [{"id": pid, "group": grp, "label": lab, "unit": unit} for pid, _, grp, lab, unit, _ in PARAMS]
    return {"meta": meta, "params": params, "khg": cols, "geo": geo}, profiles


def assemble(data, profiles, out_path):
    tpl = (ASSETS / "dashboard.html").read_text(encoding="utf-8")
    safe = lambda obj: json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")   # only the payload: "</script>" in it would end the tag
    prof_tags = "\n".join(f'<script type="application/json" id="prof-{k}">{safe(v)}</script>' for k, v in profiles.items())
    data = {**data, "style": json.loads((ASSETS / "basemap-positron.json").read_text(encoding="utf-8"))}   # OpenFreeMap Positron style
    html = (tpl.replace("/*D3*/", (ASSETS / "d3.v7.9.0.min.js").read_text(encoding="utf-8"))
            .replace("/*ML*/", (ASSETS / "maplibre-gl.v5.24.0.js").read_text(encoding="utf-8"))
            .replace("/*MLCSS*/", (ASSETS / "maplibre-gl.v5.24.0.css").read_text(encoding="utf-8"))
            .replace("/*CSS*/", (ASSETS / "dashboard.css").read_text(encoding="utf-8"))
            .replace("/*JS*/", (ASSETS / "dashboard.js").read_text(encoding="utf-8").replace("/*I18N*/", (ASSETS / "i18n_id.js").read_text(encoding="utf-8")))
            .replace("/*DATA*/", "const DATA=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";")
            .replace("<!--PROFILES-->", prof_tags))
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"{out_path}: {len(html) / 1e6:.1f} MB, {len(data['khg']['id'])} KHG, {len(profiles)} profiles")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--out")
    ap.add_argument("--reassemble", action="store_true", help="reuse the data of the last build (dashboard_data.json) and only rebuild the page")
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    out = a.out or str(Path(cfg["out"]) / "dashboard.html")
    cache = Path(cfg["out"]) / "dashboard_data.json"
    if a.reassemble and cache.exists():     # only the template, styles and script changed: skip the slow map layers
        blob = json.loads(cache.read_text(encoding="utf-8"))
        data, profiles = blob["data"], blob["profiles"]
    else:
        data, profiles = build(cfg, a.top, out)
        cache.write_text(json.dumps({"data": data, "profiles": profiles}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    assemble(data, profiles, out)


if __name__ == "__main__":
    main()
