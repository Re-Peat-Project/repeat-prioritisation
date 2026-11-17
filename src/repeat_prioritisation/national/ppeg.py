"""KLH's integrated thematic analysis for peat ecosystem restoration (PPEG, April 2026): per-KHG summary and dissolved layers.

    repeat-national-ppeg [--gpkg PATH] [--villages PATH] [--out DIR]            per-KHG table (attributes only, seconds)
    repeat-national-ppeg --layers [--chunk N] [--peat-out PATH]                 also the dissolved layers (one pass, minutes)
    repeat-national-ppeg --peat-raster configs/examples/national_profile.yaml   the peat extent on the fire tally's 30 m grid

The KLH file (ALL_Analysis_Integrasi_Tematik__PPEG_Indonesia__April_2026.gpkg in $REPEAT_DATA) is the overlay KLH built its
restoration targets on and the canonical source for them. It is read as delivered; areas are its LUAS_HA (hectares).

Priority KHG (decided 2026-11-13): a KHG is a priority KHG when it
  (a) lies in one of the 2,004 Bluebook target villages (desa_target_pemulihan_ekosistem_gambut.gpkg, matched on province,
      district, subdistrict and village name; these are the 345 "target 2026" KHG of the team database), or
  (b) holds SKEG 2024 damaged peat (any class, light to very heavy, on LAHAN_GAMB peat).
Both reasons are kept per KHG (in_target_villages, has_skeg_damage). The priority area is the SKEG-damaged peat: 3.31 million ha,
the "about 3.3 million ha" of the FGD terms of reference (KLH, B.70/E/PKL.4.5/10/2026); KHG added by (a) alone hold none of it.
The TOR counts 337 KHG; neither rule gives that number, so the list is a reconstruction.

Writes to DIR (default $REPEAT_WORK/national_profile/ppeg):
  ppeg_khg.csv       one row per KHG name in the file (plus NON KHG), with the registry code where the name matches
  ppeg_national.csv  the same columns summed over Indonesia
  ppeg_layers.gpkg   (--layers) dissolved per KHG and class, with LUAS_HA summed: skeg, priority_area (damaged peat by actor,
                     intervention class and dome), actor, landform, peat_thickness (PEAT_THICK), peat_depth_bbsdlp (KDLMN_GBT)
and (--layers) the peat extent, LAHAN_GAMB = LAHAN GAMBUT dissolved per KHG, to --peat-out
(default $REPEAT_DATA/peat/ppeg_lahan_gambut_2026.gpkg), the project's peat basis.
Blank codes ('' or ' ') and NON KHG in a class field are written as "no data", never as "not peat" or "not damaged".
"""
import argparse
import os
import re
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

NAME = "ALL_Analysis_Integrasi_Tematik__PPEG_Indonesia__April_2026.gpkg"
VILLAGES = "desa_target_pemulihan_ekosistem_gambut.gpkg"
VKEY = ["PROV_2023", "KABKO_2023", "KEC_2023", "DESA_2023"]
COLS = ["NAMA_KHG", "PULAU", "PROV_2023", "CD_KHG", "LAHAN_GAMB", "SKEG_2024", "CD_SKEG_24", "CD_BURN", "BURN_PERIOD", "CD_ATK",
        "CD_KONSESI", "CD_KAWASAN", "FEG_250K", "LANDFORM", "PROG_DMPG_2025", "PROG_INTERVENSI", "PEAT_THICK", "KDLMN_GBT", "LUAS_HA"] + VKEY[1:]
ACTOR = {"Intervensi Perusahaan": "company", "Kolaborasi Perusahaan (Area Buffer)": "company_buffer",
         "Intervensi Kementerian Kehutanan": "mofor", "Intervensi KLH/BPLH": "klh"}
DOME = {"kubah gambut", "kubah gambut (bagian tengah)", "tepi kubah gambut"}      # ombrogenous (dome) landforms; the rest of peat is topogenous, fluvial or marine
NODATA = "no data"


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def clean(s):
    """Class labels with blanks and NON KHG as 'no data'."""
    s = s.astype(str).str.strip()
    return s.where((s != "") & (s != "NON KHG"), NODATA)


def thick_bounds(label):
    """'0,5 - 1,0 meter', '0.5 - 1.0 meter', '100 - <200 cm', '>= 700 cm' -> (low m, high m); no data -> (nan, nan)."""
    s = str(label).strip().replace(",", ".")
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    if not nums:
        return np.nan, np.nan
    k = 0.01 if "cm" in s else 1.0
    return nums[0] * k, (nums[1] * k if len(nums) > 1 else np.inf)


