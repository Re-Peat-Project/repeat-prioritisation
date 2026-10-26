"""Fire and canal indicators per sub-KHG from the national layers in _data, counted the way the national profile counts them.

The sub-KHG units are passed to `national.profile.build_profile` in place of the national KHG, so both levels use one code
path: burnt-area polygons 2015-2026 (`u_fire_freq`, `u_burn_repeat`, `u_burned_now`), FIRMS VIIRS hotspots 2012-2025
(`u_hotspot`, type 0, confidence n/h), the KLH hotspots of the current year (`u_hotspot_now`, medium and high confidence, with
`hs_now_high_share`), canals by class from `KODE_KANAL` (`u_canal_primary`, `_secondary`, `_tertiary`, `u_canal_density`), and the
validation targets of the held-out years (`v_burned_frac`, `v_hotspot`). Rates are per km2 of peat (GFW composite extent), as
in AGENTS.md; `peat_frac` and `fire_basis` say which denominator each unit got.

Config (sub-KHG):

    national_layers:
      config: ../repeat-prioritisation/configs/examples/national_profile.yaml   # data paths, peat extent, hotspot filters
    years: {baseline: [2015, 2022], validation: [2023], elnino: [2015, 2019]}

The sub-KHG `years` override those of the national config. The functions merge through `pipeline.main(extra_indicators=...)`:
columns with the same name replace the ones `common.indicators` computed from the cloud cache (MODIS burnt area, FIRMS fetch).
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path

import pandas as pd
import shapely
import yaml

log = logging.getLogger("prioritas.subkhg")

COLUMNS = ["u_fire_freq", "u_burn_repeat", "u_burned_now", "burned_ever_frac", "u_hotspot", "u_hotspot_now", "hs_now_high_share",
           "u_canal_density", "u_canal_primary", "u_canal_secondary", "u_canal_tertiary", "v_burned_frac", "v_hotspot",
           "peat_frac", "fire_basis"]


def national_config(cfg: dict) -> dict:
    from repeat_prioritisation.national import profile as NP
    nl = cfg.get("national_layers") or {}
    ncfg = copy.deepcopy(NP.DEFAULTS)
    if nl.get("config"):
        NP._merge(ncfg, yaml.safe_load(Path(nl["config"]).read_text(encoding="utf-8")))
    ncfg = NP._expand(ncfg)
    y = cfg["years"]
    ncfg["years"] = {"baseline": list(y["baseline"]),
                     "validation": [min(y["validation"]), max(y["validation"])] if y.get("validation") else list(y["baseline"])}
    ncfg["tma"]["path"] = None          # the sub-KHG run reads SiTMAT itself (common.indicators)
    return ncfg


def fire_and_canals(cfg: dict, khg_id: str, units, grid, cache) -> pd.DataFrame:
    """One row per unit: the columns of COLUMNS. units: the sub-KHG of one KHG (unit_id, geometry)."""
    if not cfg.get("national_layers"):
        return pd.DataFrame({"unit_id": units["unit_id"].astype(str).values})
    from repeat_prioritisation.national import profile as NP
    ncfg = national_config(cfg)
    u = units.to_crs(4326).reset_index(drop=True)
    k = pd.DataFrame({"khg_id": u["unit_id"].astype(str).values})
    import geopandas as gpd
    k = gpd.GeoDataFrame(k, geometry=shapely.make_valid(u.geometry.values), crs=4326)
    proj = k.to_crs(NP.AEA)
    k["area_km2"] = proj.geometry.area.to_numpy() / 1e6
    k["geom_aea"] = proj.geometry.values
    k["nama"] = k["khg_id"]
    prof, _ = NP.build_profile(ncfg, khg=k)
    out = prof.rename(columns={"khg_id": "unit_id"})
    out["fire_basis"] = out["basis"]
    if not cfg["years"].get("validation"):      # no held-out years: no validation targets
        out[["v_burned_frac", "v_hotspot"]] = float("nan")
    log.info("national layers for %s: %d units, rates per km2 of %s; years %s", khg_id, len(out), out["fire_basis"].iloc[0], ncfg["years"])
    return out[["unit_id"] + [c for c in COLUMNS if c in out.columns]]
