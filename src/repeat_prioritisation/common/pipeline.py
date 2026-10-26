"""Shared pipeline for the national and sub-KHG prioritisation (entry points: national/run.py, subkhg/run.py)."""
from __future__ import annotations

import argparse
import copy
import json
import logging
import time
from pathlib import Path

import numpy as np  # noqa: F401
import pandas as pd

from repeat_common import grid as G
from repeat_common import sources as SRC
from repeat_common import tma as TMA
from repeat_common.config import deep_update, expand_env

from . import indicators as IND
from . import scoring as SC

log = logging.getLogger("prioritas")

DEFAULTS = {
    "khg": None,                      # vector file with KHG boundaries
    "khg_id_field": "khg_id",         # created from row number if missing
    "khg_filter": [],                 # run only these KHG ids (empty = all)
    "units": {"mode": "khg", "hex_area_km2": 1.0, "min_fraction": 0.2,
              "path": None, "id_field": "unit_id",
              "subkhg": {}},          # mode: khg | hex | vector (your polygons, e.g. subkhg_units.gpkg from repeat-delineation)
    "grid_res_m": 30,
    "years": {"baseline": [2016, 2022],   # indicators use these years only
              "validation": [2023],       # held-out years for checking the ranking
              "elnino": [2015, 2019, 2023]},
    "dry_months": [6, 7, 8, 9, 10],
    "ndmi_months": [8, 9, 10],
    "cache_dir": "cache",
    "out": "var/out",
    "sources": copy.deepcopy(SRC.SOURCE_DEFAULTS),
    "vectors": {"canals": None, "rivers": None, "lakes": None, "roads": None, "settlements": None,
                "protected": {"path": None, "field": None, "values": ["lindung"]},
                "blocks": None,       # existing canal blocks (points) for the IPG metric
                "tidal": None,        # tidally influenced zone (polygons)
                "concessions": {"path": None, "type_field": None, "exclude_types": ["IUP"]},
                "tma_csv": None},     # older input: CSV with station_id, date, wtd_m, lon, lat (use tma.path)
    "tma": copy.deepcopy(TMA.TMA_DEFAULTS),   # water table: path = SiTMAT folder (sitmat_out/processed) or CSV
    "rasters": {"peat_depth": None, "dtm": None},   # dtm: dtm_smooth.tif from demnas-corrections (repeat-dem)
    "extra_indicators": [],           # CSV / vector files with a unit_id column and indicator columns (u_*, i_*, f_*)
    "params": {"peat_depth_scale": 1.0,     # multiplier that turns the peat depth raster into metres (0.01 if it is in cm)
               "l_inf_m": 200, "l_inf_burnt_m": 60, "water_min_months": 10, "exposure_m": 2000,
               "forest_classes": [10, 95], "tma_threshold_m": 0.4, "tma_depth_positive": None,
               "tma_max_gap_days": 10,
               # water balance (Kahayan-Sebangau study, 2021): interception 0 % open land to 16.4 % forest;
               # runoff coefficient 0.07-0.18 measured on Pulau Padang (Aditya & Cahyono 2018)
               "runoff_coefficient": 0.12,
               "interception_by_class": {"10": 0.164, "95": 0.164, "20": 0.08, "90": 0.05, "30": 0.03, "40": 0.03},
               "water_content_natural": 0.8, "water_content_canalised": 0.7,
               # metrik IPG: block spacing js = dA / canal slope; category B doubles the spacing
               "ipg_dA_m": 0.4, "ipg_category": "A", "ipg_js_min_m": 50, "ipg_js_max_m": 2000,
               "ipg_canal_class_field": None, "ipg_canal_classes": ["primer", "sekunder", "primary", "secondary"]},
    "indicators": {},                 # override weight / direction / enabled per indicator
    "ahp": {},                        # e.g. {"u": {"indicators": [...], "matrix": [[...]]}}
    "scoring": {"alpha_urgency": 0.6, "normalise_quantiles": [0.05, 0.95], "fixed_thresholds": None,
                "correlation_warn": 0.8, "min_units_per_indicator": 20, "sensitivity_runs": 300, "sensitivity_concentration": 20,
                "top_fraction": 0.2, "validation_burn_threshold": 0.05, "seed": 42,
                "normalise_scope": "all",          # "all" (compare across KHG) | "khg" (within each KHG)
                "tidal_mode": "downweight", "tidal_factor": 0.7,   # or "exclude"
                "method": "need",                  # sub-KHG run: "need" (score) or "ranksum" (earlier slide method); see subkhg/README.md
                "ranksum_weights": {},             # sub-KHG ranksum: indicator -> weight (default 1 each; 0 drops one)
                "ranksum_directions": {},          # sub-KHG ranksum: indicator -> 1 (higher = more need) or -1
                "ranksum_columns": {},             # sub-KHG ranksum: slide indicator -> column to rank instead
                "national": False,                 # national run: risk tertiles only, no feasibility classes
                "top_n": 10},                      # national run: size of the shortlist file
    "maps": True,
}


