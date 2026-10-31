"""Compare the KLH 2026 hotspot file with the FIRMS MODIS NRT stream before they are joined.

  python -m repeat_prioritisation.investigations.hotspot_splice [--data DIR] [--out DIR] [--write]

KLH (`_data_hotspot_Januari_September_2026.gpkg`) is a curated MODIS extract that stops on 15 September; FIRMS MODIS NRT
(`hotspot_modis_nrt_2026.gpkg`, repeat_common.fetch_firms_nrt) runs to today. Over the days both cover, the script compares
detections per month, per confidence class and per day, and matches points (same satellite, date, time and a position within
0.01 degrees). A splice is only sound if the two agree there. Writes hotspot_splice.md (and the daily counts) to --out. With
--write it also writes `hotspots_modis_2026.gpkg`: KLH to its last date, FIRMS after it, in one schema (acq_date, month,
level low/medium/high, frp, satellite, source), the file the national profile reads.
"""
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

LEVEL_NAMES = {"rendah": "low", "low": "low", "sedang": "medium", "medium": "medium", "tinggi": "high", "high": "high"}
LEVEL_EDGES = (30, 80)      # low <30, medium 30-79, high >=80: the KLH classes follow these limits exactly (checked below)


def level(conf):
    return pd.cut(pd.to_numeric(conf, errors="coerce"), [-1, LEVEL_EDGES[0] - 1, LEVEL_EDGES[1] - 1, 101], labels=["low", "medium", "high"]).astype(str)


def load(data):
    k = pyogrio.read_dataframe(data / "_data_hotspot_Januari_September_2026.gpkg")
    k = pd.DataFrame({"acq_date": pd.to_datetime(k.ACQ_DATE).dt.normalize(), "acq_time": k.ACQ_TIME.astype("Int64"),
                      "satellite": k.SATELLITE, "confidence": k.CONFIDENCE, "frp": k.FRP, "klh_class": k.C_LEVEL,
                      "klh_level": k.C_LEVEL.fillna(k.Kepercayaa).astype("string").str.lower().map(LEVEL_NAMES),
                      "month": k["layer"].str[:2].astype(int), "lon": k.geometry.x, "lat": k.geometry.y})
    f = pyogrio.read_dataframe(data / "hotspot_modis_nrt_2026.gpkg", layer="hotspots")
    f = pd.DataFrame({"acq_date": pd.to_datetime(f.acq_date).dt.normalize(), "acq_time": f.acq_time.astype("Int64"),
                      "satellite": f.satellite, "confidence": f.confidence, "frp": f.frp, "lon": f.geometry.x, "lat": f.geometry.y})
    return k, f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.environ.get("REPEAT_DATA"))
    ap.add_argument("--out", default=str(Path(os.environ.get("REPEAT_WORK", ".")) / "investigations" / "hotspot_splice"))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    k, f = load(data)
    k_all = k                                  # five of the nine KLH months carry no date, confidence number or FRP: kept
    k = k_all[k_all.acq_date.notna()].copy()   # the comparison uses the dated rows
    last = k.acq_date.max()
    k["level"], f["level"] = level(k.confidence), level(f.confidence)
    agree = (k.klh_level == k.level).mean()

    lo = f.acq_date.min()                                   # FIRMS NRT keeps about two months: the overlap starts there
    both = f[f.acq_date <= last]
    ko = k[k.acq_date >= lo]
    daily = pd.DataFrame({"klh": ko.groupby("acq_date").size(), "firms": both.groupby("acq_date").size()}).fillna(0).astype(int)
    daily["ratio"] = daily.firms / daily.klh.replace(0, np.nan)
    daily.to_csv(out / "daily_counts.csv")
    lv = pd.DataFrame({"klh": ko.groupby("level").size(), "firms": both.groupby("level").size()})
    ratio_all = daily.firms.sum() / daily.klh.sum()

    # point match: the same satellite pass and a position within 0.01 degrees
    key = lambda d: (d.acq_date.dt.strftime("%Y%m%d") + "_" + d.satellite.astype(str) + "_" + d.acq_time.astype(str).str.zfill(4) + "_"
                     + (d.lon / 0.01).round().astype(int).astype(str) + "_" + (d.lat / 0.01).round().astype(int).astype(str))
    kk, ff = set(key(ko)), set(key(both))
    matched = len(kk & ff)
    lines = ["# KLH hotspots against FIRMS MODIS NRT", "",
             f"KLH: {len(k_all):,} detections in the file, {len(k):,} with a date ({k.acq_date.min():%Y-%m-%d} to {last:%Y-%m-%d}; the other months carry no date). FIRMS MODIS NRT: {f.acq_date.min():%Y-%m-%d} to "
             f"{f.acq_date.max():%Y-%m-%d}, {len(f):,} detections (the API serves about two months, so the two overlap from "
             f"{lo:%Y-%m-%d} to {last:%Y-%m-%d} only, {len(daily)} days).", "",
             f"KLH confidence classes against the numeric confidence cut at 30 and 80: {agree:.4f} of rows agree (low < 30, medium 30-79, high >= 80).", "",
             f"Over the overlap FIRMS has {daily.firms.sum():,} detections and KLH {daily.klh.sum():,} (FIRMS / KLH {ratio_all:.3f}; "
             f"daily ratio from {daily.ratio.min():.3f} to {daily.ratio.max():.3f}). "
             f"Points found in both (same satellite, date, time, position within 0.01 degree): {matched:,}, "
             f"{matched / len(kk):.1%} of KLH and {matched / max(len(ff), 1):.1%} of FIRMS points.", "",
             "## By class, overlap", "", "| class | KLH | FIRMS |", "|---|---|---|"]
    lines += [f"| {c} | {int(r.klh):,} | {int(r.firms):,} |" for c, r in lv.iterrows()]
    lines += ["", "## Per day, overlap", "", "| date | KLH | FIRMS | FIRMS / KLH |", "|---|---|---|---|"]
    lines += [f"| {d:%Y-%m-%d} | {r.klh:,} | {r.firms:,} | {r.ratio:.3f} |" for d, r in daily.iterrows()]
    text = "\n".join(lines) + "\n"
    (out / "hotspot_splice.md").write_text(text, encoding="utf-8")
    print(text)

    if a.write:
        import geopandas as gpd
        today = pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
        new = f[(f.acq_date > last) & (f.acq_date < today)]       # the current UTC day is still being filled: left out
        cols = ["acq_date", "acq_time", "satellite", "confidence", "level", "frp", "lon", "lat"]
        k2 = k_all.assign(level=k_all.klh_level, source="KLH")[cols + ["month", "source"]]
        n2 = new.assign(source="FIRMS NRT", month=new.acq_date.dt.month)[cols + ["month", "source"]]
        d = pd.concat([k2, n2], ignore_index=True)
        for c in ("confidence", "frp", "acq_time"):
            d[c] = pd.to_numeric(d[c], errors="coerce")        # numeric in the file, empty where KLH has none
        d["acq_date"] = d.acq_date.dt.strftime("%Y-%m-%d")      # empty where the KLH month has no date
        g = gpd.GeoDataFrame(d.drop(columns=["lon", "lat"]), geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326)
        g.to_file(data / "hotspots_modis_2026.gpkg", layer="hotspots", driver="GPKG")
        print(f"wrote hotspots_modis_2026.gpkg: {len(k2):,} KLH + {len(n2):,} FIRMS NRT")


if __name__ == "__main__":
    main()
