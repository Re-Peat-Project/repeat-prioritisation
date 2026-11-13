"""The national dashboard's second page: burned area and hotspots by land status (concession, forest area, DMPG, peat).

    repeat-national-fire-page --config configs/examples/national_profile.yaml [--out PATH]

Reads the tallies of `repeat-national-fire-tables` (<out>/fire_landstatus/area.parquet, hot.parquet, meta.json) and writes
<out>/fire.html next to dashboard.html; each page links to the other. `repeat-national-dashboard` also writes it.
Everything is embedded (d3, styles, data), so the page opens from disk. Low-confidence hotspots are left out.
Data: one table of land-status classes (island, province, in KHG, forest group, forest function, concession type, licence
bits, DMPG, peat); area rows give area and burned area per year per class; hotspot rows give counts per class, sensor, year,
month, confidence, static flag and year-to-date flag.
"""
import argparse
import copy
import json
from pathlib import Path

import pandas as pd
import yaml

from repeat_prioritisation.national import profile as P

ASSETS = Path(__file__).parent / "assets"
DIMS = ["island", "province", "in_khg", "forest_group", "kawasan", "concession", "lic_bits", "dmpg", "peat"]


def dmpg_reference(area, hot, years):
    """VIIRS hotspots per 100 km2 of KLH peat in DMPG villages and on other peat, in the provinces that hold DMPG village peat, per
    year over the same window (medium and high confidence, static left out): the series the page draws at default filters."""
    pa = area[area["peat"] == 1]
    prov = sorted(pa.loc[pa["dmpg"], "province"].unique())
    pa = pa[pa["province"].isin(prov)]
    ar = pa.groupby("dmpg")["area_ha"].sum()
    h = hot[(hot["source"] == "viirs") & hot["ytd"] & ~hot["static"] & (hot["peat"] == 1) & hot["province"].isin(prov) & hot["year"].between(years[0], years[1])]
    n = h.groupby(["year", "dmpg"])["n"].sum().unstack(fill_value=0)
    return {"provinces": prov, "rates": {int(y): [round(float(r.get(True, 0) / ar[True] * 1e4), 3), round(float(r.get(False, 0) / ar[False] * 1e4), 3)] for y, r in n.iterrows()}}


def first_dmpg_year(cfg):
    """Earliest year in the DMPG layer's scheme field (Skema_DPG, e.g. '2018 Kemitraan')."""
    if not cfg or not (cfg.get("inputs") or {}).get("dmpg"):
        return None
    import pyogrio
    p = Path(cfg["data"]) / cfg["inputs"]["dmpg"]
    if not p.exists():
        return None
    sk = pyogrio.read_dataframe(p, layer="dmpg_villages", columns=["Skema_DPG"], read_geometry=False)["Skema_DPG"].astype(str)
    y = pd.to_numeric(sk.str.extract(r"((?:19|20)\d{2})")[0], errors="coerce")
    return int(y.min()) if y.notna().any() else None


def payload(src, cfg=None):
    area = pd.read_parquet(src / "area.parquet")
    hot = pd.read_parquet(src / "hot.parquet")
    hot = hot[hot["conf"].isin(["medium", "high"])]
    hot = hot.groupby(DIMS + ["source", "year", "month", "conf", "static", "ytd"], as_index=False)["n"].sum()
    meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    years = list(range(meta["years"][0], meta["years"][1] + 1))
    keys = pd.concat([area[DIMS], hot[DIMS]]).drop_duplicates().reset_index(drop=True)
    keys["k"] = range(len(keys))
    a = area.merge(keys, on=DIMS)
    h = hot.merge(keys, on=DIMS)
    cls = {c: (keys[c].astype(int).tolist() if keys[c].dtype == bool or c in ("lic_bits", "peat") else keys[c].astype(str).tolist()) for c in DIMS}
    ref = dmpg_reference(area, hot, meta["years"])
    return {
        "meta": {**{k: meta[k] for k in ("cell_m", "years", "viirs_last", "modis_last", "static_radius_m")},
                 "dmpg_first_year": first_dmpg_year(cfg), "dmpg_reference": ref},
        "cls": cls,
        "area": {"k": a["k"].tolist(), "ha": a["area_ha"].round(1).tolist(), "ever": a["burned_any_ha"].round(1).tolist(),
                 "twice": a["burned_2plus_ha"].round(1).tolist(), "x2": a["burned_2x_ha"].round(1).tolist(), "x3": a["burned_3x_ha"].round(1).tolist(), "x4": a["burned_4plus_ha"].round(1).tolist(), "burned": [a[f"burned_{y}_ha"].round(1).tolist() for y in years]},
        "hot": {"k": h["k"].tolist(), "s": (h["source"] == "viirs").astype(int).tolist(), "y": h["year"].astype(int).tolist(),
                "m": h["month"].fillna(0).astype(int).tolist(), "hi": (h["conf"] == "high").astype(int).tolist(),
                "st": h["static"].astype(int).tolist(), "ytd": h["ytd"].astype(int).tolist(), "n": h["n"].astype(int).tolist()},
    }


def assemble(data, out_path):
    tpl = (ASSETS / "fire.html").read_text(encoding="utf-8")
    js = (ASSETS / "fire.js").read_text(encoding="utf-8").replace("/*I18N*/", (ASSETS / "i18n_id.js").read_text(encoding="utf-8"))
    html = (tpl.replace("/*D3*/", (ASSETS / "d3.v7.9.0.min.js").read_text(encoding="utf-8"))
            .replace("/*CSS*/", (ASSETS / "dashboard.css").read_text(encoding="utf-8"))
            .replace("/*JS*/", js)
            .replace("/*DATA*/", "const DATA=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";"))
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"{out_path}: {len(html) / 1e6:.1f} MB, {len(data['area']['k'])} area rows, {len(data['hot']['k'])} hotspot rows")


def build(cfg, out=None):
    src = Path(cfg["out"]) / "fire_landstatus"
    if not (src / "area.parquet").exists():
        print(f"{src}: no fire tallies (run repeat-national-fire and repeat-national-fire-tables); fire.html not written")
        return None
    out = Path(out or Path(cfg["out"]) / "fire.html")
    assemble(payload(src, cfg), out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    build(P._expand(cfg), a.out)


if __name__ == "__main__":
    main()
