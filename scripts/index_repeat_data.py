#!/usr/bin/env python3
"""Question: for a KHG, which DTM and peat depth rasters in the REPEAT data folder cover it?

The file names do not match between the boundary, DTM and peat depth folders, so this matches them by location.
It reads only metadata (no pixels): the KHG shapefiles in BatasKHG/ and the rasters in DTM_*/ and PeatDepth_*/.

  python scripts/index_repeat_data.py --root "$REPEAT_DATA/Peat depth and DTM" --out ../re-peat/sites/repeat_data_index.csv

Writes one row per KHG shapefile: name, code, province, number of distinct Sub_KHG values, area, and the rasters whose
extent covers at least half of the KHG's bounding box (as paths relative to --root, with the covered share).
Check a match before using it: an extent overlap is not proof that the raster has data over the whole KHG.
"""
import argparse
import glob
import os
import warnings

warnings.filterwarnings("ignore")

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import box


def rasters(root, kind_dirs, exts):
    rows = []
    for d in sorted(glob.glob(os.path.join(root, kind_dirs))):
        for dp, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(exts):
                    p = os.path.join(dp, f)
                    try:
                        with rasterio.open(p) as s:
                            b = transform_bounds(s.crs, 4326, *s.bounds) if s.crs else s.bounds
                            rows.append({"path": os.path.relpath(p, root), "size_mb": round(os.path.getsize(p) / 1e6), "res": round(s.res[0], 8),
                                         "crs": str(s.crs), "box": box(*b)})
                    except Exception as e:
                        print("skip", p, type(e).__name__)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="the 'Peat depth and DTM' folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-cover", type=float, default=0.5)
    a = ap.parse_args()
    dtm = rasters(a.root, "DTM_*", (".tif", ".tiff"))
    peat = rasters(a.root, "PeatDepth_*", (".img", ".tif", ".tiff"))
    print(f"{len(dtm)} DTM rasters, {len(peat)} peat depth rasters")
    rows = []
    for shp in sorted(glob.glob(os.path.join(a.root, "BatasKHG", "*", "*.shp"))):
        try:
            g = gpd.read_file(shp)
        except Exception as e:
            print("skip", shp, type(e).__name__)
            continue
        g4 = g.to_crs(4326)
        b = box(*g4.total_bounds)
        c = g4.geometry.union_all().centroid

        def cover(lst):
            out = []
            for r in lst:
                share = b.intersection(r["box"]).area / b.area
                if share >= a.min_cover:
                    out.append((share, r["path"]))
            return "; ".join(f"{p} ({s:.0%})" for s, p in sorted(out, reverse=True))

        from repeat_common.grid import auto_utm
        rows.append({"khg": g["NAMA_KHG"].iloc[0] if "NAMA_KHG" in g else os.path.basename(shp), "code": g["KODE_KHG"].iloc[0] if "KODE_KHG" in g else "",
                     "province": g["PROVINSI"].iloc[0] if "PROVINSI" in g else "",
                     "sub_khg_values": int(g["Sub_KHG"].nunique()) if "Sub_KHG" in g else 0,
                     "area_km2": round(g4.to_crs(auto_utm(c.x, c.y)).area.sum() / 1e6),
                     "shapefile": os.path.relpath(shp, a.root), "dtm": cover(dtm), "peat_depth": cover(peat)})
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"{len(df)} KHG; with a DTM match: {(df.dtm != '').sum()}; with a peat depth match: {(df.peat_depth != '').sum()}; "
          f"with several Sub_KHG values: {(df.sub_khg_values > 1).sum()}")
    print("written", a.out)


if __name__ == "__main__":
    main()