def thick_label(label):
    lo, hi = thick_bounds(label)
    if np.isnan(lo):
        return NODATA
    return f">= {lo:g} m" if np.isinf(hi) else f"{lo:g}-{hi:g} m"


def village_keys(path):
    v = pyogrio.read_dataframe(path, read_geometry=False, columns=VKEY)
    return set(vkey(v))


def vkey(d):
    s = d[VKEY[0]].astype(str).str.strip()
    for c in VKEY[1:]:
        s = s + "|" + d[c].astype(str).str.strip()
    return s


def derive(df, targets):
    """Columns shared by the table and the layers."""
    out = pd.DataFrame(index=df.index)
    out["khg"] = df["NAMA_KHG"].map(lambda s: re.sub(r"\s+", " ", str(s)).strip())
    out["peat"] = df["LAHAN_GAMB"] == "LAHAN GAMBUT"
    out["damaged"] = df["CD_SKEG_24"].str.startswith("Rusak")
    out["skeg"] = clean(df["SKEG_2024"]).where(df["CD_SKEG_24"] != "NON KHG", NODATA)
    out["target_village"] = vkey(df).isin(targets)
    lf = df["LANDFORM"].map(norm).replace({"deresi aluvial": "depresi aluvial", "dataran fluviomarin": "dataran fluvio-marin"})
    out["landform"] = lf.where(lf != "", NODATA)
    out["dome"] = lf.isin(DOME)
    out["actor"] = df["PROG_DMPG_2025"].map(ACTOR).fillna(NODATA)
    out["intervention"] = clean(df["PROG_INTERVENSI"])
    out["peat_thick"] = df["PEAT_THICK"].map(thick_label)
    out["depth_bbsdlp"] = df["KDLMN_GBT"].map(thick_label)
    return out


def load(path, targets, whole_khg=None):
    """Per-polygon areas. whole_khg: KHG names (normalised as derive() does) whose whole area counts as peat, for the KHG of
    KLH's 337 that hold no peat in KLH's map (final prioritisation amendment 2026-11-17)."""
    try:
        import pyarrow  # noqa: F401
        arrow = True
    except ImportError:
        arrow = False
    df = pyogrio.read_dataframe(path, read_geometry=False, use_arrow=arrow, columns=COLS)
    d = derive(df, targets)
    if whole_khg:
        d["peat"] = d["peat"] | d["khg"].isin(set(whole_khg))
    peat, dmg, ha = d["peat"], d["damaged"], df["LUAS_HA"]
    f = pd.DataFrame({"khg": d["khg"], "area_ha": ha, "peat_ha": ha * peat})
    f["target_village_ha"] = ha * d["target_village"]
    f["priority_ha"] = ha * (peat & dmg)
    f["priority_in_target_villages_ha"] = ha * (peat & dmg & d["target_village"])
    for k in ["Rusak Ringan", "Rusak Sedang", "Rusak Berat", "Rusak Sangat Berat"]:
        f[f"priority_{k.split(' ', 1)[1].lower().replace(' ', '_')}_ha"] = ha * (peat & (df["SKEG_2024"] == k))
    f["peat_dome_ha"] = ha * (peat & d["dome"])
    f["peat_landform_blank_ha"] = ha * (peat & (d["landform"] == NODATA))
    f["priority_dome_ha"] = ha * (peat & dmg & d["dome"])
    lo = df["PEAT_THICK"].map(lambda s: thick_bounds(s)[0])
    f["peat_thick3m_ha"] = ha * (peat & (lo >= 3))
    f["priority_thick3m_ha"] = ha * (peat & dmg & (lo >= 3))
    f["peat_burned_ha"] = ha * (peat & (df["CD_BURN"] == "Areal Terbakar"))
    f["peat_burned_2plus_ha"] = ha * (peat & df["BURN_PERIOD"].isin(["Terbakar 2x", "Terbakar 3x", "Terbakar >3x"]))
    f["peat_canal_ha"] = ha * (peat & (df["CD_ATK"] == "Area Terdampak Kanal"))
    f["peat_protected_feg_ha"] = ha * (peat & df["FEG_250K"].str.contains("Lindung"))
    for v in ACTOR.values():
        f[f"priority_{v}_ha"] = ha * (peat & dmg & (d["actor"] == v))
    for k in ["01", "02", "03"]:
        f[f"priority_class{k}_ha"] = ha * (peat & dmg & df["PROG_INTERVENSI"].str.startswith(k))
    f["priority_forest_area_ha"] = ha * (peat & dmg & (df["CD_KAWASAN"] == "Kawasan Hutan"))
    side = df.assign(khg=d["khg"]).groupby("khg").agg(island=("PULAU", lambda s: ", ".join(sorted(s.unique()))),
                                                      provinces=("PROV_2023", lambda s: ", ".join(sorted(s.unique()))))
    return f, side