def load_config(config_path, preset, level, khg=None, out=None):
    cfg = copy.deepcopy(DEFAULTS)
    user = {}
    if config_path:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    deep_update(cfg, copy.deepcopy(preset))
    deep_update(cfg, expand_env(user))
    cfg["level"] = level
    if khg:
        cfg["khg"] = khg
    if out:
        cfg["out"] = out
    y = cfg["years"]
    y["all"] = sorted(set(range(y["baseline"][0], y["baseline"][1] + 1)) | set(y["validation"]) | set(y["elnino"]))
    return cfg


def merge_indicators(df: pd.DataFrame, table: pd.DataFrame, source: str = "extra table") -> pd.DataFrame:
    """Left-join an indicator table on unit_id. Columns that already exist are replaced by the table's."""
    if "unit_id" not in table:
        raise ValueError(f"{source}: needs a unit_id column")
    t = table.drop(columns=[c for c in ("khg_id", "geometry") if c in table]).drop_duplicates("unit_id")
    t["unit_id"] = t["unit_id"].astype(str)
    over = [c for c in t.columns if c != "unit_id" and c in df.columns]
    if over:
        log.info("%s replaces computed columns: %s", source, ", ".join(over))
    out = df.drop(columns=over).merge(t, on="unit_id", how="left")
    missing = float((~df["unit_id"].astype(str).isin(t["unit_id"])).mean())
    if missing > 0:
        log.warning("%s has no row for %.0f%% of the units", source, 100 * missing)
    return out


BALANCE_COLUMNS = ("u_wb_mean", "u_deficit_months", "p_minus_et_mean_mm")


