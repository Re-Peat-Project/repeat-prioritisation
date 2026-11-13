"""Class codes and readers shared by the fire tally (`fire_landstatus`, `fire_tables`, `fire_export`) and the land-status overlays.

Kept free of the rest of the package, so that the fire tally can be packed as a standalone kit
(standalone/fire_kit: python -m kebakaran_lahan) with these four modules only.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import pyogrio
import shapely

log = logging.getLogger("prioritas.fire_common")

# forest area function (Fungsi code in the KWS layer) -> class
KWS_CLASS = {
    "cons": ["CA", "CAL", "SM", "SML", "TN", "TNL", "TWA", "TWAL", "TAHURA", "TB", "HSA (KSA)", "KSA/KPA", "KSAL/KPAL"],
    "hl": ["HL"], "prod": ["HP", "HPT"], "hpk": ["HPK"], "apl": ["APL"], "other": ["TUBUH AIR", "DANAU", "Belum terdefinisi"],
}
CODE_TO_KWS = {c: k for k, cs in KWS_CLASS.items() for c in cs}
# business licence type (IZIN_USAHA in the licence layer) -> class
LIC_VALUE = {"Perkebunan Kelapa Sawit": "sawit", "PBPH": "pbph", "PPHKM": "pphkm", "PPHTR": "pphtr", "Pertambangan": "tambang"}
DMPG_LAYER = "dmpg_villages"


def norm_name(s):
    return re.sub(r"\s+", " ", str(s).replace("’", "'")).strip().lower()


def peat_path(cfg):
    pe = (cfg.get("peat") or {}).get("extent") or (cfg.get("stage3") or {}).get("peat_extent")
    return pe if pe and Path(pe).exists() else None


def load_khg(cfg):
    """KHG boundaries (inputs.khg, NAMA_KHG) with khg_id and nama. khg_id is the registry code (cfg['registry'], columns name and
    khg_code; SK.129/2017) matched on the normalised name; without a registry, or for a name not in it, khg_id is the name."""
    khg = pyogrio.read_dataframe(Path(cfg["data"]) / cfg["inputs"]["khg"])
    khg["_k"] = khg["NAMA_KHG"].map(norm_name)
    reg_path = cfg.get("registry")
    if reg_path and Path(reg_path).exists():
        reg = pd.read_csv(reg_path)
        reg["_k"] = reg["name"].map(norm_name)
        khg = khg.merge(reg[["_k", "khg_code"]], on="_k", how="left")
        miss = khg["khg_code"].isna()
        if miss.any():
            log.warning("%d KHG in the boundary file have no code in the registry: %s", miss.sum(), khg.loc[miss, "NAMA_KHG"].tolist())
        khg["khg_id"] = khg["khg_code"].fillna(khg["NAMA_KHG"])
    else:
        khg["khg_id"] = khg["NAMA_KHG"]
    khg = khg.rename(columns={"NAMA_KHG": "nama"})
    khg["geometry"] = shapely.make_valid(khg.geometry.values)
    return khg[["khg_id", "nama", "geometry"]].reset_index(drop=True)
