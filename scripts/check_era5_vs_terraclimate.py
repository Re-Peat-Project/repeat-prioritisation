#!/usr/bin/env python3
"""Question: how close is ERA5 to TerraClimate where both exist, so how far can ERA5 stand in for TerraClimate's missing years?

Supports "Fallback for the TerraClimate gap" in docs/data_sources.md. For one month of one KHG it computes rain,
evaporation and deficit from ERA5 (repeat_common.sources.era5_water_balance) and compares them with the TerraClimate
layers in that KHG's cache. On the Riau test KHG, August 2021: evaporation 113 mm (ERA5) against 112 mm, rain 224 mm
against 184 mm, deficit 11 mm against 0. It reads about 1,240 hourly ERA5 fields (about 2 minutes).

  python scripts/check_era5_vs_terraclimate.py --khg tests/fixtures/khg_small.gpkg --khg-id 72 --cache tests/fixtures/prefetched/72 --year 2021 --month 8
"""
import argparse
import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import geopandas as gpd
import numpy as np
import rasterio

from repeat_common import grid as G
from repeat_prioritisation.common import pipeline
from repeat_common import sources as SRC


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--khg", required=True)
    ap.add_argument("--khg-id", required=True)
    ap.add_argument("--khg-id-field", default="khg_id")
    ap.add_argument("--cache", required=True, help="the KHG's cache folder: has climate/ppt_<year>.tif and aet_<year>.tif (12 bands)")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for n in ("azure", "fsspec", "rasterio._env"):
        logging.getLogger(n).setLevel(logging.WARNING)
    cfg = pipeline.load_config(None, {}, "subkhg")
    k = gpd.read_file(a.khg).to_crs(4326)
    k = k[k[a.khg_id_field].astype(str) == str(a.khg_id)]
    grid = G.make_grid(k.geometry.iloc[0], 30)
    r = SRC.era5_water_balance(a.year, [a.month], grid, cfg["sources"], months=[a.month])
    print(f"ERA5 {a.year}-{a.month:02d}: rain {np.mean(r['ppt']):.0f} mm, evaporation {np.mean(r['aet']):.0f} mm, deficit {np.mean(r['deficit']):.0f} mm")
    clim = Path(a.cache) / "climate"
    with rasterio.open(clim / f"ppt_{a.year}.tif") as p, rasterio.open(clim / f"aet_{a.year}.tif") as e:
        print(f"TerraClimate {a.year}-{a.month:02d}: rain {np.mean(p.read(a.month)):.0f} mm, actual evaporation {np.mean(e.read(a.month)):.0f} mm")
    print("(ERA5 deficit is potential minus actual evaporation; the TerraClimate deficit layer holds the dry-season sum, see the cache)")


if __name__ == "__main__":
    main()
