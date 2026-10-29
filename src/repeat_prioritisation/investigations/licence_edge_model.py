#!/usr/bin/env python3
"""What the groundwater model says about land beside licences: open-land depth by distance to the licence edge, with and without managed land held.

  python -m repeat_prioritisation.investigations.licence_edge_model --khg 14.02-04-05.01 [--khg ...] [--target 0.4]

Two runs of `repeat-neraca-model` per KHG with the same settings (LiDAR DTM, canal levels from LiDAR, canals inside cells), the baseline
without a managed target (every cell is computed) and the scenario with managed land (the licence layer) held at the target. The
rasters `model_season_days_deeper_40cm.tif` (days deeper than 40 cm of the dry season, June to September 2026) and
`model_season_mean_depth.tif` (cm) are sampled at the peat cells of `licence_edge` (cells.csv.gz), which carry the signed distance to the
licence edge and the position on the dome. Cells held by the scenario are left out of the comparison (their level is the target).

Reading: the baseline column is what the land does on its own (DTM, peat, canals, rain, evapotranspiration), by distance to the edge and
position. The change column is the model's answer to "does holding the licence land at the target move the open land beside it": the
only link is groundwater flow between cells and the canal cells (no canal routing between licences and open land, no outflow control).
It does not include what operators do with canal outflow. The managed target is an assumption (`concession_levels.md`).

Outputs in `<khg>/04_prioritisation/licence_edge/`: model_by_band.csv, model_report.md, figures/model_by_band.png.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from repeat_common import khg as K
from repeat_prioritisation.investigations.licence_edge import AEA, BAND_LABEL, POS, band_of

log = logging.getLogger("licence_edge_model")


def runs_dir(code, dem):
    return K.step_dir(code, "03_neraca", dem) / "runs" / "model"


def sample(path, x, y):
    with rasterio.open(path) as s:
        tf = Transformer.from_crs(AEA, s.crs, always_xy=True)
        px, py = tf.transform(x, y)
        a = s.read(1).astype(float)
        a[a == s.nodata] = np.nan
        col = np.floor((px - s.transform.c) / s.transform.a).astype(int)
        row = np.floor((py - s.transform.f) / s.transform.e).astype(int)
        ok = (row >= 0) & (row < a.shape[0]) & (col >= 0) & (col < a.shape[1])
        v = np.full(len(x), np.nan)
        v[ok] = a[row[ok], col[ok]]
    return v


def find_run(rd: Path, target, res="*"):
    """The run with the recommended set-up (peat table tropical-large, LiDAR canal levels, canals inside cells), with or without a target,
    on grid `res` (metres, as in the run name; the finest grid when not given)."""
    tag = f"_mt{target}" if target else ""
    hits = sorted((p for p in rd.glob(f"tropical-large_p0.8_s0.3_t0.3{tag}_lk_e0.3_{res}m_pb_dbbsdlp") if (p / "model_season_days_deeper_40cm.tif").exists()),
                  key=lambda p: int(p.name.split("_e0.3_")[1].split("m_")[0]), reverse=True)
    if not hits:
        raise FileNotFoundError(f"no run 'tropical-large ... {tag}_lk' in {rd}")
    return hits[-1]       # the finest grid


def one(code, dem, target):
    f = K.folder(code)
    out = f / "04_prioritisation" / "licence_edge"
    c = pd.read_csv(out / "cells.csv.gz", usecols=["x", "y", "edge_m", "position", "canal_m"])
    c["position"] = c["position"].fillna("")
    rd = runs_dir(code, dem)
    base = find_run(rd, None)
    scen = find_run(rd, target, base.name.split("_e0.3_")[1].split("m_")[0])       # same grid as the baseline
    for tag, run in (("base", base), ("scen", scen)):
        c[f"days_{tag}"] = sample(run / "model_season_days_deeper_40cm.tif", c.x.to_numpy(), c.y.to_numpy())
        c[f"depth_{tag}"] = sample(run / "model_season_mean_depth.tif", c.x.to_numpy(), c.y.to_numpy())
    open_ = c.days_scen.notna() & c.days_base.notna()          # not held in the scenario, and computed in both
    c = c[open_ & c.edge_m.notna()].copy()
    c["band"] = band_of(c.edge_m.to_numpy())
    c["d_days"] = c.days_scen - c.days_base
    c["d_depth"] = c.depth_scen - c.depth_base
    rows = []
    for pos in ["all"] + POS:
        s0 = c if pos == "all" else c[c.position == pos]
        for i, lab in enumerate(BAND_LABEL):
            s = s0[s0.band == i]
            if len(s) < 10:
                continue
            rows.append({"position": pos, "band": lab, "band_i": i, "cells": len(s), "base_days_deeper_40": s.days_base.mean(),
                         "scen_days_deeper_40": s.days_scen.mean(), "change_days": s.d_days.mean(), "base_depth_cm": s.depth_base.mean(),
                         "change_depth_cm": s.d_depth.mean(), "median_canal_m": s.canal_m.median()})
    t = pd.DataFrame(rows)
    t.to_csv(out / "model_by_band.csv", index=False)
    meta = {"khg": code, "baseline": base.name, "scenario": scen.name}
    figure(out, t, code)
    report(out, t, meta)
    return t, meta


def figure(out, t, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (out / "figures").mkdir(exist_ok=True)
    col = {"foot": "#1b9e77", "slope": "#d95f02", "crest": "#7570b3", "all": "#333333"}
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharex=True)
    for pos in ["all"] + POS:
        s = t[t.position == pos].sort_values("band_i")
        if len(s):
            ax[0].plot(s.band_i, s.base_days_deeper_40, marker="o", ms=3, color=col[pos], label=pos, ls="--" if pos == "all" else "-")
            ax[1].plot(s.band_i, s.change_days, marker="o", ms=3, color=col[pos], ls="--" if pos == "all" else "-")
    ax[0].set_ylabel("baseline: days deeper than 40 cm (Jun-Sep 2026)")
    ax[1].set_ylabel("change with licence land held at the target (days)")
    ax[1].axhline(0, color="k", lw=0.6)
    for a in ax:
        a.axvline(3.5, color="k", lw=0.8)
        a.set_xticks(range(len(BAND_LABEL)), BAND_LABEL, rotation=35, ha="right")
        a.set_xlabel("distance to licence edge (negative inside); open land only")
    ax[0].legend(title="dome position", fontsize=8)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "figures" / "model_by_band.png", dpi=150)
    plt.close(fig)


def report(out, t, meta):
    a = t[t.position == "all"][["band", "cells", "base_days_deeper_40", "scen_days_deeper_40", "change_days", "base_depth_cm", "change_depth_cm", "median_canal_m"]]
    L = [f"# Model: land beside licences, {meta['khg']}", "",
         f"Baseline `{meta['baseline']}`; scenario `{meta['scenario']}`. Open land only (cells held in the scenario are left out). "
         "Written by `repeat_prioritisation.investigations.licence_edge_model`. The model is in development and the managed target is an assumption.", "",
         "## All positions", "", a.round(2).to_markdown(index=False), "", "![](figures/model_by_band.png)", ""]
    (out / "model_report.md").write_text("\n".join(L), encoding="utf-8")


def hub_report():
    """Cross-KHG table in re-peat/reports/investigations/licence_edge_model.md from each KHG's model_by_band.csv (all positions)."""
    import os
    rows = []
    for f in sorted(K.root().glob("*/04_prioritisation/licence_edge/model_by_band.csv")):
        t = pd.read_csv(f)
        t = t[t.position == "all"].assign(KHG=f.parents[2].name)
        rows.append(t[["KHG", "band", "cells", "base_days_deeper_40", "change_days", "base_depth_cm", "change_depth_cm"]])
    if not rows:
        return
    a = pd.concat(rows)
    pv = a.pivot(index="band", columns="KHG", values="change_days").reindex(BAND_LABEL)
    L = ["# Groundwater model: open land beside licences", "",
         "`python -m repeat_prioritisation.investigations.licence_edge_model --khg <code> ...`. Change in days deeper than 40 cm over June to September 2026 on open "
         "land, when licence land is held at 0.4 m against the same run without a managed target (LiDAR canal levels, canals inside cells), by distance "
         "to the licence edge (negative inside). Method and per-KHG tables: `licence_edge_model.py`, `_khg/<khg>/04_prioritisation/licence_edge/model_report.md`.", "",
         "## Change in days deeper than 40 cm (of 122)", "", pv.round(2).to_markdown(), "",
         "## Baseline days deeper than 40 cm, no managed target", "", a.pivot(index="band", columns="KHG", values="base_days_deeper_40").reindex(BAND_LABEL).round(1).to_markdown(), "",
         "The only link between licence land and open land in the model is groundwater flow between cells and the canal cells; there is no canal routing between "
         "them and no outflow control. The managed target is an assumption (`repeat-neraca/docs/reports/concession_levels.md`).", ""]
    dst = Path(os.environ.get("REPEAT_HUB") or K.WORKSPACE / "re-peat") / "reports" / "investigations" / "licence_edge_model.md"
    dst.write_text("\n".join(L), encoding="utf-8")
    log.info("wrote %s", dst)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--khg", nargs="+", required=True)
    ap.add_argument("--dem", default="lidar")
    ap.add_argument("--target", default="0.4")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for code in a.khg:
        try:
            t, meta = one(code, a.dem, a.target)
            log.info("%s: %s vs %s", code, meta["baseline"], meta["scenario"])
        except Exception as e:      # noqa: batch: one KHG failing must not stop the others
            log.error("%s failed: %s", code, e)
    hub_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