def summarise(f, side, registry):
    t = side.join(f.groupby("khg").sum())
    reg = pd.read_csv(registry)
    code = dict(zip(reg["name"].map(norm), reg["khg_code"]))
    t.insert(0, "khg_code", [code.get(norm(k), "") for k in t.index])
    named = t.index != "NON KHG"
    t["in_target_villages"] = named & (t["target_village_ha"] > 0)
    t["has_skeg_damage"] = named & (t["priority_ha"] > 0)
    t["priority"] = t["in_target_villages"] | t["has_skeg_damage"]
    t["priority_rank"] = t["priority_ha"].where(t["has_skeg_damage"]).rank(ascending=False, method="min")
    t["dome_share_of_priority"] = t["priority_dome_ha"] / t["priority_ha"].where(t["priority_ha"] > 0)
    return t.sort_values(["priority_ha", "target_village_ha"], ascending=False).rename_axis("khg_name").reset_index()


# --- dissolved layers -------------------------------------------------------------------------------------------------
LAYERS = {   # name: (keys, row filter on the derived frame)
    "skeg": (["khg", "skeg", "peat"], None),
    "priority_area": (["khg", "skeg", "actor", "intervention", "dome", "target_village"], lambda d: d["peat"] & d["damaged"]),
    "actor": (["khg", "actor", "peat"], None),
    "landform": (["khg", "landform", "dome"], lambda d: d["peat"]),
    "peat_thickness": (["khg", "peat_thick"], None),
    "peat_depth_bbsdlp": (["khg", "depth_bbsdlp"], None),
    "peat_extent": (["khg"], lambda d: d["peat"]),
}


def union(geoms):
    geoms = shapely.make_valid(np.asarray(geoms))
    geoms = shapely.get_parts(geoms)
    geoms = geoms[shapely.get_type_id(geoms) >= 3]          # polygons only (make_valid can return lines)
    try:
        u = shapely.coverage_union_all(geoms)
        if shapely.is_valid(u):
            return u
    except shapely.errors.GEOSException:
        pass
    return shapely.union_all(geoms)


def layers(path, targets, out_gpkg, peat_out, chunk):
    n = pyogrio.read_info(path)["features"]
    parts = {k: [] for k in LAYERS}
    t0 = time.time()
    for start in range(0, n, chunk):
        df = pyogrio.read_dataframe(path, columns=COLS, skip_features=start, max_features=chunk, use_arrow=True)
        d = derive(df, targets)
        d["LUAS_HA"] = df["LUAS_HA"].values
        d["geometry"] = df.geometry.values
        for name, (keys, sel) in LAYERS.items():
            dd = d if sel is None else d[sel(d)]
            for k, g in dd.groupby(keys, sort=False):
                parts[name].append((k if isinstance(k, tuple) else (k,), g["LUAS_HA"].sum(), union(g["geometry"].values)))
        print(f"  features {start:,}-{min(start + chunk, n):,} of {n:,}: {time.time() - t0:.0f} s", flush=True)
    written = {}
    for name, (keys, _) in LAYERS.items():
        p = pd.DataFrame([(*k, a, g) for k, a, g in parts[name]], columns=keys + ["LUAS_HA", "geometry"])
        p = p.groupby(keys, sort=True).agg(LUAS_HA=("LUAS_HA", "sum"), geometry=("geometry", lambda s: union(s.values))).reset_index()
        g = gpd.GeoDataFrame(p, geometry="geometry", crs="EPSG:4326")
        g["geometry"] = shapely.force_2d(g.geometry.values)
        target = peat_out if name == "peat_extent" else out_gpkg
        target.parent.mkdir(parents=True, exist_ok=True)
        lyr = "lahan_gambut" if name == "peat_extent" else name
        g.to_file(target, layer=lyr, driver="GPKG", promote_to_multi=True)
        written[name] = (target, len(g), g["LUAS_HA"].sum())
        print(f"  {name}: {len(g):,} features, {g['LUAS_HA'].sum() / 1e6:.3f} million ha -> {target}", flush=True)
    return written


