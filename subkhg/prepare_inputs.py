#!/usr/bin/env python3
"""Cut the big national vector files down to one KHG, so runs do not re-read hundreds of MB each time.

  python -m subkhg.prepare_inputs --khg-shp <KHG shapefile> --khg-id 71 --out data_local/kampar_gaung \\
      --canals kanal.gpkg --rivers sungai.gpkg --lakes danau.gpkg \\
      --blocks infrastruktur.gpkg --blocks-where "Jenis == 'Sekat Kanal' and KETERANGAN == 'REALISASI'"

Writes into --out: khg.gpkg (EPSG:4326, with the id column khg_id) and one GeoPackage per layer given. Features that
touch the KHG plus a buffer are kept whole (lines are not cut). Only the window around the KHG is read from each file.
"""
import argparse
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

log = logging.getLogger("prioritas.prepare")


def clip_layer(path, poly_ll, buffer_deg: float, where: str | None = None) -> gpd.GeoDataFrame:
    import pyogrio
    info = pyogrio.read_info(path)
    area = poly_ll.buffer(buffer_deg)
    if "4326" in str(info["crs"]):
        bbox, crs_area = tuple(area.bounds), area
    else:
        crs_area = gpd.GeoSeries([area], crs=4326).to_crs(info["crs"]).iloc[0]
        bbox = tuple(crs_area.bounds)
    g = gpd.read_file(path, bbox=bbox, engine="pyogrio")
    g = g[g.intersects(crs_area)]
    if where:
        g = g.query(where, engine="python")
    return g.to_crs(4326)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--khg-shp", required=True, help="KHG boundary file (any CRS)")
    ap.add_argument("--khg-id", required=True, help="id written to khg_id")
    ap.add_argument("--out", required=True)
    ap.add_argument("--buffer-km", type=float, default=2.0)
    for name in ("canals", "rivers", "lakes", "blocks"):
        ap.add_argument(f"--{name}")
        ap.add_argument(f"--{name}-where", help="pandas query to keep only some features")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    khg = gpd.read_file(a.khg_shp).to_crs(4326)
    poly = khg.geometry.union_all()
    khg = gpd.GeoDataFrame({"khg_id": [str(a.khg_id)]}, geometry=[poly], crs=4326)
    khg.to_file(out / "khg.gpkg", driver="GPKG")
    log.info("khg.gpkg: id %s, %.0f km2", a.khg_id, gpd.GeoSeries([poly], crs=4326).to_crs(32647).area.iloc[0] / 1e6)
    for name in ("canals", "rivers", "lakes", "blocks"):
        src = getattr(a, name)
        if not src:
            continue
        g = clip_layer(src, poly, a.buffer_km / 111.0, getattr(a, f"{name}_where"))
        g.to_file(out / f"{name}.gpkg", driver="GPKG")
        log.info("%s.gpkg: %d features", name, len(g))


if __name__ == "__main__":
    main()
