#!/usr/bin/env python3
"""Question: which cloud datasets exist for our needs, and do they cover the years we use?

Supports the provider table and the date-coverage findings in docs/data_sources.md (TerraClimate ends 2021-12, the
Planetary Computer ERA5 stops at 2020-12, the ARCO-ERA5 store reaches within days of today, CHIRPS needs politeness).

  python scripts/probe_cloud_sources.py catalogue --provider planetary-computer
  python scripts/probe_cloud_sources.py catalogue --provider cdse --pattern "swi|eta|burn"
  python scripts/probe_cloud_sources.py coverage

`catalogue` lists the STAC collections of a provider with their date range (collection ids come from the live
catalogue, not from memory). `coverage` reads the time axis of the datasets the pipeline depends on.
"""
import argparse
import re
import warnings

warnings.filterwarnings("ignore")

PROVIDERS = {"planetary-computer": "https://planetarycomputer.microsoft.com/api/stac/v1",
             "earth-search": "https://earth-search.aws.element84.com/v1",
             "cdse": "https://stac.dataspace.copernicus.eu/v1"}
DEFAULT_PATTERN = (r"era5|terraclimate|imerg|gpm|precip|evapo|smap|soil|sentinel-1|sentinel-2|landsat|cop-dem|nasadem|alos|"
                   r"modis-(13|16|17|64|09|43|11)|viirs|jrc|worldcover|lulc|biomass|gedi|burn|swi|eta\b|lai|ndvi")


def catalogue(provider: str, pattern: str):
    import pystac_client
    cl = pystac_client.Client.open(PROVIDERS[provider])
    rx = re.compile(pattern, re.I)
    n = 0
    for col in cl.get_collections():
        if rx.search(f"{col.id} {col.title or ''}"):
            t = col.extent.temporal.intervals[0]
            print(f"{col.id:52s} {(col.title or '')[:46]:46s} {str(t[0])[:10]}..{str(t[1])[:10] if t[1] else 'now'}")
            n += 1
    print(f"{n} collections match at {PROVIDERS[provider]}")


def coverage():
    import urllib.request

    import numpy as np
    import planetary_computer as pc
    import pystac_client
    import xarray as xr
    cl = pystac_client.Client.open(PROVIDERS["planetary-computer"], modifier=pc.sign_inplace)
    a = cl.get_collection("terraclimate").assets["zarr-abfs"]
    ds = xr.open_dataset(a.href, **a.extra_fields["xarray:open_kwargs"])
    print("TerraClimate (Planetary Computer zarr): %s .. %s" % (str(ds.time.values[0])[:10], str(ds.time.values[-1])[:10]))
    for yr in (2019, 2020, 2021, 2022, 2023):
        n = len(list(cl.search(collections=["era5-pds"], datetime=f"{yr}-01-01/{yr}-12-31", max_items=50).items()))
        print(f"ERA5 on Planetary Computer, items in {yr}: {n}")
    url = "https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
    e = xr.open_zarr(url, chunks=None, consolidated=None)
    tt = e.time.values
    pt = e["total_precipitation"].sel(latitude=0.1, longitude=102.5, method="nearest")

    def valid(i):
        return not np.isnan(float(pt.isel(time=i).values))

    lo = int(np.searchsorted(tt, np.datetime64("2026-01-01")))
    hi = int(np.searchsorted(tt, np.datetime64("now")))
    hi = min(hi, len(tt) - 1)
    if valid(hi):
        print("ARCO-ERA5: valid up to", str(tt[hi])[:13])
    else:
        a_, b_ = lo, hi
        while b_ - a_ > 24:
            m = (a_ + b_) // 2
            a_, b_ = (m, b_) if valid(m) else (a_, m)
        print("ARCO-ERA5: the last valid hour lies between", str(tt[a_])[:13], "and", str(tt[b_])[:13],
              "(the store's time axis nominally runs to", str(tt[-1])[:10] + ")")
    for y in (2022, 2023, 2024):
        u = f"https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/cogs/p05/{y}/chirps-v2.0.{y}.08.15.cog"
        try:
            code = urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=20).status
        except Exception as ex:
            code = str(ex)[:40]
        print(f"CHIRPS file 15 Aug {y}: {code}   (a full-year fetch with 8 workers got HTTP 403 and then a block; see docs/data_sources.md)")
    r = urllib.request.urlopen(urllib.request.Request("https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2021/viirs-snpp_2021_Indonesia.csv", method="HEAD"), timeout=30)
    print("FIRMS Indonesia VIIRS 2021 file: %.1f MB" % (int(r.headers.get("Content-Length", 0)) / 1e6))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalogue")
    c.add_argument("--provider", choices=list(PROVIDERS), default="planetary-computer")
    c.add_argument("--pattern", default=DEFAULT_PATTERN)
    sub.add_parser("coverage")
    a = ap.parse_args()
    catalogue(a.provider, a.pattern) if a.cmd == "catalogue" else coverage()


if __name__ == "__main__":
    main()
