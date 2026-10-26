#!/usr/bin/env python3
"""Question: does our SiTMAT reader (common/tma.py) agree with the sitmat-extract project's own station summary?

Supports the TMA section of the README. With the extract's settings (the full period and 80% coverage) both should keep
the same stations and give the same mean depth. On 2026-10-15 both kept 307 stations and mean depths agreed to 2 cm.
If daily_long.csv was refreshed after baseline_out/ was written (the extract's update.py rewrites the first), the valid-day counts
differ by the days added; compare after regenerating baseline_out. The share of days deeper than 40 cm can differ, because the portal counts a reading of exactly -40 cm as "rawan"
and u_tma counts only readings deeper than 0.4 m.

  python scripts/check_tma_vs_sitmat.py --sitmat C:/.../sitmat-extract --start 2026-04-01 --end 2026-10-14 --min-coverage 0.8
"""
import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import pandas as pd

from repeat_prioritisation.common import pipeline
from repeat_common import tma as TMA


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sitmat", required=True, help="the sitmat-extract folder (has sitmat_out/ and baseline_out/)")
    ap.add_argument("--start", default="2026-04-01")
    ap.add_argument("--end", default="2026-10-14")
    ap.add_argument("--min-coverage", type=float, default=0.8)
    a = ap.parse_args()
    root = Path(a.sitmat)
    cfg = pipeline.load_config(None, {}, "subkhg")
    cfg["tma"].update(path=str(root / "sitmat_out" / "processed"), period=[a.start, a.end], min_coverage=a.min_coverage)
    t = TMA.load(cfg, [])
    ss = pd.read_csv(root / "baseline_out" / "station_summary.csv")
    ss = ss[ss.kind == "concession"].assign(key=lambda d: "concession/" + d.station_id).set_index("key")
    mine = t.assign(ex=t.depth_m > 0.4).groupby("station_id").agg(ex=("ex", "mean"), n=("date", "nunique"), depth_m=("depth_m", "mean"))
    both = mine.join(ss[["n_days", "pct_rawan", "pct_sangat_rawan", "mean"]], how="inner")
    print(f"stations: ours {len(mine)}, the extract's {len(ss)}, in both {len(both)}")
    print(f"same number of valid days: {(both.n == both.n_days).mean():.1%} of stations")
    print(f"max |mean depth difference|: {(both.depth_m * -100 - both['mean']).abs().max():.2f} cm")
    d = both.ex - (both.pct_rawan + both.pct_sangat_rawan)
    print(f"share of days deeper than 40 cm: max |difference| {d.abs().max():.2f} (the portal counts exactly -40 cm as rawan); median {d.abs().median():.3f}")


if __name__ == "__main__":
    main()