def peat_raster(cfg_path, peat_gpkg, out_tif):
    """KLH peat (the dissolved PPEG extent) burned onto the 30 m equal-area grid of repeat-national-fire (same CRS, cell and
    origin), so the fire tally reads it cell for cell and the profile samples it per KHG. 1 = peat, 0 = not peat; a cell is
    peat when its centre is. The vector stays the native copy."""
    import rasterio
    from rasterio.features import rasterize
    from rasterio.windows import Window
    from repeat_prioritisation.national import fire_landstatus as FL
    from repeat_prioritisation.national import land as L
    cfg = L.load_cfg(cfg_path)
    s = FL.settings(cfg)
    tl, origin = FL.tiles(cfg)
    c, t = s["cell_m"], s["tile_cells"]
    nx, ny = max(i for i, _ in tl) + 1, max(j for _, j in tl) + 1
    g = gpd.read_file(peat_gpkg, layer="lahan_gambut").to_crs(s["crs"])
    geoms = shapely.make_valid(g.geometry.values)
    tree = shapely.STRtree(geoms)
    prof = dict(driver="GTiff", width=nx * t, height=ny * t, count=1, dtype="uint8", crs=s["crs"], nodata=255,
                transform=rasterio.transform.from_origin(origin[0], origin[1], c, c), tiled=True, blockxsize=512, blockysize=512,
                compress="deflate", predictor=1, BIGTIFF="YES")
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    t0, peat_cells = time.time(), 0
    with rasterio.open(out_tif, "w", **prof) as dst:
        for k, (i, j) in enumerate((i, j) for j in range(ny) for i in range(nx)):
            tr, box = FL.tile_geo(origin, i, j, c, t)
            idx = tree.query(shapely.box(*box))
            arr = (rasterize(((geoms[q], 1) for q in idx), out_shape=(t, t), transform=tr, fill=0, dtype="uint8")
                   if len(idx) else np.zeros((t, t), "uint8"))
            peat_cells += int(arr.sum())
            dst.write(arr, 1, window=Window(i * t, j * t, t, t))
            if k % 100 == 0:
                print(f"  tile {k:,} of {nx * ny:,}: {time.time() - t0:.0f} s", flush=True)
        dst.update_tags(source=str(peat_gpkg), values="1 peat, 0 not peat", method="cell centre in a KLH peat polygon")
    print(f"  {out_tif}: {peat_cells * c * c / 1e10:.3f} million ha of peat", flush=True)


def main(argv=None):
    data = Path(os.environ.get("REPEAT_DATA", "_data"))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpkg", type=Path, default=data / NAME)
    ap.add_argument("--villages", type=Path, default=data / VILLAGES)
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("REPEAT_WORK", "re-peat/reports")) / "national_profile" / "ppeg")
    ap.add_argument("--registry", type=Path, default=Path(os.environ.get("REPEAT_HUB", "re-peat")) / "sites" / "khg_registry.csv")
    ap.add_argument("--layers", action="store_true", help="also write the dissolved layers (reads the geometry in chunks)")
    ap.add_argument("--peat-out", type=Path, default=data / "peat" / "ppeg_lahan_gambut_2026.gpkg")
    ap.add_argument("--chunk", type=int, default=100_000, help="features per chunk when dissolving")
    ap.add_argument("--peat-raster", type=Path, metavar="CONFIG",
                    help="only burn the peat extent (--peat-out) onto the fire tally grid of this national config; writes <peat-out stem>_30m.tif")
    a = ap.parse_args(argv)
    if a.peat_raster:
        peat_raster(a.peat_raster, a.peat_out, a.peat_out.with_name(a.peat_out.stem + "_30m.tif"))
        return
    targets = village_keys(a.villages)
    f, side = load(a.gpkg, targets)
    t = summarise(f, side, a.registry)
    a.out.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out / "ppeg_khg.csv", index=False, float_format="%.2f")
    num = t.select_dtypes("number").drop(columns=["priority_rank", "dome_share_of_priority"]).sum()
    for k in ["priority", "in_target_villages", "has_skeg_damage"]:
        num[f"khg_{k}"] = int(t[k].sum())
    num["khg_target_villages_only"] = int((t["in_target_villages"] & ~t["has_skeg_damage"]).sum())
    num["khg_skeg_only"] = int((t["has_skeg_damage"] & ~t["in_target_villages"]).sum())
    num["khg_without_code"] = int(((t["khg_code"] == "") & (t["khg_name"] != "NON KHG")).sum())
    num["target_villages_matched"] = len(targets)
    num.to_frame("value").to_csv(a.out / "ppeg_national.csv", float_format="%.2f")
    print(a.out / "ppeg_khg.csv")
    print(num[["khg_priority", "khg_in_target_villages", "khg_has_skeg_damage", "khg_target_villages_only", "khg_skeg_only",
               "priority_ha", "priority_in_target_villages_ha"]].to_string())
    if a.layers:
        layers(a.gpkg, targets, a.out / "ppeg_layers.gpkg", a.peat_out, a.chunk)


if __name__ == "__main__":
    main()
