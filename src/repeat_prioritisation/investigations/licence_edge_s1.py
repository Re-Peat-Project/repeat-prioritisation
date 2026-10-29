#!/usr/bin/env python3
"""Sentinel-1 backscatter change from the wet to the dry months, by distance to the licence edge, inside one land-cover class.

  python -m repeat_prioritisation.investigations.licence_edge_s1 --khg 14.02-04-05.01 [--wet 2026-04 2026-05] [--dry 2026-07 2026-08 2026-09]

Reads `03_neraca/inputs/s1/s1_*.tif` (repeat_common.gee_s1: monthly VV and VH in dB and WorldCover shares on the 200 m licence-edge grid)
and the cells of `licence_edge`. Per cell: VV and VH of the wet months and of the dry months (mean of dB), and their difference
dry minus wet. C-band backscatter rises with topsoil moisture in open peat and weakens under dense canopy and with a deep water table
(the studies are in gee_s1.py), and cover decides the level, so the comparison is inside a cover class:
  tree     tree share of the cell 0.8 or more (forest, plantations with closed canopy)
  open     tree share below 0.3, with water, built and bare shares below 0.1 (shrub, grass, crop, burnt land)
Cells with 0.1 or more open water are dropped. A fall of VV from the wet to the dry months is read as a drying signal in that class;
how large it is for a given water table depth is not calibrated here (no tropical station record at the cell scale).
The contrast is the difference of the mean change between 0-2 km outside and 0-2 km inside the licence edge, same class and position;
interval from resampling 5 km blocks.

Outputs in `<khg>/04_prioritisation/licence_edge/`: s1_by_band.csv, s1_contrast.csv, s1_report.md, figures/s1_by_band.png.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

import numpy as np
import pandas as pd
import rasterio

from repeat_common import khg as K
from repeat_prioritisation.investigations.licence_edge import BAND_LABEL, POS, band_of

log = logging.getLogger("licence_edge_s1")


def read_cells(code, wet, dry):
    f = K.folder(code)
    need = {f"{m}-01" for m in list(wet) + list(dry)}
    tifs = []
    for t in sorted((f / "03_neraca" / "inputs" / "s1").glob("s1_*.tif"), key=lambda p: p.stat().st_mtime):
        side = t.with_suffix(".json")
        if side.exists() and need <= set(json.loads(side.read_text())["months"]):       # only a fetch that holds every wet and dry month
            tifs.append(t)
    if not tifs:
        raise FileNotFoundError("no s1_*.tif with the wet and dry months: run repeat_common.gee_s1 first")
    with rasterio.open(tifs[-1]) as s:
        a, d, t = s.read(), list(s.descriptions), s.transform
    c = pd.read_csv(f / "04_prioritisation" / "licence_edge" / "cells.csv.gz", usecols=["x", "y", "edge_m", "position", "canal_m"])
    c["position"] = c["position"].fillna("")
    col, row = ((c.x - t.c) // t.a).astype(int), ((t.f - c.y) // -t.e).astype(int)
    ok = (col >= 0) & (col < a.shape[2]) & (row >= 0) & (row < a.shape[1])
    col, row = col.where(ok, 0), row.where(ok, 0)
    g = lambda name: np.where(ok, a[d.index(name)][row, col], np.nan)
    for pol in ("vv", "vh"):
        for tag, mm in (("wet", wet), ("dry", dry)):
            c[f"{pol}_{tag}"] = np.nanmean(np.vstack([g(f"{pol}_{m}") for m in mm]), axis=0)
        c[f"{pol}_d"] = c[f"{pol}_dry"] - c[f"{pol}_wet"]
    for k in ("10", "20", "30", "40", "50", "60", "80", "90", "95"):
        c[f"wc{k}"] = g(f"wc{k}")
    c["cover"] = np.where((c.wc80 < 0.1) & (c.wc10 >= 0.8), "tree",
                          np.where((c.wc80 < 0.1) & (c.wc10 < 0.3) & (c.wc50 < 0.1) & (c.wc60 < 0.1), "open", ""))
    c["block"] = (np.floor(c.x / 5000).astype(int).astype(str) + "_" + np.floor(c.y / 5000).astype(int).astype(str))
    return c, tifs[-1].name


def block_diff(inn, out, col, n_boot=1000, seed=1):
    """Mean of col outside minus inside, with a 95% interval from resampling 5 km blocks (cells of both sides are drawn by block)."""
    def agg(d, tag):
        return d.groupby("block")[col].agg(**{f"s_{tag}": "sum", f"n_{tag}": "count"})
    t = agg(inn, "i").join(agg(out, "o"), how="outer").fillna(0)
    A = t[["s_i", "n_i", "s_o", "n_o"]].to_numpy(float)
    est = A[:, 2].sum() / A[:, 3].sum() - A[:, 0].sum() / A[:, 1].sum()
    if len(A) < 5:
        return est, np.nan, np.nan, len(A)
    idx = np.random.default_rng(seed).integers(0, len(A), size=(n_boot, len(A)))
    S = A[idx].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        b = S[:, 2] / S[:, 3] - S[:, 0] / S[:, 1]
    b = b[np.isfinite(b)]
    return est, float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5)), len(A)


def one(code, wet, dry):
    c, tif = read_cells(code, wet, dry)
    out = K.folder(code) / "04_prioritisation" / "licence_edge"
    c = c[c.cover.ne("") & c.edge_m.notna() & c.vv_d.notna()].copy()
    c["band"] = band_of(c.edge_m.to_numpy())
    rows, con = [], []
    for cov in ("tree", "open"):
        for pos in ["all"] + POS:
            s0 = c[(c.cover == cov) & ((c.position == pos) | (pos == "all"))]
            for i, lab in enumerate(BAND_LABEL):
                s = s0[s0.band == i]
                if len(s) >= 10:
                    rows.append({"cover": cov, "position": pos, "band": lab, "band_i": i, "cells": len(s), "vv_wet": s.vv_wet.mean(), "vv_dry": s.vv_dry.mean(),
                                 "vv_change": s.vv_d.mean(), "vh_change": s.vh_d.mean()})
            inn, outs = s0[(s0.edge_m > -2000) & (s0.edge_m <= 0)], s0[(s0.edge_m > 0) & (s0.edge_m <= 2000)]
            if len(inn) >= 30 and len(outs) >= 30:
                for pol in ("vv", "vh"):
                    est, lo, hi, nb = block_diff(inn, outs, f"{pol}_d")
                    con.append({"cover": cov, "position": pos, "pol": pol.upper(), "cells_inside": len(inn), "cells_outside": len(outs),
                                "outside_minus_inside_dB": est, "lo": lo, "hi": hi, "blocks": nb})
    t, k = pd.DataFrame(rows), pd.DataFrame(con)
    t.to_csv(out / "s1_by_band.csv", index=False)
    k.to_csv(out / "s1_contrast.csv", index=False)
    figure(out, t, code)
    L = [f"# Sentinel-1 wet to dry change at the licence edge, {code}", "",
         f"`{tif}`; wet months {', '.join(wet)}, dry months {', '.join(dry)}; dB, dry minus wet (negative: backscatter fell). Cover classes and method in "
         "`repeat_prioritisation.investigations.licence_edge_s1`. A backscatter change is a moisture signal, not a measured water table.", "",
         "## Contrast: 0-2 km outside minus 0-2 km inside the licence edge (dB)", "", k.round(2).to_markdown(index=False) if len(k) else "No class with enough cells on both sides.", "",
         "A negative contrast: the backscatter fell more outside the edge than inside, in the same class and position.", "",
         "![](figures/s1_by_band.png)", ""]
    (out / "s1_report.md").write_text("\n".join(L), encoding="utf-8")
    return k


def figure(out, t, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (out / "figures").mkdir(exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    col = {"foot": "#1b9e77", "slope": "#d95f02", "crest": "#7570b3", "all": "#333333"}
    for a, cov in zip(ax, ("tree", "open")):
        for pos in ["all"] + POS:
            s = t[(t.cover == cov) & (t.position == pos)].sort_values("band_i") if len(t) else t
            if len(s):
                a.plot(s.band_i, s.vv_change, marker="o", ms=3, color=col[pos], ls="--" if pos == "all" else "-", label=pos)
        a.axvline(3.5, color="k", lw=0.8)
        a.axhline(0, color="k", lw=0.4)
        a.set_title(f"{cov} cover", fontsize=9)
        a.set_xticks(range(len(BAND_LABEL)), BAND_LABEL, rotation=35, ha="right")
        a.set_xlabel("distance to licence edge (negative inside)")
    ax[0].set_ylabel("VV, dry minus wet (dB)")
    ax[0].legend(title="dome position", fontsize=8)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "figures" / "s1_by_band.png", dpi=150)
    plt.close(fig)


def hub_report():
    """Cross-KHG contrast table in re-peat/reports/investigations/licence_edge_s1.md from each KHG's s1_contrast.csv."""
    import os
    from pathlib import Path
    rows = []
    for f in sorted(K.root().glob("*/04_prioritisation/licence_edge/s1_contrast.csv")):
        t = pd.read_csv(f)
        if len(t):
            rows.append(t.assign(KHG=f.parents[2].name))
    if not rows:
        return
    a = pd.concat(rows)
    a = a[(a.pol == "VV")]
    a["outside minus inside, dB (95% interval)"] = a.apply(lambda r: f"{r.outside_minus_inside_dB:+.2f} ({r.lo:+.2f} to {r.hi:+.2f})", axis=1)
    pv = a.pivot_table(index=["KHG", "cover"], columns="position", values="outside_minus_inside_dB").reindex(columns=["all"] + POS)
    iv = a.assign(v=a["outside minus inside, dB (95% interval)"]).pivot_table(index=["KHG", "cover"], columns="position", values="v", aggfunc="first").reindex(columns=["all"] + POS)
    L = ["# Sentinel-1: wet to dry change beside licences", "",
         "`python -m repeat_common.gee_s1 --khg <code> --start 2026-04 --end 2026-09`, then `python -m repeat_prioritisation.investigations.licence_edge_s1 --khg <code>`. "
         "VV backscatter (dB, ascending orbit, ESA WorldCover classes on the 200 m licence-edge grid), mean of April-May against July-September 2026, inside one cover class. "
         "Value shown: change dry minus wet, 0-2 km outside the licence edge minus 0-2 km inside; positive means backscatter fell less outside. "
         "Interval from resampling 5 km blocks.", "", iv.reset_index().to_markdown(index=False), "",
         "A backscatter change is a moisture signal, not a measured water table. C-band is weak under dense canopy and for a deep water table. "
         "Tree and open cover inside and outside a licence can be different kinds of stand (planted, natural, regrowth, harvested): holding the cover class "
         "equal does not make the land comparable.", ""]
    dst = Path(os.environ.get("REPEAT_HUB") or K.WORKSPACE / "re-peat") / "reports" / "investigations" / "licence_edge_s1.md"
    dst.write_text("\n".join(L), encoding="utf-8")
    log.info("wrote %s", dst)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--khg", nargs="+", required=True)
    ap.add_argument("--wet", nargs="+", default=["2026-04", "2026-05"])
    ap.add_argument("--dry", nargs="+", default=["2026-07", "2026-08", "2026-09"])
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for code in a.khg:
        try:
            k = one(code, a.wet, a.dry)
            log.info("%s done\n%s", code, k.round(2).to_string(index=False) if len(k) else "no contrast")
        except Exception as e:      # noqa: batch: one KHG failing must not stop the others
            log.error("%s failed: %s", code, e)
    hub_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