def gate_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Blank the neraca air balance columns of units whose table says the order of sub-KHG is not stable
    (balance_stable_ok = 0: the ET products disagree on the order of units, or the order changes between years; repeat_neraca.balance).
    Units with the flag empty (KHG-level runs) or 1 keep their values."""
    if "balance_stable_ok" not in df:
        return df
    bad = df["balance_stable_ok"].eq(0)
    cols = [c for c in BALANCE_COLUMNS if c in df]
    if bad.any() and cols:
        log.info("neraca air balance not stable for %d units (balance_stable_ok = 0): %s left empty", int(bad.sum()), ", ".join(cols))
        df = df.copy()
        df.loc[bad, cols] = np.nan
    return df


def read_indicator_table(path) -> pd.DataFrame:
    import geopandas as gpd
    path = str(path)
    return pd.read_csv(path) if path.lower().endswith(".csv") else pd.DataFrame(gpd.read_file(path))


def save_maps(out: Path, gdf, class_colors=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except Exception:
        return
    colors = {SC.CLASS_ORDER[0]: "#0F6E56", SC.CLASS_ORDER[1]: "#5DCAA5", SC.CLASS_ORDER[2]: "#D85A30",
              SC.CLASS_ORDER[3]: "#EF9F27", SC.CLASS_ORDER[4]: "#D3D1C7"}
    colors = class_colors or colors
    for kid, g in gdf.groupby("khg_id"):
        b = g.total_bounds
        g = g.to_crs(G.auto_utm((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
        fig, axes = plt.subplots(1, 4, figsize=(20, 5.5))
        for ax, col, ttl in zip(axes[:3], ["skor_urgensi", "skor_dampak", "skor_kelayakan"],
                                ["Urgensi", "Dampak", "Kelayakan"]):
            g.plot(column=col, cmap="YlOrRd" if col != "skor_kelayakan" else "BuGn", vmin=0, vmax=1,
                   ax=ax, legend=True, missing_kwds={"color": "#eeeeee"})
            ax.set_title(ttl)
            ax.set_axis_off()
        g.plot(color=g["kelas"].map(colors).fillna("#eeeeee"), ax=axes[3], linewidth=0)
        axes[3].legend(handles=[Patch(color=c, label=k) for k, c in colors.items()], loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
        axes[3].set_title("Kelas prioritas")
        axes[3].set_axis_off()
        fig.suptitle(f"KHG {kid}")
        fig.tight_layout()
        fig.savefig(out / f"peta_prioritas_{kid}.png", dpi=150)
        plt.close(fig)


def main(level: str, preset: dict, description: str, argv=None, score=None, class_colors=None,
         extra_indicators=(), after=None):
    """score(df, cfg) -> (ranked df, report) replaces the shared risk x feasibility scoring (common.scoring.score).
    extra_indicators: functions f(cfg, khg_id, units, grid, cache) -> DataFrame with unit_id and indicator columns,
    merged into each KHG's indicators (an analysis module, e.g. a water balance, plugs in here).
    Files listed in cfg["extra_indicators"] are merged the same way.
    after(gdf, cfg, out): called once the ranking is written (the sub-KHG program writes subkhg_priority.csv here)."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--config")
    ap.add_argument("--khg")
    ap.add_argument("--out")
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--print-default-config", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("azure", "rasterio._env", "rasterio._err", "fsspec", "pyogrio._io"):   # per-request / per-file chatter
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if a.print_default_config:
        import yaml
        print(yaml.safe_dump(load_config(None, preset, level), sort_keys=False, allow_unicode=True))
        return
    cfg = load_config(a.config, preset, level, a.khg, a.out)
    t0 = time.time()
    import geopandas as gpd
    if not cfg["khg"]:
        raise SystemExit("set 'khg' (KHG boundary file) in the config or with --khg")
    khg = gpd.read_file(cfg["khg"]).to_crs(4326)
    idf = cfg["khg_id_field"]
    if idf not in khg.columns:
        khg[idf] = [f"KHG{i + 1:02d}" for i in range(len(khg))]
    khg[idf] = khg[idf].astype(str)
    if cfg["khg_filter"]:
        khg = khg[khg[idf].isin([str(x) for x in cfg["khg_filter"]])]
    out = Path(cfg["out"])
    out.mkdir(parents=True, exist_ok=True)

    mode = cfg["units"]["mode"]
    if mode == "subkhg":
        raise SystemExit("units.mode 'subkhg' (delineation inside this program) was removed: run repeat-delineation first, then set "
                         "units: {mode: vector, path: <its out>/subkhg_units.gpkg}")
    units = G.load_units(cfg, khg)
    frames = []
    for _, r in khg.iterrows():
        kid = r[idf]
        grid = G.make_grid(r.geometry, float(cfg["grid_res_m"]))
        cache = Path(cfg["cache_dir"]) / (f"L1_{kid}" if level == "khg" else kid)
        if not a.skip_fetch:
            SRC.build_cache(cfg, kid, r.geometry, grid, cache)
        if a.fetch_only:
            continue
        uk = units[units["khg_id"] == kid]
        if len(uk) == 0:
            log.warning("KHG %s has no units", kid)
            continue
        d = IND.compute(cfg, kid, uk, grid, cache)
        for fn in extra_indicators:
            d = merge_indicators(d, fn(cfg, kid, uk, grid, cache), getattr(fn, "__name__", "extra indicators"))
        frames.append(d)
    if a.fetch_only:
        log.info("fetch done in %.0f s", time.time() - t0)
        return

    df = pd.concat(frames, ignore_index=True)
    for f in cfg["extra_indicators"] or []:
        df = merge_indicators(df, read_indicator_table(f), str(f))
    df = gate_balance(df)
    scored, report = (score or SC.score)(df, cfg)
    corr = report.pop("_corr", None)
    gdf = units.merge(scored.drop(columns=["khg_id"]), on="unit_id", how="inner")
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=4326).sort_values("peringkat")
    gdf.to_file(out / "unit_prioritas.gpkg", layer="unit_prioritas", driver="GPKG")
    pd.DataFrame(gdf.drop(columns="geometry")).to_csv(out / "unit_prioritas.csv", index=False)
    if corr is not None:
        corr.to_csv(out / "korelasi_indikator.csv")
    summary = (gdf.groupby(["khg_id", "kelas"]).agg(unit=("unit_id", "count"), luas_km2=("area_km2", "sum"))
               .reset_index())
    summary.to_csv(out / "ringkasan_kelas.csv", index=False)
    if level == "khg":
        top = gdf.nsmallest(int(cfg["scoring"]["top_n"]), "peringkat")
        top.to_file(out / "khg_terpilih.gpkg", driver="GPKG")
        log.info("national: top %d KHG -> khg_terpilih.gpkg", len(top))
    else:
        cols = [c for c in ("sekat_tambahan", "n_sekat_perlu", "n_sekat_ada") if c in gdf]
        if cols:
            (gdf.groupby(["khg_id", "kelas"])[cols].sum().reset_index()
             .to_csv(out / "kebutuhan_sekat.csv", index=False))
    if after is not None:
        after(gdf, cfg, out)
    if cfg["maps"]:
        save_maps(out, gdf, class_colors)
    report.update({"level": level, "runtime_s": round(time.time() - t0, 1), "n_units": int(len(gdf)),
                   "khg": sorted(gdf["khg_id"].unique().tolist()),
                   "indicator_coverage": {c: float(df[c].notna().mean()) for c in df.columns
                                          if c[:2] in ("u_", "i_", "f_", "v_")},
                   "config": {k: v for k, v in cfg.items() if k != "sources"}})
    with open(out / "laporan.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)
    log.info("done: %d units, outputs in %s (%.0f s)", len(gdf), out, time.time() - t0)

