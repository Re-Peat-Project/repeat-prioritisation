"""Hand-over package of the fire tally: one folder (and zip) with the tables as CSV and Excel, the full tallies as CSV, the checks,
the review layers and a data dictionary.

    python -m repeat_prioritisation.national.fire_export <out>/fire_landstatus DEST [--rasters] [--extra NAME=PATH ...] [--zip]

Reads what `fire_landstatus` and `fire_tables` wrote in <out>/fire_landstatus and writes, in DEST:
  README.md              contents, inputs, method in short, data dictionary
  fire_tables.xlsx       one sheet per table (tables/t_*.csv), sheet `columns` (the dictionary) and `about` (run settings)
  tables/                the same tables as CSV
  tally/                 area.csv, hot.csv, khg.csv (the tallies every table is a sum of), districts.csv, khg_index.csv
  checks/                checks*.csv, hotspots_outside_villages.csv
  layers/                summary.gpkg, hotspots_<year>.gpkg, and with --rasters status.vrt + tiles/ (30 m status and burn years)
  meta.json              run settings; input paths are given relative to the data folder
  extra/                 files passed with --extra (for example the per-KHG PPEG summary)
Column descriptions come from `describe`, which follows the names the tally writes; a column it cannot describe stops the export.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import pandas as pd

KWS = "cons conservation, hl protection forest, prod production forest (HP, HPT), hpk convertible production forest, apl other land use (APL), other water or undefined, none not mapped"
LIC = "sawit oil palm, tambang mining, pphtr plantation forest (PPHTR), pbph forest concession (PBPH), none no concession; a cell in several licences takes the first type in this order. Community forest (PPHKM) is not a concession"

FIXED = {
    "basis": "all = all land (inside the 2023 village boundaries); peat = only the cells on KLH peat (PPEG LAHAN_GAMB = LAHAN GAMBUT)",
    "_all": "Indonesia (national total)",
    "island": "island group, from the 2023 village boundaries (PULAU)",
    "province": "province, from the 2023 village boundaries (PROV_2023)",
    "district": "district (kabupaten/kota), from the 2023 village boundaries (KABKO_2023)",
    "kab": "district index (districts.csv)",
    "idx": "KHG index used in the 30 m raster (band 5)",
    "in_khg": "True = inside one of the KHG (peat hydrological units)",
    "khg_id": "KHG code (SK.129/MENLHK/2017 registry; the KHG name where no code matches)",
    "nama": "KHG name (NAMA_KHG of the KHG boundaries)",
    "forest_group": "kawasan = forest area (conservation, protection, production, convertible); apl = other land use; other = water, undefined or not mapped",
    "kawasan": "forest area function: " + KWS,
    "class": "forest area function: " + KWS,
    "concession": "concession type: " + LIC,
    "concession_any": "True = inside an oil palm, mining, PPHTR or PBPH licence (2025)",
    "lic_bits": "licence types present, as bits: 1 oil palm, 2 mining, 4 PPHTR, 8 PBPH, 16 PPHKM (add up when licences overlap)",
    "licence": "licence type; a cell in several licences is counted under each, so rows do not add up: sawit, tambang, pphtr, pbph, pphkm",
    "licence_types": "licence types at the hotspot, comma separated (sawit, tambang, pphtr, pbph, pphkm)",
    "dmpg": "True = inside a Desa Mandiri Peduli Gambut village (SiTMAT DMPG layer)",
    "peat": "1 = KLH peat, 0 = not peat, 3 = no peat information",
    "source": "hotspot sensor: modis (KLH series of the current year) or viirs (S-NPP, all years)",
    "file": "hotspot input file",
    "year": "year",
    "month": "month of detection",
    "conf": "hotspot confidence: low, medium or high",
    "static": "True = within static_radius_m of a VIIRS detection typed volcano, static land source or offshore (likely not a vegetation fire)",
    "ytd": "True = on or before the day and month of the last VIIRS date of the current year (comparable part of each year)",
    "on_land": "True = inside the 2023 village boundaries",
    "n": "number of hotspots",
    "area_ha": "area, hectares (30 m equal-area cells, EPSG:6933)",
    "unburned_ha": "area not burned in any year of the burned-area record, hectares",
    "burned_any_ha": "area burned in at least one year of the burned-area record, hectares",
    "burned_2plus_ha": "area burned in two or more different years, hectares",
    "burned_1x_ha": "area burned in exactly one year, hectares",
    "burned_2x_ha": "area burned in exactly two different years, hectares",
    "burned_3x_ha": "area burned in exactly three different years, hectares",
    "burned_4plus_ha": "area burned in four or more different years, hectares",
    "peat_ha": "KLH peat area, hectares",
    "provinces": "number of provinces with DMPG village land (the comparison is limited to them)",
    "scope": "Indonesia or province", "name": "Indonesia or the province name",
    "burned_ha": "burned area of the year, hectares",
    "viirs_n": "VIIRS hotspots of the year (medium + high, static left out)",
    "ha_per_detection": "burned hectares per VIIRS hotspot; low values point to an incomplete burned-area map for that year",
    "check": "what is compared", "measure": "the quantity compared", "value": "value in the outputs", "reference": "value it must agree with",
    "diff": "value minus reference",
    "tile": "90 km tile of the 30 m grid (i_j)", "exact_ha": "exact area of the burned polygons in the tile, hectares",
    "raster_ha": "burned area on the 30 m grid in the tile, hectares", "raster_land_ha": "the same, on land cells only, hectares",
    "n_file": "hotspots in the input file (after the type filter)", "n_tiles": "hotspots counted in the land tiles",
    "outside_land_tiles": "hotspots in tiles without land (sea, neighbouring countries)",
    "land_km2": "area by the national profile's 100 m grid, km²", "fire_km2": "area by this tally, km²", "rel_diff": "relative difference",
    "diff_km2": "difference, km²",
    "radius_m": "static-source radius, metres", "detections": "VIIRS detections tested", "typed_static": "detections typed static in the file",
    "flagged": "detections the radius rule flags", "true_pos": "flagged and typed static", "false_pos": "flagged, not typed static",
    "false_neg": "typed static, not flagged", "precision": "true_pos / flagged", "recall": "true_pos / typed_static",
}


def describe(col):
    if col in FIXED:
        return FIXED[col]
    m = re.fullmatch(r"burned_((?:19|20)\d{2})_ha", col)
    if m:
        return f"area burned in {m[1]} (KLHK burned-area flag BA_{m[1]}), hectares"
    m = re.fullmatch(r"burned_(\d{2})(\d{2})_ha", col)
    if m:
        return f"area burned in 20{m[1]}-20{m[2]}, summed over the years (a cell burned twice counts twice), hectares"
    m = re.fullmatch(r"modis_(\d{4})_(n|high_n|static_n)", col)
    if m:
        return {"n": f"MODIS hotspots {m[1]}, medium + high confidence, static sources left out",
                "high_n": f"MODIS hotspots {m[1]}, high confidence only, static sources left out",
                "static_n": f"MODIS hotspots {m[1]} flagged static (medium + high), not counted in modis_{m[1]}_n"}[m[2]]
    m = re.fullmatch(r"viirs_(\d{4})(_ytd)?_n", col)
    if m:
        part = "from 1 January to the day and month of the last VIIRS date of the current year" if m[2] else "full year"
        return f"VIIRS S-NPP hotspots {m[1]}, {part}, medium + high confidence, static sources left out"
    m = re.fullmatch(r"modis(\d{2})(_peat|_per100km2)?", col)
    if m:
        return f"MODIS hotspots 20{m[1]}, medium + high, static left out" + {None: "", "_peat": ", on KLH peat", "_per100km2": ", per 100 km² of land"}[m[2]]
    m = re.fullmatch(r"(area|burned|modis\d{2})_(conc|kws|dmpg)_pct", col)
    if m:
        what = {"area": "area", "burned": "past burned area (burned_yyyy_ha summed)"}.get(m[1], f"MODIS hotspots 20{m[1][-2:]}")
        where = {"conc": "inside concessions", "kws": "inside forest area (kawasan hutan)", "dmpg": "inside DMPG villages"}[m[2]]
        return f"share of the {what} {where}, %"
    raise KeyError(f"no description for column {col!r}: add it to fire_export.FIXED")


def clean_meta(meta, data_dir=None):
    """meta.json with input paths relative to the data folder (no local paths in a hand-over)."""
    m = json.loads(json.dumps(meta))
    for k, v in m.get("inputs", {}).items():
        if isinstance(v, str) and (Path(v).is_absolute() or ":" in v):
            p = Path(v)
            try:
                m["inputs"][k] = p.relative_to(data_dir).as_posix() if data_dir else p.name
            except ValueError:
                m["inputs"][k] = p.name
    return m


def export(src, dest, rasters=False, extra=None, data_dir=None, sources=None):
    src, dest = Path(src), Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    for d in ("tables", "tally", "checks", "layers"):
        (dest / d).mkdir(parents=True)
    meta = clean_meta(json.loads((src / "meta.json").read_text(encoding="utf-8")), data_dir)
    (dest / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    cols, files = {}, []

    def note(path, df):
        files.append((path, len(df)))
        for c in df.columns:
            cols.setdefault(c, describe(c))

    tables = {f.stem: pd.read_csv(f, keep_default_na=False) for f in sorted((src / "tables").glob("t_*.csv"))}
    for name, t in tables.items():
        shutil.copy2(src / "tables" / f"{name}.csv", dest / "tables")
        note(f"tables/{name}.csv", t)
    for x in ("area", "hot", "khg"):
        t = pd.read_parquet(src / f"{x}.parquet")
        t.to_csv(dest / "tally" / f"{x}.csv", index=False)
        note(f"tally/{x}.csv", t)
    for x in ("districts", "khg_index"):
        shutil.copy2(src / f"{x}.csv", dest / "tally")
        note(f"tally/{x}.csv", pd.read_csv(src / f"{x}.csv"))
    for f in sorted(src.glob("checks*.csv")) + [src / "hotspots_outside_villages.csv"]:
        if f.exists():
            shutil.copy2(f, dest / "checks")
            note(f"checks/{f.name}", pd.read_csv(f))
    import pyogrio
    lay = src / "layers"
    for f in sorted(lay.glob("*.gpkg")):
        shutil.copy2(f, dest / "layers")
        for name in pyogrio.list_layers(f)[:, 0]:
            info = pyogrio.read_info(f, layer=name)
            files.append((f"layers/{f.name} ({name})", info["features"]))
            for c in info["fields"]:
                cols.setdefault(c, describe(c))
    if (lay / "README.md").exists():
        shutil.copy2(lay / "README.md", dest / "layers")
    if rasters and (lay / "status.vrt").exists():
        shutil.copy2(lay / "status.vrt", dest / "layers")
        shutil.copytree(lay / "tiles", dest / "layers" / "tiles")
        files.append(("layers/status.vrt + tiles/", len(list((lay / "tiles").glob("*.tif")))))
    for name, path in (extra or {}).items():
        (dest / "extra").mkdir(exist_ok=True)
        shutil.copy2(path, dest / "extra" / name)
        files.append((f"extra/{name}", None))

    dic = pd.DataFrame(sorted(cols.items()), columns=["column", "description"])
    about = pd.DataFrame([(k, json.dumps(v) if not isinstance(v, str) else v) for k, v in meta.items()], columns=["setting", "value"])
    with pd.ExcelWriter(dest / "fire_tables.xlsx", engine="openpyxl") as xw:
        about.to_excel(xw, sheet_name="about", index=False)
        dic.to_excel(xw, sheet_name="columns", index=False)
        for name, t in tables.items():
            t.to_excel(xw, sheet_name=name[:31], index=False)
    (dest / "README.md").write_text(readme(meta, files, dic, sources), encoding="utf-8")
    return dest


def readme(meta, files, dic, sources=None):
    y0, y1 = meta["years"]
    lines = [f"# Burned area and hotspots by land status, Indonesia {y0}-{y1}", "",
             f"Burned area {y0}-{y1} and hotspots counted on a {meta['cell_m']} m equal-area grid ({meta['crs']}) over all land inside the "
             "2023 village boundaries, by concession (business licences), forest area function, DMPG village and peat. "
             f"Hotspots run to {meta.get('viirs_last')} (VIIRS) and {meta.get('modis_last')} (MODIS).", "",
             "Every table in `tables/` is a sum over `tally/area.csv` (area and burned area per class) and `tally/hot.csv` (hotspot counts per "
             "class, sensor, year, month, confidence). Hotspot measures count medium and high confidence and leave out likely static sources "
             "unless a column says otherwise. `checks/checks.csv` holds the totals that must agree (tables against the national total, the "
             "grid against the exact polygon areas, hotspots against the input files).", "",
             "Tables with a `basis` column give every row twice: `all` (all land) and `peat` (KLH peat only).", "",
             "## Inputs", "", "| Input | File | Source |", "|---|---|---|"]
    for k, v in meta["inputs"].items():
        for f in (v if isinstance(v, list) else [v]):
            lines.append(f"| {k} | `{f}` | {(sources or {}).get(f, '')} |")
    lines += ["", "## Files", "", "| File | Rows |", "|---|---|"]
    lines += [f"| `{p}` | {'' if n is None else f'{n:,}'} |" for p, n in files]
    lines += ["", "## Columns", "", "| Column | Meaning |", "|---|---|"]
    lines += [f"| `{r.column}` | {r.description} |" for r in dic.itertuples()]
    return "\n".join(lines) + "\n"


def zip_dir(d):
    return Path(shutil.make_archive(str(d), "zip", root_dir=Path(d).parent, base_dir=Path(d).name))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="<out>/fire_landstatus")
    ap.add_argument("dest", type=Path)
    ap.add_argument("--rasters", action="store_true", help="also copy the 30 m status rasters (layers/tiles, about 170 MB)")
    ap.add_argument("--extra", nargs="*", default=[], metavar="NAME=PATH")
    ap.add_argument("--zip", action="store_true")
    a = ap.parse_args(argv)
    d = export(a.src, a.dest, a.rasters, dict(x.split("=", 1) for x in a.extra))
    print(zip_dir(d) if a.zip else d)


if __name__ == "__main__":
    main()
